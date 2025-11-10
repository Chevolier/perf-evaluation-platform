"""Utility client for invoking InfraForge automation workflows."""

from __future__ import annotations

import os
import subprocess
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class InfraForgeResult:
    """Capture the outcome of an InfraForge command execution."""

    command: List[str]
    returncode: int
    succeeded: bool
    dry_run: bool
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    log_path: Optional[str] = None
    error: Optional[str] = None


class InfraForgeClient:
    """Thin wrapper around InfraForge shell scripts with dry-run support."""

    def __init__(
        self,
        root_path: Path | str,
        deploy_script: Path | str,
        destroy_script: Path | str | None = None,
        *,
        dry_run: bool = False,
    ) -> None:
        self._root_path = Path(root_path).resolve()
        self._deploy_script = self._resolve_script_path(deploy_script)
        destroy_script_path = destroy_script if destroy_script is not None else deploy_script
        self._destroy_script = self._resolve_script_path(destroy_script_path)
        self._dry_run = dry_run

    @property
    def root_path(self) -> Path:
        """Return InfraForge project root."""

        return self._root_path

    @property
    def deploy_script(self) -> Path:
        """Return path to the deployment script."""

        return self._deploy_script

    @property
    def destroy_script(self) -> Path:
        """Return path to the destroy script."""

        return self._destroy_script

    @property
    def dry_run(self) -> bool:
        """Return the client's dry-run setting."""

        return self._dry_run

    def set_dry_run(self, enabled: bool) -> None:
        """Update dry-run mode at runtime."""

        self._dry_run = bool(enabled)

    def is_available(self) -> bool:
        """Return True if InfraForge scripts are accessible."""

        return self._root_path.exists() and self._deploy_script.exists()

    def list_scripts(self) -> Dict[str, str]:
        """Return resolved script locations for diagnostics."""

        return {
            "root": str(self._root_path),
            "deploy_script": str(self._deploy_script),
            "destroy_script": str(self._destroy_script),
        }

    def run(
        self,
        preset: str,
        *,
        action: str = "deploy",
        log_path: Optional[Path | str] = None,
        env_overrides: Optional[Dict[str, str]] = None,
        dry_run: Optional[bool] = None,
        timeout: Optional[int] = None,
    ) -> InfraForgeResult:
        """Execute an InfraForge workflow.

        Args:
            preset: HyperPod preset (translates to config selection).
            action: `deploy` (default) or `destroy`.
            log_path: Optional file path to stream logs into.
            env_overrides: Environment variables to merge into the process env.
            dry_run: Override dry-run behaviour for this invocation.
            timeout: Optional timeout (seconds) for the command.

        Returns:
            InfraForgeResult describing the execution outcome.
        """

        command = self._build_command(preset, action=action)
        execution_dry_run = self._dry_run if dry_run is None else bool(dry_run)
        started_at = datetime.utcnow()
        log_file_path = Path(log_path).resolve() if log_path else None
        if log_file_path:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)

        if execution_dry_run:
            self._write_dry_run_log(log_file_path, command, env_overrides, started_at)
            finished = datetime.utcnow()
            return InfraForgeResult(
                command=command,
                returncode=0,
                succeeded=True,
                dry_run=True,
                started_at=started_at,
                finished_at=finished,
                duration_seconds=(finished - started_at).total_seconds(),
                log_path=str(log_file_path) if log_file_path else None,
            )

        env = os.environ.copy()
        if env_overrides:
            env.update({key: str(value) for key, value in env_overrides.items() if value is not None})

        stdout_pipe = None
        log_file_ctx = nullcontext()
        if log_file_path:
            log_file_ctx = open(log_file_path, "a", encoding="utf-8")

        try:
            with log_file_ctx as log_file:
                process = subprocess.Popen(
                    command,
                    cwd=str(self._root_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                )
                stdout_pipe = process.stdout

                if stdout_pipe is not None:
                    for line in iter(stdout_pipe.readline, ""):
                        if log_file:
                            log_file.write(line)
                            log_file.flush()

                returncode = process.wait(timeout=timeout)
                finished_at = datetime.utcnow()
                return InfraForgeResult(
                    command=command,
                    returncode=returncode,
                    succeeded=returncode == 0,
                    dry_run=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=(finished_at - started_at).total_seconds(),
                    log_path=str(log_file_path) if log_file_path else None,
                )

        except subprocess.TimeoutExpired as exc:
            if 'process' in locals():
                process.kill()
            finished_at = datetime.utcnow()
            message = f"InfraForge command timed out after {timeout}s"
            self._append_log_message(log_file_path, message)
            return InfraForgeResult(
                command=command,
                returncode=-1,
                succeeded=False,
                dry_run=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                log_path=str(log_file_path) if log_file_path else None,
                error=message,
            )
        except FileNotFoundError as exc:
            finished_at = datetime.utcnow()
            message = f"InfraForge script not found: {exc}"
            self._append_log_message(log_file_path, message)
            return InfraForgeResult(
                command=command,
                returncode=-1,
                succeeded=False,
                dry_run=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                log_path=str(log_file_path) if log_file_path else None,
                error=message,
            )
        except Exception as exc:  # pylint: disable=broad-except
            finished_at = datetime.utcnow()
            message = f"InfraForge command failed: {exc}"
            self._append_log_message(log_file_path, message)
            return InfraForgeResult(
                command=command,
                returncode=-1,
                succeeded=False,
                dry_run=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                log_path=str(log_file_path) if log_file_path else None,
                error=message,
            )
        finally:
            if stdout_pipe is not None and not stdout_pipe.closed:
                stdout_pipe.close()

    def _build_command(self, preset: str, *, action: str) -> List[str]:
        if action not in {"deploy", "destroy"}:
            raise ValueError(f"Unsupported InfraForge action: {action}")

        script_path = self._deploy_script if action == "deploy" else self._destroy_script
        return ["bash", str(script_path), preset] + ([] if action == "deploy" else [action])

    def _resolve_script_path(self, script: Path | str) -> Path:
        script_path = Path(script)
        if not script_path.is_absolute():
            script_path = (self._root_path / script_path).resolve()
        return script_path

    def _write_dry_run_log(
        self,
        log_path: Optional[Path],
        command: Iterable[str],
        env_overrides: Optional[Dict[str, str]],
        timestamp: datetime,
    ) -> None:
        if not log_path:
            return

        lines = [
            f"[{timestamp.isoformat()}] [DRY-RUN] InfraForge execution simulated.",
            f"[{timestamp.isoformat()}] [DRY-RUN] Command: {' '.join(command)}",
        ]

        if env_overrides:
            lines.append(f"[{timestamp.isoformat()}] [DRY-RUN] Environment overrides: {env_overrides}")

        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write("\n".join(lines) + "\n")

    def _append_log_message(self, log_path: Optional[Path], message: str) -> None:
        if not log_path:
            return
        timestamp = datetime.utcnow().isoformat()
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")
