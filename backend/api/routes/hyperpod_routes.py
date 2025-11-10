"""API routes for managing InfraForge-powered HyperPod deployments."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...services.hyperpod_service import HyperPodService
from ...utils import get_logger

logger = get_logger(__name__)

hyperpod_bp = Blueprint("hyperpod", __name__)
_service = HyperPodService()


@hyperpod_bp.route("/hyperpod/deploy", methods=["POST"])
def deploy_hyperpod():
    """Trigger a new HyperPod deployment via InfraForge."""

    payload = request.get_json() or {}
    user_id = payload.get("requested_by") or payload.get("user_id")

    if not _service.is_configured():
        return jsonify({
            "status": "error",
            "message": "HyperPod deployment backend is not configured. Check infraforge settings.",
        }), 503

    try:
        job = _service.start_deployment(payload, user_id=user_id)
    except ValueError as exc:
        logger.warning("Invalid HyperPod deploy request: %s", exc)
        return jsonify({
            "status": "error",
            "message": str(exc),
        }), 400
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unable to start HyperPod deployment: %s", exc)
        return jsonify({
            "status": "error",
            "message": "Failed to start HyperPod deployment",
        }), 500

    return jsonify({
        "status": "submitted",
        "job": job,
    }), 202


@hyperpod_bp.route("/hyperpod/destroy", methods=["POST"])
def destroy_hyperpod():
    """Trigger a HyperPod destroy workflow via InfraForge."""

    payload = request.get_json() or {}
    user_id = payload.get("requested_by") or payload.get("user_id")

    if not _service.is_configured():
        return jsonify({
            "status": "error",
            "message": "HyperPod deployment backend is not configured. Check infraforge settings.",
        }), 503

    try:
        job = _service.start_destroy(payload, user_id=user_id)
    except ValueError as exc:
        logger.warning("Invalid HyperPod destroy request: %s", exc)
        return jsonify({
            "status": "error",
            "message": str(exc),
        }), 400
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unable to start HyperPod destroy: %s", exc)
        return jsonify({
            "status": "error",
            "message": "Failed to start HyperPod destroy workflow",
        }), 500

    return jsonify({
        "status": "submitted",
        "job": job,
    }), 202


@hyperpod_bp.route("/hyperpod/jobs", methods=["GET"])
def list_hyperpod_jobs():
    """List tracked HyperPod jobs."""

    jobs = _service.list_jobs()
    return jsonify({
        "status": "success",
        "jobs": jobs,
    })


@hyperpod_bp.route("/hyperpod/presets", methods=["GET"])
def list_hyperpod_presets():
    """Return available HyperPod presets."""

    presets = _service.get_presets()
    return jsonify({
        "status": "success",
        "presets": presets,
    })


@hyperpod_bp.route("/hyperpod/jobs/<job_id>", methods=["GET"])
def get_hyperpod_job(job_id: str):
    """Return status information for a specific HyperPod job."""

    status_payload = _service.get_job_status(job_id)
    if not status_payload:
        return jsonify({
            "status": "error",
            "message": f"Unknown HyperPod job: {job_id}",
        }), 404

    return jsonify({
        "status": "success",
        "job": status_payload,
    })


@hyperpod_bp.route("/hyperpod/jobs/<job_id>/logs", methods=["GET"])
def get_hyperpod_job_logs(job_id: str):
    """Return logs for a HyperPod job."""

    tail_param = request.args.get("tail")
    tail_lines = None
    if tail_param is not None:
        try:
            tail_lines = int(tail_param)
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "tail query parameter must be an integer",
            }), 400

    try:
        log_payload = _service.get_job_logs(job_id, tail=tail_lines)
    except KeyError:
        return jsonify({
            "status": "error",
            "message": f"Unknown HyperPod job: {job_id}",
        }), 404
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unable to read HyperPod logs for %s: %s", job_id, exc)
        return jsonify({
            "status": "error",
            "message": "Failed to read HyperPod logs",
        }), 500

    return jsonify({
        "status": "success",
        "logs": log_payload,
    })


@hyperpod_bp.route("/hyperpod/status", methods=["GET"])
def legacy_hyperpod_status():
    """Backward compatible status endpoint using the jobId query parameter."""

    job_id = request.args.get("jobId") or request.args.get("job_id") or request.args.get("executionArn")
    if not job_id:
        return jsonify({
            "status": "error",
            "message": "jobId query parameter is required",
        }), 400

    status_payload = _service.get_job_status(job_id)
    if not status_payload:
        return jsonify({
            "status": "error",
            "message": f"Unknown HyperPod job: {job_id}",
        }), 404

    return jsonify({
        "status": "success",
        "job": status_payload,
    })

