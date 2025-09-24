# InfraForge Integration Plan for Perf Evaluation Platform

## Goal and Context
- Deliver a single automated path for Perf Eval users to provision SageMaker HyperPod clusters, bootstrap add-ons, and hand off inference endpoints without leaving the UI, aligning with the automation vision in `infraforge_HYPERPOD_AUTOMATION_PLAN.md` (§1–3).
- Replace the manual shell scripts in `reference_folder/HyperPod-InstantStart/HYPERPOD_DEPLOYMENT_GUIDE.md` with InfraForge-driven workflows, while preserving the proven guardrails (naming, quota, OIDC) captured in the guide (§7 and §10).

## Target End-to-End Experience
1. **Launch** – User selects a HyperPod preset (small/medium/large) and optional overrides (region, GPU count, model manifests) from the Model Hub wizard.
2. **Provision** – Backend calls an asynchronous deployment service that wraps the InfraForge CLI with the chosen `configs/hyperpod/*.yaml` profile and dynamic parameters (stack/tag names, subnets, quotas).
3. **Validate** – Post-deploy checks confirm guardrails: quotas, ALB controller/IAM, subnets, and health per automation plan (§4) before exposing cluster details.
4. **Handshake** – Deployment outputs (cluster ARN, EKS name, NLB DNS, S3 buckets) are persisted to Parameter Store/S3 (automation plan §5) and mirrored into the platform database.
5. **Operate** – Perf Eval surfaces endpoints for inference and enables stress tests against the freshly created cluster; cleanup hooks tear down resources through InfraForge when requested.

## Implementation Snapshot (2025-02)
- **Backend service** – `backend/services/hyperpod_service.py` orchestrates InfraForge shell scripts, runs jobs asynchronously, and persists logs under `logs/hyperpod`. Dry-run mode defaults to `true` in development to enable local validation without touching AWS.
- **InfraForge client** – `backend/utils/infraforge_client.py` provides a reusable runner with log streaming, timeout handling, and optional dry-run execution for both deploy and destroy actions.
- **API surface** – `/api/hyperpod/deploy`, `/api/hyperpod/destroy`, `/api/hyperpod/jobs`, `/api/hyperpod/jobs/<job_id>`, `/api/hyperpod/jobs/<job_id>/logs`, and `/api/hyperpod/presets` expose the orchestration workflow. A legacy `/api/hyperpod/status?jobId=` endpoint remains for backward compatibility.
- **Configuration** – `config/environments/*.yaml` now includes `hyperpod` entries describing the InfraForge root, script paths, presets, log directory, and supported overrides. Production can disable dry-run to execute real deployments.
- **Job metadata** – Service responses include timestamps, command metadata, dry-run flag, and preset info so the UI can surface guardrail context while deployments run.
- **Tooling** – `scripts/fetch_infraforge.sh` clones or updates InfraForge into the expected directory on EC2 hosts so the backend can invoke the CLI without manual git steps.

## High-Level Architecture Changes
- **Deployment Orchestrator**: Package InfraForge as a containerized job (AWS Step Functions + ECS/Fargate or AWS Batch). The backend posts a job request and receives a job ID (automation plan Phase 2).
- **Backend Integration Layer**:
  - New service module (`backend/services/hyperpod_service.py`) managing request validation, job submission, status polling, and result ingestion.
  - REST endpoints under `/api/hyperpod` for `deploy`, `status/<job_id>`, `list`, `delete`, `logs`.
  - Background scheduler (e.g., APScheduler worker) polling job state or subscribing to EventBridge notifications written by the orchestrator.
  - Persistence via existing SQLite/postgres layers: add `hyperpod_jobs` and `hyperpod_clusters` tables capturing job metadata, guardrail checks, and outputs.
- **Frontend Enhancements**:
  - Extend Model Hub with a "HyperPod" tab featuring config presets (mirroring InfraForge `config_hyperpod_{size}.yaml`) and guardrail previews (quota availability, naming budget).
  - Real-time status panel (Phase 3) consuming `/api/hyperpod/status`.
  - Quick actions to register the resulting inference endpoint into StressTestService.
- **Configuration & Secrets**:
  - Store InfraForge runtime configuration (paths to configs, S3/SSM prefixes, IAM role ARNs) in `backend/config/hyperpod.yaml` and load via `get_config`.
  - Use STS AssumeRole for cross-account deployments when required (automation plan Phase 3 credential decision).

## Deployment Workflow Details
1. **Input Assembly**
   - Merge UI selections with base config (`configs/hyperpod/config_hyperpod.yaml`).
   - Apply naming guardrails (<=63 char bucket limit) per HyperPod guide §7.1.
   - Validate quotas (Service Quotas APIs in guardrail checklist §4).
   - Choose subnets/VPC from config or catalog (use insights from Instant Start guide §§3–4).
2. **Job Submission**
   - Backend invokes a lightweight Lambda that starts a Step Function execution, passing config payload and a callback token (see `docs/hyperpod_step_function.asl.json` and `docs/hyperpod_step_function.md`).
   - Step Function tasks:
     1. Generate working configuration file and upload to S3.
     2. Run InfraForge container with `config.json` pointing to the generated config.
     3. Capture CDK synth/deploy logs; push to CloudWatch and S3.
     4. Execute post-deploy validator Lambda (HyperPod status, ALB controller, OIDC trust).
     5. Persist outputs to Parameter Store/S3 (`/hyperpod/<job_id>/clusterArn`, etc.).
   - On failure, trigger cleanup task (automation plan Phase 2 rollback) using InfraForge destroy mode or CloudFormation delete.
3. **Status Tracking**
   - Step Function emits execution events to EventBridge; backend subscribes through Webhook or scheduled polling (new `/api/hyperpod/status`).
   - Cache last known state in `hyperpod_jobs` table with timestamps and failure reasons.
4. **Post-Deploy Handshake**
   - Once status == `SUCCEEDED`, backend reads Parameter Store outputs, stores them in `hyperpod_clusters`, and registers available endpoints into `model_service` / `stress_test_service` for immediate benchmarking.
   - Provide helper endpoints to fetch kubeconfig secrets or NLB DNS, respecting IAM/OIDC rules described in the Instant Start guide §§4–5.
5. **Teardown**
   - `/api/hyperpod/delete` triggers InfraForge destroy workflow using stored stack IDs; confirm S3 cleanup as recommended in the guide §7.4.

## Guardrails and Validation (Automation Plan §4, Guide §7–10)
- **Naming**: Enforce `CLUSTER_TAG` limit and auto-suffixing to keep S3 buckets <63 chars; leverage Instant Start guidance (Troubleshooting §1).
- **Quota Checks**: Preflight Service Quotas for HyperPod (`sagemaker` `L-B0E3E2FF`) and GPU instances (`ec2` `L-1216C47A`). Fail fast with actionable errors.
- **IAM/OIDC**: Before deployment, verify OIDC provider and Load Balancer Controller IAM policy; auto-generate trust relationships if missing (automation plan §4, guide Troubleshooting §§3–6).
- **Subnet Validation**: Cross-check service subnets align with HyperPod VPC; expose them in UI with helpful tips from Instant Start §8.
- **Health Probes**: After InfraForge finishes, run scripted `kubectl` checks (node readiness, controller pods) using the bootstrap steps from the guide §§4–6.

## Data Model Additions
- `hyperpod_jobs` (job_id, user_id, status, config_snapshot, infraforge_execution_arn, started_at, finished_at, error_code, guardrail_results).
- `hyperpod_clusters` (cluster_id, job_id, stack_name, hyperpod_arn, eks_cluster_name, kubeconfig_secret, nlb_dns, s3_buckets, parameter_store_path, created_at, expires_at).
- Optionally `hyperpod_logs` metadata pointing to S3/CloudWatch locations for troubleshooting.

## Backend Module Changes
- `backend/services/hyperpod_service.py`: job orchestration, guardrails, InfraForge client wrapper.
- `backend/api/routes/hyperpod_routes.py`: blueprint exposing REST APIs.
- `backend/utils/infraforge_client.py`: shared helper for invoking Lambda/Step Function and reading outputs.
- Extend `backend/utils/storage.py` to persist new tables and job updates.
- Integrate with `stress_test_service.py` to allow immediate throughput tests using returned endpoints.

## Frontend Work Items
1. **Config Wizard**
   - Form with presets (small/medium/large) mapping to InfraForge configs; allow expert overrides for tags, AZs, GPU count.
   - Inline guardrail checks (quota fetch, naming) with info modals referencing Instant Start guide tips.
2. **Status Dashboard**
   - Real-time progress tracker (Queued → Deploying → Validating → Ready / Failed) fed by `/api/hyperpod/status`.
   - Surface guardrail failures with remediation hints (bucket naming, quota, OIDC) drawn from troubleshooting guide §8.
3. **Endpoint Registration**
   - Display NLB DNS and quick "Run Smoke Test" buttons that prefill Stress Test forms.

## Operational Considerations
- **Accounts & Roles**: Define IAM role used by InfraForge job runner; ensure least privilege for CloudFormation, SageMaker HyperPod, EKS, FSx, S3.
- **Configuration Management**: Version `configs/hyperpod` overlays in a dedicated S3 bucket or GitOps repo; track via job metadata for reproducibility.
- **Logging**: Centralize InfraForge CLI logs in CloudWatch (`/InfraForge/HyperPod/<stack>`) as recommended in automation plan FAQ.
- **Metrics**: Emit deployment durations, success rate, guardrail failure counts; align with automation plan Phase 5 monitoring goals.
- **Secrets Handling**: Use AWS Secrets Manager for kubeconfig and MLflow credentials referenced in Instant Start §6.

## Suggested Milestones (Synthesizing Automation Plan Phases)
1. **Sprint 0 (Discovery)**: Confirm regions, quotas, and data model updates; mock UI flow.
2. **Sprint 1 (Forge Enablement)**: Package InfraForge HyperPod forge with config templates; run sandbox deployment from CLI.
3. **Sprint 2 (Runtime Wrapper)**: Stand up Step Function + ECS wrapper; expose MVP backend service for job submission.
4. **Sprint 3 (Platform Integration)**: Wire backend APIs, persistence, and frontend wizard; support status polling and endpoint registration.
5. **Sprint 4 (Validation)**: Execute guardrail chaos tests, document failure handling, integrate logs/metrics.
6. **Sprint 5 (Pilot)**: Run full E2E with selected users, collect feedback, finalize docs/playbooks (`hyperpod-fixed-deployment.md`).

## Documentation & Runbooks
- Update existing guides (`HYPERPOD_DEPLOYMENT_GUIDE.md`, troubleshooting notes) with InfraForge flow once validated.
- Produce operator runbook describing rollback, quota remediation, and manual overrides.
- Add developer guide in `docs/` on extending InfraForge configs and interpreting guardrail results.

## Next Actions
1. Confirm orchestration target (Step Functions vs. direct Lambda runner) and required IAM roles.
2. Prototype backend `hyperpod_service` with mocked InfraForge responses to validate API contract.
3. Align frontend design with UX team; create wireframes for HyperPod wizard and status views.
4. Schedule sandbox deployment to baseline timings and guardrail behavior.
