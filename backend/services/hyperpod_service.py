"""Service layer for orchestrating InfraForge-backed HyperPod deployments."""

from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..utils import InfraForgeClient, InfraForgeResult, get_logger
from ..utils.emd import extract_endpoint_from_model_entry

logger = get_logger(__name__)

_OVERRIDE_ENV_MAP = {
    "region": "AWS_REGION",
    "aws_region": "AWS_REGION",
    "cluster_tag": "CLUSTER_TAG",
    "clustertag": "CLUSTER_TAG",
    "gpu_instance_type": "GPU_INSTANCE_TYPE",
    "gpuinstancetype": "GPU_INSTANCE_TYPE",
    "gpu_instance_count": "GPU_INSTANCE_COUNT",
    "gpuinstancecount": "GPU_INSTANCE_COUNT",
    "availability_zone": "AVAILABILITY_ZONE",
    "availabilityzone": "AVAILABILITY_ZONE",
    "stack_name": "STACK_NAME",
    "stackname": "STACK_NAME",
}


class HyperPodService:
    """Expose helpers for launching and tracking InfraForge-driven HyperPod builds."""

    def __init__(self) -> None:
        self._config_manager = get_config()
        self._project_root = Path(__file__).resolve().parents[2]

        self._client: Optional[InfraForgeClient] = None
        self._infraforge_root: Optional[Path] = None
        self._deploy_script_name: Optional[str] = None
        self._destroy_script_name: Optional[str] = None

        self._default_region: str = "us-west-2"
        self._dry_run: bool = True
        self._log_dir: Path = self._project_root / "logs" / "hyperpod"
        self._presets: Dict[str, Any] = {}
        self._supported_overrides: set[str] = set()

        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._job_threads: Dict[str, threading.Thread] = {}
        self._jobs_lock = threading.Lock()

        self._refresh_runtime_config()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_configured(self) -> bool:
        """Return True when InfraForge integration is ready."""

        self._refresh_runtime_config()
        return self._client is not None and self._client.is_available()

    def start_deployment(self, request: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """Kick off a HyperPod deployment using InfraForge."""

        return self._start_job("deploy", request, user_id=user_id)

    def start_destroy(self, request: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """Kick off a HyperPod destroy workflow using InfraForge."""

        return self._start_job("destroy", request, user_id=user_id)

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return status information for a specific job."""

        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return self._public_snapshot(job)

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all tracked jobs ordered by creation time (desc)."""

        with self._jobs_lock:
            jobs = [self._public_snapshot(job) for job in self._jobs.values()]

        return sorted(jobs, key=lambda item: item["created_at"], reverse=True)

    def get_job_logs(self, job_id: str, tail: Optional[int] = 200) -> Dict[str, Any]:
        """Return tail of the log file for a job."""

        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(f"Unknown HyperPod job: {job_id}")
            log_path = Path(job["log_path"])

        if not log_path.exists():
            return {
                "job_id": job_id,
                "log_path": str(log_path),
                "logs": "",
                "message": "Log file not created yet",
            }

        content = self._tail_file(log_path, tail) if tail else log_path.read_text(encoding="utf-8", errors="replace")
        return {
            "job_id": job_id,
            "log_path": str(log_path),
            "tail": tail,
            "logs": content,
        }

    def get_presets(self) -> List[str]:
        """Return available HyperPod presets."""

        self._refresh_runtime_config()
        if not self._presets:
            return []
        return sorted(self._presets.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _start_job(self, action: str, request: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        self._refresh_runtime_config()

        if not self.is_configured():
            raise RuntimeError("InfraForge HyperPod deployment is not configured")

        if action not in {"deploy", "destroy"}:
            raise ValueError(f"Unsupported HyperPod action: {action}")

        config_block = request.get("config") or {}

        preset = self._select_preset(request, config_block)
        if self._presets and preset not in self._presets:
            raise ValueError(
                f"Preset '{preset}' is not supported. Available presets: {sorted(self._presets.keys())}"
            )

        region = (
            request.get("region")
            or config_block.get("region")
            or request.get("aws_region")
            or self._default_region
        )

        overrides_input = (
            request.get("overrides")
            or request.get("config_overrides")
            or config_block.get("overrides")
            or {}
        )
        environment_input = request.get("environment") or {}

        dry_run = request.get("dry_run")
        dry_run = self._dry_run if dry_run is None else bool(dry_run)

        job_id = request.get("job_id") or str(uuid.uuid4())
        now_iso = datetime.utcnow().isoformat()

        env = self._build_environment(region, overrides_input, environment_input)
        log_path = self._build_log_path(job_id, preset, action)

        job_payload = {
            "id": job_id,
            "action": action,
            "preset": preset,
            "status": "queued",
            "created_at": now_iso,
            "updated_at": now_iso,
            "user_id": user_id,
            "region": region,
            "dry_run": dry_run,
            "env": env,
            "log_path": str(log_path),
            "preset_config": self._presets.get(preset),
            "result": None,
            "error": None,
        }

        with self._jobs_lock:
            self._jobs[job_id] = job_payload

        thread = threading.Thread(target=self._execute_job, args=(job_id,), daemon=True)
        self._job_threads[job_id] = thread
        thread.start()

        logger.info(
            "HyperPod %s job submitted", action,
            extra={"job_id": job_id, "preset": preset, "dry_run": dry_run}
        )

        return self._public_snapshot(job_payload)

    def _execute_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return

        self._update_job(job_id, status="running", started_at=datetime.utcnow().isoformat())

        try:
            result = self._client.run(
                job["preset"],
                action=job["action"],
                log_path=job["log_path"],
                env_overrides=job["env"],
                dry_run=job["dry_run"],
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("HyperPod job %s failed: %s", job_id, exc)
            self._update_job(
                job_id,
                status="failed",
                error=str(exc),
                finished_at=datetime.utcnow().isoformat(),
            )
            self._job_threads.pop(job_id, None)
            return

        job_result = self._build_result_payload(result)
        status = self._derive_status(job["action"], result)

        update_payload: Dict[str, Any] = {
            "status": status,
            "result": job_result,
            "finished_at": result.finished_at.isoformat(),
        }
        if result.error:
            update_payload["error"] = result.error

        self._update_job(job_id, **update_payload)

        if result.succeeded:
            logger.info(
                "HyperPod %s job %s completed", job["action"], job_id,
                extra={"job_id": job_id, "duration": job_result["duration_seconds"]}
            )
            try:
                self._ingest_job_outputs(job, job_result)
            except Exception as exc:  # pragma: no cover
                logger.warning("Unable to ingest outputs for job %s: %s", job_id, exc)
        else:
            logger.warning(
                "HyperPod %s job %s failed", job["action"], job_id,
                extra={"job_id": job_id, "error": result.error}
            )

        self._job_threads.pop(job_id, None)

    def _build_environment(
        self,
        region: Optional[str],
        overrides: Any,
        environment_input: Dict[str, Any],
    ) -> Dict[str, str]:
        env: Dict[str, str] = {}

        if region:
            env["AWS_REGION"] = str(region)
            env.setdefault("AWS_DEFAULT_REGION", str(region))

        if isinstance(overrides, dict):
            for key, value in overrides.items():
                if value is None:
                    continue
                env_key = self._map_override_key(str(key))
                if env_key:
                    env[env_key] = str(value)

        if isinstance(environment_input, dict):
            for key, value in environment_input.items():
                if value is None:
                    continue
                env[str(key)] = str(value)

        return env

    def _map_override_key(self, key: str) -> Optional[str]:
        normalized = key.lower()
        if self._supported_overrides and normalized not in self._supported_overrides:
            return None
        return _OVERRIDE_ENV_MAP.get(normalized, key.upper())

    def _build_log_path(self, job_id: str, preset: str, action: str) -> Path:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"{job_id}-{action}-{preset}.log"
        return (self._log_dir / suffix).resolve()

    def _update_job(self, job_id: str, **fields: Any) -> None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.update(fields)
            job["updated_at"] = datetime.utcnow().isoformat()

    def _public_snapshot(self, job: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = {
            "job_id": job["id"],
            "action": job["action"],
            "preset": job["preset"],
            "status": job["status"],
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
            "dry_run": job["dry_run"],
            "region": job.get("region"),
            "log_path": job.get("log_path"),
            "user_id": job.get("user_id"),
            "preset_config": job.get("preset_config"),
        }

        if "started_at" in job:
            snapshot["started_at"] = job["started_at"]
        if "finished_at" in job:
            snapshot["finished_at"] = job["finished_at"]
        if job.get("result") is not None:
            snapshot["result"] = job["result"]
        if job.get("error"):
            snapshot["error"] = job["error"]

        return snapshot

    def _ingest_job_outputs(self, job: Dict[str, Any], result_payload: Dict[str, Any]) -> None:
        """Capture deployment outputs (e.g., inference endpoints) after a successful run."""

        if job.get("dry_run"):
            logger.debug("Skipping output ingestion for dry-run HyperPod job %s", job.get("id"))
            return

        prefix = self._config_manager.get("hyperpod.outputs_parameter_prefix")
        if not prefix:
            return

        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError:  # pragma: no cover
            logger.debug("boto3 not available; cannot ingest HyperPod outputs")
            return

        job_id = job.get("id")
        if not job_id:
            return

        region = job.get("region") or self._default_region
        path = f"{prefix.rstrip('/')}/{job_id}"

        try:
            ssm_client = boto3.client("ssm", region_name=region)
        except Exception as exc:  # pragma: no cover
            logger.warning("Unable to initialise SSM client for HyperPod outputs: %s", exc)
            return

        parameters: Dict[str, Any] = {}
        next_token: Optional[str] = None

        try:
            while True:
                response = ssm_client.get_parameters_by_path(
                    Path=path,
                    Recursive=True,
                    WithDecryption=True,
                    NextToken=next_token
                )

                for parameter in response.get("Parameters", []):
                    name = parameter.get("Name", "")
                    key = name.split("/")[-1] if name else None
                    if key:
                        parameters[key] = parameter.get("Value")

                next_token = response.get("NextToken")
                if not next_token:
                    break
        except (BotoCoreError, ClientError) as exc:
            logger.warning("Failed to read HyperPod outputs from %s: %s", path, exc)
            return

        if not parameters:
            logger.info("No HyperPod outputs found under %s", path)
            return

        endpoint = extract_endpoint_from_model_entry(parameters)

        if not endpoint:
            dns_name = parameters.get("NlbDnsName") or parameters.get("nlbDnsName")
            if dns_name:
                endpoint = extract_endpoint_from_model_entry({"DNSName": dns_name})

        if not endpoint:
            logger.info("HyperPod job %s completed but no inference endpoint was discovered", job_id)
            return

        metadata = {
            "raw_parameters": parameters,
            "model_path": parameters.get("ModelId") or parameters.get("modelId"),
            "display_name": parameters.get("ModelName") or parameters.get("modelName"),
            "deployment_type": "SageMaker HyperPod",
        }

        try:
            from .model_service import ModelService

            model_service = ModelService()
            registration = model_service.register_external_endpoint(
                deployment_method="SageMaker HyperPod",
                endpoint_url=endpoint,
                deployment_id=job_id,
                model_name=parameters.get("ModelName") or parameters.get("modelName"),
                metadata=metadata,
            )

            logger.info(
                "Registered HyperPod endpoint %s for job %s (model_key=%s)",
                endpoint,
                job_id,
                registration["model_key"],
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Unable to register HyperPod endpoint for job %s: %s", job_id, exc)

    def _build_result_payload(self, result: InfraForgeResult) -> Dict[str, Any]:
        payload = {
            "returncode": result.returncode,
            "command": " ".join(result.command),
            "dry_run": result.dry_run,
            "succeeded": result.succeeded,
            "duration_seconds": result.duration_seconds,
            "started_at": result.started_at.isoformat(),
            "finished_at": result.finished_at.isoformat(),
        }
        if result.error:
            payload["error"] = result.error
        return payload

    def _derive_status(self, action: str, result: InfraForgeResult) -> str:
        if not result.succeeded:
            return "failed" if action == "deploy" else "destroy_failed"
        if action == "destroy":
            return "destroyed"
        return "succeeded"

    def _tail_file(self, path: Path, max_lines: Optional[int]) -> str:
        if max_lines is None or max_lines <= 0:
            return path.read_text(encoding="utf-8", errors="replace")

        with open(path, "r", encoding="utf-8", errors="replace") as file_handle:
            lines = deque(file_handle, maxlen=max_lines)
        return "".join(lines)

    def _select_preset(self, request: Dict[str, Any], config_block: Dict[str, Any]) -> str:
        return str(
            request.get("preset")
            or config_block.get("preset")
            or config_block.get("size")
            or request.get("size")
            or "small"
        )

    def _refresh_runtime_config(self) -> None:
        hyperpod_cfg = self._config_manager.get("hyperpod", {}) or {}

        self._default_region = (
            hyperpod_cfg.get("default_region")
            or hyperpod_cfg.get("region")
            or self._default_region
        )

        infraforge_root_value = hyperpod_cfg.get("infraforge_root") or "../InfraForge"
        deploy_script_value = hyperpod_cfg.get("deploy_script") or "scripts/deploy_hyperpod.sh"
        destroy_script_value = hyperpod_cfg.get("destroy_script") or deploy_script_value
        dry_run = bool(hyperpod_cfg.get("dry_run", self._dry_run))
        log_dir_value = hyperpod_cfg.get("log_directory") or "logs/hyperpod"

        presets_cfg = hyperpod_cfg.get("presets", {})
        if isinstance(presets_cfg, dict):
            presets = presets_cfg
        elif isinstance(presets_cfg, list):
            presets = {item: None for item in presets_cfg}
        else:
            presets = {}

        supported_overrides = {
            str(item).lower() for item in hyperpod_cfg.get("supported_overrides", [])
        }

        infraforge_root_path = self._resolve_path(infraforge_root_value)
        log_dir_path = self._resolve_path(log_dir_value)

        needs_client = (
            self._client is None
            or self._infraforge_root != infraforge_root_path
            or self._deploy_script_name != deploy_script_value
            or self._destroy_script_name != destroy_script_value
        )

        if needs_client:
            self._client = InfraForgeClient(
                infraforge_root_path,
                deploy_script_value,
                destroy_script_value,
                dry_run=dry_run,
            )
            self._infraforge_root = infraforge_root_path
            self._deploy_script_name = deploy_script_value
            self._destroy_script_name = destroy_script_value
        elif self._client is not None:
            self._client.set_dry_run(dry_run)

        self._dry_run = dry_run
        self._log_dir = log_dir_path
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._presets = presets
        self._supported_overrides = supported_overrides

    def _resolve_path(self, path_value: str) -> Path:
        path = Path(path_value)
        if not path.is_absolute():
            path = (self._project_root / path).resolve()
        return path
