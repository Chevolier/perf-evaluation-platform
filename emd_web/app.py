from fastapi import FastAPI, Request
from typing import Optional
from enum import Enum
import uvicorn
import json
from emd.sdk.deploy import deploy
from emd.sdk.status import get_model_status
from emd.sdk.destroy import destroy



# Define enums and constants
class FrameworkType(str, Enum):
    FASTAPI = "fastapi"
    FLASK = "flask"
    DJANGO = "django"

MODEL_DEFAULT_TAG = "dev"

# Create FastAPI app
app = FastAPI(title="EMD Web API", version="1.0.0")

@app.get("/ping")
async def ping():
    return {"success": True, "message": "EMD Web API is running"}

@app.post("/emd_deploy")
async def emd_deploy(request: Request) -> dict:
    """
    Deploy a model with specified configuration
    """

    body = await request.body()
    data = json.loads(body.decode('utf-8'))

    # Extract parameters with defaults
    model_id = data.get("model_id")
    instance_type = data.get("instance_type")
    engine_type = data.get("engine_type")
    service_type = data.get("service_type")
    framework_type = data.get("framework_type", FrameworkType.FASTAPI)
    model_tag = data.get("model_tag", MODEL_DEFAULT_TAG)
    region = data.get("region")
    model_stack_name = data.get("model_stack_name")
    extra_params = data.get("extra_params")
    env_stack_on_failure = data.get("env_stack_on_failure", "ROLLBACK")
    force_env_stack_update = data.get("force_env_stack_update", False)
    waiting_until_deploy_complete = False
    dockerfile_local_path = None

    result = deploy(
        model_id=model_id,
        instance_type=instance_type,
        engine_type=engine_type,
        service_type=service_type,
        waiting_until_deploy_complete=False
    )

    # Implementation logic here
    deployment_config = {
        "model_id": model_id,
        "instance_type": instance_type,
        "engine_type": engine_type,
        "service_type": service_type,
        "framework_type": framework_type,
        "model_tag": model_tag,
        "region": region,
        "model_stack_name": model_stack_name,
        "extra_params": extra_params,
        "env_stack_on_failure": env_stack_on_failure,
        "force_env_stack_update": force_env_stack_update,
        "waiting_until_deploy_complete": waiting_until_deploy_complete,
        "dockerfile_local_path": dockerfile_local_path,
    }
    
    return {
        "success": True,
        "message": "Deployment initiated successfully",
        "deployment_config": deployment_config
    }


@app.post("/emd_status")
async def emd_status(request: Request) -> dict:
    """
    Retrieve a model status
    """

    body = await request.body()
    data = json.loads(body.decode('utf-8'))

    # Extract parameters with defaults
    model_id = data.get("model_id")
    model_tag = data.get("model_tag", MODEL_DEFAULT_TAG)

    status = get_model_status(model_id,model_tag)
    return status

@app.post("/emd_destroy")
async def emd_destroy(request: Request) -> dict:
    """
    Destroy a model
    """

    body = await request.body()
    data = json.loads(body.decode('utf-8'))
    model_id = data.get("model_id")
    model_tag = data.get("model_tag", MODEL_DEFAULT_TAG)

    destroy(model_id=model_id,model_tag=model_tag,waiting_until_complete=False)

    return {"success": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
