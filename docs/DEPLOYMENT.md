# EMD Deployment Guide

This guide covers deploying and managing EMD (Easy Model Deployer) models for the Multimodal Inference Platform.

## Prerequisites

- EMD CLI installed (`pip install emd-cli`)
- AWS credentials configured
- Sufficient AWS quotas for chosen instance types

## Model Deployment

### Supported Models

The platform supports these EMD models:

| Model Key | Model ID | Description |
|-----------|----------|-------------|
| `qwen2-vl-7b` | `Qwen2-VL-7B-Instruct` | 7B vision-language model |
| `qwen2.5-vl-32b` | `Qwen2.5-VL-32B-Instruct` | 32B advanced vision model |
| `gemma-3-4b` | `gemma-3-4b-it` | 4B instruction-tuned model |
| `ui-tars-1.5-7b` | `UI-TARS-1.5-7B` | 7B UI understanding model |

### Deployment Commands

#### Qwen2-VL-7B (Recommended for testing)
```bash
emd deploy --model-id Qwen2-VL-7B-Instruct \
           --instance-type g5.12xlarge \
           --engine-type vllm \
           --service-type sagemaker_realtime \
           --model-tag dev
```

#### Qwen2.5-VL-32B (Higher performance)
```bash
emd deploy --model-id Qwen2.5-VL-32B-Instruct \
           --instance-type g5.48xlarge \
           --engine-type vllm \
           --service-type sagemaker_realtime \
           --model-tag dev
```

#### Gemma-3-4B (Lightweight)
```bash
emd deploy --model-id gemma-3-4b-it \
           --instance-type g5.2xlarge \
           --engine-type vllm \
           --service-type sagemaker_realtime \
           --model-tag dev
```

#### UI-TARS-1.5-7B (UI focused)
```bash
emd deploy --model-id UI-TARS-1.5-7B \
           --instance-type g5.12xlarge \
           --engine-type vllm \
           --service-type sagemaker_realtime \
           --model-tag dev
```

### Instance Types

| Instance Type | vCPUs | Memory | GPU | Use Case |
|---------------|-------|--------|-----|----------|
| `g5.2xlarge` | 8 | 32 GB | 1x A10G | Small models (4B) |
| `g5.12xlarge` | 48 | 192 GB | 4x A10G | Medium models (7B) |
| `g5.48xlarge` | 192 | 768 GB | 8x A10G | Large models (32B+) |

## Deployment Process

### 1. Bootstrap EMD (First time only)
```bash
emd bootstrap
```

### 2. Deploy Model
```bash
emd deploy --model-id Qwen2-VL-7B-Instruct \
           --instance-type g5.12xlarge \
           --engine-type vllm \
           --service-type sagemaker_realtime \
           --model-tag dev
```

### 3. Monitor Deployment
```bash
# Check deployment status
emd status

# View deployment logs
emd logs

# List all models
emd list-models
```

## Deployment Status

### Status Types

- **Creating**: Deployment in progress
- **InService**: Model ready for inference
- **Failed**: Deployment failed
- **Updating**: Model being updated
- **Deleting**: Model being deleted

### Example Status Output
```bash
$ emd status

Model: Qwen2-VL-7B-Instruct
Status: InService
Endpoint: https://runtime.sagemaker.us-west-2.amazonaws.com/endpoints/qwen2-vl-7b-dev
Created: 2025-07-28 06:30:00
Instance: g5.12xlarge
```

## Managing Deployments

### Update Model
```bash
emd update --model-id Qwen2-VL-7B-Instruct --model-tag v2
```

### Delete Model
```bash
emd delete --model-id Qwen2-VL-7B-Instruct --model-tag dev
```

### Scale Instance
```bash
emd scale --model-id Qwen2-VL-7B-Instruct \
          --instance-count 2
```

## Troubleshooting

### Common Issues

#### 1. Deployment Stuck in "Creating"
```bash
# Check logs for detailed error
emd logs --model-id Qwen2-VL-7B-Instruct

# Common causes:
# - Insufficient quota for instance type
# - Invalid model configuration
# - AWS service issues
```

#### 2. "InsufficientInstanceCapacity" Error
```bash
# Try different availability zone
emd deploy --model-id Qwen2-VL-7B-Instruct \
           --instance-type g5.12xlarge \
           --availability-zone us-west-2b

# Or try smaller instance type
emd deploy --model-id Qwen2-VL-7B-Instruct \
           --instance-type g5.2xlarge
```

#### 3. Authentication Errors
```bash
# Refresh AWS credentials
aws sts get-caller-identity

# Check EMD configuration
emd config show
```

#### 4. Model Loading Timeout
```bash
# Increase timeout for large models
emd deploy --model-id Qwen2.5-VL-32B-Instruct \
           --instance-type g5.48xlarge \
           --timeout 1800  # 30 minutes
```

### Debug Commands

```bash
# Verbose deployment
emd deploy --model-id Qwen2-VL-7B-Instruct \
           --instance-type g5.12xlarge \
           --verbose

# Check endpoint health
emd health --model-id Qwen2-VL-7B-Instruct

# View metrics
emd metrics --model-id Qwen2-VL-7B-Instruct
```

## Cost Optimization

### Instance Selection
- Use smallest instance that handles your model
- g5.2xlarge for 4B models
- g5.12xlarge for 7B models
- g5.48xlarge for 32B+ models

### Auto-scaling
```bash
# Enable auto-scaling
emd auto-scale --model-id Qwen2-VL-7B-Instruct \
               --min-capacity 1 \
               --max-capacity 5 \
               --target-utilization 70
```

### Scheduled Scaling
```bash
# Scale down during off-hours
emd schedule --model-id Qwen2-VL-7B-Instruct \
             --scale-down "0 22 * * *" \
             --scale-up "0 8 * * *"
```

## Production Considerations

### High Availability
```bash
# Deploy across multiple AZs
emd deploy --model-id Qwen2-VL-7B-Instruct \
           --instance-type g5.12xlarge \
           --multi-az \
           --instance-count 2
```

### Security
```bash
# Enable VPC endpoints
emd deploy --model-id Qwen2-VL-7B-Instruct \
           --vpc-config subnet-12345,sg-67890

# Enable encryption
emd deploy --model-id Qwen2-VL-7B-Instruct \
           --kms-key-id arn:aws:kms:region:account:key/key-id
```

### Monitoring
```bash
# Enable CloudWatch metrics
emd monitor --model-id Qwen2-VL-7B-Instruct \
            --enable-metrics \
            --log-level INFO
```

## Integration with Platform

Once deployed, models are automatically available in the platform:

1. **Backend Detection**: The platform automatically detects deployed models
2. **Client Initialization**: Both OpenAI and SageMaker clients are configured
3. **Error Handling**: Graceful fallback if deployment fails
4. **Logging**: Comprehensive deployment status logging

### Verification

Test deployment through the platform:

```bash
# Check model availability
curl -X GET http://localhost:5000/api/emd/status

# Test inference
curl -X POST http://localhost:5000/api/emd/qwen2-vl-7b \
  -H "Content-Type: application/json" \
  -d '{"text": "test", "frames": [], "mediaType": "image"}'
```

---

For additional help, check the [EMD documentation](https://docs.emd.ai) or contact support.