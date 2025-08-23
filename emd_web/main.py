from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
from enum import Enum
import uvicorn
import json
import os
from emd.sdk.deploy import deploy
from emd.sdk.status import get_model_status
from emd.sdk.destroy import destroy
from emd.models import Model
from typing_extensions import Annotated
import typer

# Define enums and constants
class FrameworkType(str, Enum):
    FASTAPI = "fastapi"
    FLASK = "flask"
    DJANGO = "django"

MODEL_DEFAULT_TAG = "dev"

# Create FastAPI app
app = FastAPI(title="EMD Web API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境中应该指定具体域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
)

@app.get("/", response_class=HTMLResponse)
async def get_test_page():
    """
    Serve the API test page
    """
    try:
        # Get the directory where main.py is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_file_path = os.path.join(current_dir, "api_test.html")
        
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>测试页面未找到</h1><p>请确保 api_test.html 文件存在于同一目录中。</p>",
            status_code=404
        )

@app.get("/test", response_class=HTMLResponse)
async def get_test_page_alias():
    """
    Alternative route for the API test page
    """
    return await get_test_page()

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


    required_params = ["model_id", "instance_type", "engine_type", "service_type"]
    missing_params = [param for param in required_params if not data.get(param)]
    if missing_params:
        return {"success": False, "error": f"Missing required parameters: {', '.join(missing_params)}"}


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

    try:
        result = deploy(
            model_id=model_id,
            model_tag=model_tag,
            instance_type=instance_type,
            engine_type=engine_type,
            service_type=service_type,
            waiting_until_deploy_complete=False
        )
    except Exception as e:
        return {"success": False, "error": f"Deployment failed: {str(e)}"}

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

@app.post("/emd_models")
async def emd_list_models() :

    ret = get_model_status(model_id=None, model_tag=None)
    inprogress = ret['inprogress']
    completed = ret['completed']

    #print(inprogress)
    data = []
    cli_messages = []  # Store CLI messages for display after the table

    # Process all in-progress executions (now includes enhanced pipeline-stack logic)
    for d in inprogress:
        if d['status'] == "Stopped":
            continue

        # Use enhanced status if available, otherwise fall back to original logic
        if d.get('enhanced_status'):
            display_status = d['enhanced_status']
        else:
            display_status = f"{d['status']} ({d['stage_name']})" if d.get('stage_name') else d['status']

        data.append({
            "model_id": d['model_id'],
            "model_tag": d['model_tag'],
            "status": display_status,
            "service_type": d.get('service_type', ''),
            "instance_type": d.get('instance_type', ''),
            "create_time": d.get('create_time', ''),
            "outputs": d.get('outputs', ''),  # Use .get() to handle missing outputs field
        })

        # Collect CLI messages for this model
        if d.get('cli_message'):
            model_name = f"{d['model_id']}/{d['model_tag']}"
            cli_messages.append({
                'model_name': model_name,
                'message_type': d['cli_message'],
                'stack_name': d.get('stack_name', '')
            })

    # Process completed models
    for d in completed:
        data.append({
            "model_id": d['model_id'],
            "model_tag": d['model_tag'],
            "status": d['stack_status'],
            "service_type": d['service_type'],
            "instance_type": d['instance_type'],
            "create_time": d['create_time'],
            "outputs": d['outputs'],
        })
    if not data:
        return []
    return data


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



@app.post("/emd_supported_models")
async def list_supported_models(request: Request):

    detail=False
    # console.print("[bold blue]Retrieving models...[/bold blue]")
    support_models = Model.get_supported_models(detail=detail)
    #if model_id:
    #    support_models = [model for _model_id,model in support_models.items() if _model_id == model_id]
    #r = json.dumps(support_models,indent=2,ensure_ascii=False)
    #print(f"{r}")
    #print(support_models)
    return support_models


@app.post("/emd_details")
async def get_model_details(request: Request):

    body = await request.body()
    data = json.loads(body.decode('utf-8'))
    model_id = data.get("model_id")
    detail = data.get("detail",False)
    support_models = Model.get_supported_models(detail=detail)
    model_details = [model for _model_id,model in support_models.items() if _model_id == model_id]
    #r = json.dumps(support_models,indent=2,ensure_ascii=False)
    #print(f"{r}")
    #print(support_models)
    return model_details

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
