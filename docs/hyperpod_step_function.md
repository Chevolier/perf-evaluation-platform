# HyperPod Deployment State Machine

This document explains the Step Functions workflow that orchestrates InfraForge-driven SageMaker HyperPod deployments for the performance evaluation platform.

## Overview
- **Purpose**: Provide a resilient, observable pipeline for provisioning HyperPod infrastructure, running guardrail checks, and persisting deployment outputs.
- **Entry point**: Requests originate from the backend `HyperPodService`, which starts a Step Functions execution after validating configuration.
- **Execution model**: Standard Step Functions state machine coordinating Lambda functions and an ECS Fargate task that runs the InfraForge CLI.

## State Breakdown
1. **PrepareDeploymentConfig** (`Lambda`)
   - Builds a deployment manifest from user input, applies guardrail presets (naming, quota checks), and uploads configuration to S3 for the InfraForge container.
2. **RunInfraForgeTask** (`ECS::RunTask.sync`)
   - Launches the InfraForge container with environment overrides pointing at the S3 configuration and stack identifiers.
   - Emits CloudWatch logs for traceability; retries on transient ECS or permissions errors.
3. **PostDeploymentValidation** (`Lambda`)
   - Confirms HyperPod cluster health, verifies Load Balancer Controller/OIDC posture, and collects primary outputs (cluster ARN, EKS name, NLB DNS).
4. **PersistDeploymentOutputs** (`Lambda`)
   - Writes deployment metadata to AWS Systems Manager Parameter Store (prefix: `/perf-eval/hyperpod/...`) and S3 for later retrieval by the platform backend.
5. **CleanupOnFailure** (`Lambda`)
   - Invoked whenever InfraForge or validation fails; attempts to destroy partially created stacks or undo resource changes.
6. **RecordFailure** (`Lambda`)
   - Records terminal failure details, including guardrail outcomes and cleanup results, to make them visible to the UI/backend.
7. **Success**
   - Terminal `Succeed` state reached after outputs are safely persisted.

## Failure Handling
- Each task has exponential backoff retries for service exceptions.
- Failures route through `CleanupOnFailure`, ensuring CloudFormation stacks and ancillary resources are removed.
- `RecordFailure` centralizes logging and metrics so that downstream systems can surface actionable messages to users.

## Inputs & Outputs
- **Input payload** (from backend):
  ```json
  {
    "jobId": "<uuid>",
    "requestedBy": "<user>",
    "requestedAt": "2025-01-01T00:00:00Z",
    "timeoutSeconds": 3600,
    "config": {"preset": "medium", "region": "us-west-2", ...},
    "guardrails": {"quotaChecks": true},
    "artifacts": {
      "configBucket": "perf-eval-hyperpod-config",
      "parameterPrefix": "/perf-eval/hyperpod"
    }
  }
  ```
- **Outputs** (on success): stored under `/perf-eval/hyperpod/<jobId>/...` and include stack IDs, ARNs, DNS names, and guardrail reports. The Step Functions `output` field mirrors this structure for the backend.

## Related Files
- `docs/hyperpod_step_function.asl.json` — machine-readable Amazon States Language definition.
- `backend/services/hyperpod_service.py` — backend integration that launches executions and retrieves status.
- `backend/api/routes/hyperpod_routes.py` — REST surface for deployment and status queries.

## Next Steps
- Implement the Lambda functions and ECS task definition referenced in the state machine.
- Wire EventBridge notifications to push status updates back to the platform without polling.
- Extend the frontend HyperPod wizard to display guardrail results and execution progress in real time.
