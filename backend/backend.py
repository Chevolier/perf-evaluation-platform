# 标准库
import base64
import hashlib
import io
import json
import logging
import os
import queue
import re
import subprocess
import tempfile
import threading
import time
import traceback
from datetime import datetime

# 第三方库 - Web相关
from flask import Flask, request, jsonify, Response, make_response
from flask_cors import CORS
import requests

# 第三方库 - AWS相关
import boto3

# 第三方库 - 数据处理
from PIL import Image

# 第三方库 - AI/ML相关
from openai import OpenAI
from emd.sdk.clients.sagemaker_client import SageMakerClient
from emd.sdk.status import get_model_status
from emd.sdk.bootstrap import bootstrap
from emd.sdk.deploy import deploy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)
CORS(app)

# 配置日志
logging.basicConfig(
    filename='backend.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

bedrock_client = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-west-2'
)

deployment_threads = {}
# EMD client configurations - Updated with tested models
EMD_MODELS = {
    'qwen2-vl-7b': {
        "model_path": 'Qwen2-VL-7B-Instruct',
        "name": "Qwen2-VL-7B",
        "description": "通义千问视觉语言模型，7B参数",
    },
    'qwen2.5-vl-7b': {
        "model_path": 'Qwen2.5-VL-7B-Instruct',
        "name": "Qwen2.5-VL-7B",
        "description": "通义千问视觉语言模型，7B参数",
    },
    'qwen2.5-vl-32b': {
        "model_path": 'Qwen2.5-VL-32B-Instruct',
        "name": "Qwen2.5-VL-32B",
        "description": "通义千问视觉语言模型，32B参数",
    },
    'qwen2.5-0.5b': {
        "model_path": 'Qwen2.5-0.5B-Instruct',
        "name": "Qwen2.5-0.5B",
        "description": "轻量级文本模型，适合快速推理",
    },
    'gemma-3-4b': {
        "model_path": 'gemma-3-4b-it',
        "name": "Gemma-3-4B",
        "description": "Google开源语言模型",
    },
    'ui-tars-1.5-7b': {
        "model_path": 'UI-TARS-1.5-7B',
        "name": "UI-TARS-1.5-7B",
        "description": "用户界面理解专用模型",
    },
    'qwen3-0.6b': {
        "model_path": 'Qwen3-0.6B',
        "name": "Qwen3-0.6B",
        "description": "最新Qwen3模型，0.6B参数，高效轻量",
    },
    'qwen3-8b': {
        "model_path": 'Qwen3-8B',
        "name": "Qwen3-8B",
        "description": "最新Qwen3模型，8B参数，强大性能",
    }
}

BEDROCK_MODELS = {
    'claude4': {
        "name": "Claude 4",
        "description": "最新的Claude模型，具备强大的推理能力",
    }, 
    'claude35': {
        "name": "Claude 3.5 Sonnet",
        "description": "平衡性能与速度的高效模型",
    },
    'nova': {
        "name": "Amazon Nova Pro",
        "description": "AWS原生多模态大模型",
    }
}

ALL_MODELS = {
    "bedrock": BEDROCK_MODELS,
    "emd": EMD_MODELS,
}

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def init_emd_env(region="us-west-2"):
    """Initialize EMD environment by setting region and bootstrapping."""
    # os.environ["AWS_DEFAULT_REGION"] = region
    # subprocess.run(["emd", "bootstrap"], check=True, env=os.environ)
    # logging.info(f"EMD environment initialized in region {region}")
    bootstrap()


def generate_short_tag(model_name: str):
    """
    生成一个简短但唯一的 tag：
    - model_name 保留前10位的安全字符（只保留字母和数字）
    - 后缀添加时间和哈希
    """
    # 保留字母和数字
    safe_prefix = ''.join(c for c in model_name if c.isalnum())[:10].lower()
    
    # 当前时间戳（如08071345）
    time_part = datetime.now().strftime("%m%d%H%M")

    # 哈希短码（避免重名）：取 model_name + 当前时间 的 SHA1 前6位
    hash_suffix = hashlib.sha1(f"{model_name}{time_part}".encode()).hexdigest()[:6]

    tag = f"{safe_prefix}-{time_part}-{hash_suffix}"
    return tag


def get_current_models():
    print(f"get_current_models")
    """通过 emd status 提取 Base URL，并请求 /models 接口，返回 CREATE_COMPLETE 的模型列表"""
    try:
        # 获取 emd status 输出并提取 Base URL
        # result = subprocess.run(
        #     ["emd", "status"],
        #     capture_output=True,
        #     text=True,
        #     check=True,
        #     env=os.environ
        # )
        # output = result.stdout
        # match = re.search(r"http://[^\s]+\.elb\.amazonaws\.com/v1", output)
        # if not match:
        #     logging.error("❌ 无法在 emd status 输出中找到 Base URL")
        #     return {}
        # base_url = match.group(0)
        # logging.info(f"🌐 检测到 EMD Base URL: {base_url}")

        # # 请求 /models 接口获取所有模型
        # response = requests.get(f"{base_url}/models")
        # response.raise_for_status()
        # models_data = response.json().get("data", [])
        # print(f"models_data:{models_data}")
        # 过滤状态为 CREATE_COMPLETE 的模型，并构造返回值
        # 创建反向映射：完整模型名 -> 简化键名
        status = get_model_status()
        print("status", status)
        logging.info(f"[DEBUG] EMD SDK get_model_status返回: {status}")
        reverse_mapping = {v["model_path"]: k for k, v in EMD_MODELS.items()}
        print("reverse_mapping", reverse_mapping)
        
        deployed = {}
        inprogress = {}
        failed = {}

        for model in status["completed"]:
            model_id = model.get("model_id")
            model_tag = model.get("model_tag")
            stack_status = model.get("stack_status")
            
            if model_id in reverse_mapping:
                simple_key = reverse_mapping[model_id]
                if stack_status is not None and "CREATE_COMPLETE" in stack_status:
                    deployed[simple_key] = {
                        "tag": model_tag,
                        "full_name": model_id
                    }
                else:
                    failed[simple_key] = {
                        "tag": model_tag,
                        "full_name": model_id
                    }
        
        for model in status["inprogress"]:
            model_id = model.get("model_id")
            model_tag = model.get("model_tag")
            stack_status = model.get("stack_status")
            model_status = model.get("status")
            execution_info = model.get("execution_info", {})
            execution_status = execution_info.get("status")
            
            if model_id in reverse_mapping:
                simple_key = reverse_mapping[model_id]
                # Check if the inprogress model has actually failed
                is_failed = False
                
                # Check various failure indicators
                if stack_status is not None and any(fail_status in stack_status for fail_status in ["ROLLBACK_COMPLETE", "CREATE_FAILED", "DELETE_FAILED", "ROLLBACK_FAILED"]):
                    is_failed = True
                elif model_status == "Failed":
                    is_failed = True
                elif execution_status == "Failed":
                    is_failed = True
                
                if is_failed:
                    failed[simple_key] = {
                        "tag": model_tag,
                        "full_name": model_id
                    }
                else:
                    inprogress[simple_key] = {
                        "tag": model_tag,
                        "full_name": model_id
                    }
        
        # Also check if there's a "failed" category in the status
        if "failed" in status:
            for model in status["failed"]:
                model_id = model.get("model_id")
                model_tag = model.get("model_tag")
                
                if model_id in reverse_mapping:
                    simple_key = reverse_mapping[model_id]
                    failed[simple_key] = {
                        "tag": model_tag,
                        "full_name": model_id
                    }
        logging.info(f"✅ 当前部署的模型: {deployed}")
        logging.info(f"✅ 当前正在部署的模型: {inprogress}")
        logging.info(f"✅ 当前部署失败的模型: {failed}")

        return {
            "inprogress": inprogress,
            "deployed": deployed,
            "failed": failed,
        }

    except subprocess.CalledProcessError as e:
        logging.error(f"❌ 获取 emd status 失败: {e}")
        return {}
    except Exception as e:
        logging.error(f"❌ 处理模型列表失败: {e}")
        return {}



def deploy_model_if_not_exist(model_name, instance_type="g5.12xlarge", engine_type="vllm"):
    """Deploy the model if it does not exist."""
    deployed = get_current_models()
    if model_name in deployed:
        logging.info(f"✅ {model_name} is already deployed with tag: {deployed[model_name]['tag']}")
        return deployed[model_name]["tag"]

    tag = generate_short_tag(model_name)
    deploy_cmd = [
        "emd", "deploy",
        "--model-id", model_name,
        "--instance-type", instance_type,
        "--engine-type", engine_type,
        "--service-type", "sagemaker_realtime",
        "--skip-confirm",
        "--model-tag", tag,
         "--extra-params", "{}"
    ]
    subprocess.run(deploy_cmd, check=True, env=os.environ)
    logging.info(f"🚀 Deployment initiated for {model_name} with tag={tag}")
    return tag

def check_model_deployment(model_name):
    """check if the model to reach CREATE_COMPLETE status."""
    logging.info(f"⏳ Waiting for {model_name} deployment to complete...")
    models = get_current_models()
    if model_name in models:
        logging.info(f"🎉 {model_name} deployed successfully with tag: {models[model_name]['tag']}")
        return True
    logging.info(f"🔄 {model_name} not yet deployed, please wait")
    return False

def wait_for_model_deployment(model_name, timeout=1800, check_interval=60):
    """Wait for the model to reach CREATE_COMPLETE status."""
    logging.info(f"⏳ Waiting for {model_name} deployment to complete...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        models = get_current_models()
        if model_name in models:
            logging.info(f"🎉 {model_name} deployed successfully with tag: {models[model_name]['tag']}")
            return True
        logging.info(f"🔄 {model_name} not yet deployed, checking again in {check_interval}s...")
        time.sleep(check_interval)
    logging.error(f"❌ Timeout reached. {model_name} deployment did not complete within {timeout}s.")
    return False


# Default model tag - Update this for your deployment
DEFAULT_EMD_TAG = "test200"

# Dynamic model management - use functions instead of hardcoded dict

# Cache for EMD base URL to avoid repeated calls
_emd_base_url_cache = {"url": None, "timestamp": 0, "cache_duration": 300}  # 5 minutes cache

def set_emd_tag(tag):
    """Update the default EMD tag for all models"""
    global DEFAULT_EMD_TAG
    DEFAULT_EMD_TAG = tag
    logging.info(f"Updated EMD tag to: {tag}")

def get_emd_info():
    """Get current EMD configuration info"""
    return {
        "models": EMD_MODELS,
        "default_tag": DEFAULT_EMD_TAG,
        "base_url": get_emd_base_url()
    }

def get_emd_base_url(model_id, tag):
    status = get_model_status(model_id, tag)
    completed_status = status.get("completed")
    print("completed_status")
    if completed_status is None:
        return None
    outputs = completed_status[0].get("outputs")
    if outputs is None:
        return None
    try:
        outputs = json.loads(outputs.replace("'", "\""))
        BaseURL = outputs.get("BaseURL")
        return BaseURL
    except Exception as e:
        print("Error:", e)
        return None
    

def create_emd_openai_client(model_id, tag):
    """Create OpenAI client for EMD endpoints"""
    base_url = get_emd_base_url(model_id, tag)
    if base_url:
        return OpenAI(api_key="", base_url=f"{base_url}/v1")
    return None

def encode_image_for_emd(image_base64):
    """Encode image for EMD inference"""
    return image_base64

def get_account_id():
    """动态获取当前AWS账户ID"""
    try:
        sts_client = boto3.client('sts')
        identity = sts_client.get_caller_identity()
        return identity['Account']
    except Exception as e:
        logging.warning(f"无法获取账户ID，使用默认值: {e}")
        return "651433607849"  # 更新的账户ID

def build_inference_profile_arn(model_type, account_id=None, region='us-west-2'):
    """构建推理配置文件ARN或返回标准模型ID"""
    # 使用标准模型ID避免跨账户权限问题
    model_mappings = {
        'claude4': 'anthropic.claude-3-5-sonnet-20241022-v2:0',  # 使用标准Claude 3.5模型
        'nova': 'amazon.nova-pro-v1:0'
    }
    
    if model_type in model_mappings:
        return model_mappings[model_type]
    else:
        return model_type

def extract_frames_from_video(video_base64, num_frames=8):
    """从base64视频中提取关键帧"""
    try:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 保存base64视频到临时文件
            video_path = os.path.join(temp_dir, "input_video.mp4")
            with open(video_path, "wb") as f:
                f.write(base64.b64decode(video_base64))
            
            # 获取视频时长
            try:
                duration_cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '{video_path}'"
                duration = float(subprocess.check_output(duration_cmd, shell=True, env=os.environ.copy()).decode().strip())
            except Exception as e:
                logging.warning(f"无法获取视频时长，使用默认值: {e}")
                duration = 10.0  # 默认10秒
            
            # 创建输出目录
            frames_dir = os.path.join(temp_dir, "frames")
            os.makedirs(frames_dir, exist_ok=True)
            
            # 计算帧间隔
            interval = max(duration / num_frames, 0.5)  # 最小间隔0.5秒
            
            frame_base64_list = []
            
            # 提取关键帧
            for i in range(num_frames):
                timestamp = min(i * interval, duration - 0.1)  # 确保不超过视频长度
                frame_path = os.path.join(frames_dir, f"frame_{i+1:02d}.jpg")
                
                # 使用ffmpeg提取帧
                ffmpeg_cmd = f"ffmpeg -ss {timestamp} -i '{video_path}' -frames:v 1 -q:v 2 '{frame_path}' -y -loglevel quiet"
                
                try:
                    subprocess.run(ffmpeg_cmd, shell=True, check=True, env=os.environ.copy())
                    
                    # 将帧转换为base64
                    if os.path.exists(frame_path):
                        with Image.open(frame_path) as img:
                            # 调整图片大小以节省token
                            img.thumbnail((800, 600), Image.Resampling.LANCZOS)
                            buffer = io.BytesIO()
                            img.save(buffer, format="JPEG", quality=85)
                            frame_base64 = base64.b64encode(buffer.getvalue()).decode()
                            frame_base64_list.append(frame_base64)
                            
                except subprocess.CalledProcessError as e:
                    logging.warning(f"提取第{i+1}帧失败: {e}")
                    continue
            
            logging.info(f"成功提取了 {len(frame_base64_list)} 个关键帧")
            return frame_base64_list
            
    except Exception as e:
        logging.error(f"视频切帧处理失败: {e}")
        return []

def enhance_prompt_for_video(original_prompt, num_frames):
    """为视频分析增强提示词"""
    video_context = f"These are {num_frames} keyframes extracted from a video at regular intervals. Please analyze these sequential frames to understand the video content and answer the following question: "
    return video_context + original_prompt

def process_model_async(model_name, endpoint_func, data, result_queue):
    """异步处理单个模型的推理"""
    start_time = time.time()
    try:
        result = endpoint_func(data)
        end_time = time.time()
        processing_time = f"{end_time - start_time:.2f}s"
        
        result_queue.put({
            'model': model_name,
            'status': 'success',
            'result': result,
            'metadata': {
                'processingTime': processing_time,
                'startTime': start_time,
                'endTime': end_time
            }
        })
    except Exception as e:
        end_time = time.time()
        processing_time = f"{end_time - start_time:.2f}s"
        
        result_queue.put({
            'model': model_name,
            'status': 'error',
            'error': str(e),
            'metadata': {
                'processingTime': processing_time,
                'startTime': start_time,
                'endTime': end_time
            }
        })


@app.route('/api/emd/init', methods=['POST'])
def api_init_emd():
    region = request.json.get('region', 'us-west-2')
    try:
        init_emd_env(region=region)
        return jsonify({"status": "success", "region": region})
    except Exception as e:
        logging.error(f"EMD Init Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/api/emd/current-models', methods=['GET'])
def api_get_current_models():
    try:
        models = get_current_models()
        return jsonify({"status": "success", "deployed_models": models})
    except Exception as e:
        logging.error(f"Get Current Models Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    
@app.route('/api/emd/check-deployment', methods=['GET'])
def api_check_model_deployment():
    model_name = request.args.get('model_name')
    if not model_name:
        return jsonify({"status": "error", "message": "model_name is required"}), 400

    try:
        if check_model_deployment(model_name):
            return jsonify({"status": "deployed", "model_name": model_name})
        else:
            return jsonify({"status": "deploying", "model_name": model_name, "message": "模型仍在部署中，请稍后再试。"})
    except Exception as e:
        logging.error(f"Check Model Deployment Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
    
@app.route('/api/multi-inference', methods=['POST'])
def multi_inference():
    """同时调用多个模型进行推理，支持流式返回结果"""
    data = request.json
    models = data.get('models', BEDROCK_MODELS)
    
    def generate():
        result_queue = queue.Queue()
        threads = []
        
        # 创建线程处理每个模型
        for model in models:
            if model == 'claude4':
                thread = threading.Thread(
                    target=process_model_async,
                    args=(model, lambda d: call_claude4_internal(d), data, result_queue)
                )
            elif model == 'claude35':
                thread = threading.Thread(
                    target=process_model_async,
                    args=(model, lambda d: call_claude35_internal(d), data, result_queue)
                )
            elif model == 'nova':
                thread = threading.Thread(
                    target=process_model_async,
                    args=(model, lambda d: call_nova_internal(d), data, result_queue)
                )
            elif model in EMD_MODELS:
                # EMD model - check if deployed first
                deployed_models = get_current_models()["deployed"]
                print("[debug] deployed_models", deployed_models, model)
                if model in deployed_models:
                    thread = threading.Thread(
                        target=process_model_async,
                        args=(model, lambda d: call_emd_model_internal(d, model), data, result_queue)
                    )
                else:
                    # Model not deployed, return waiting message
                    result_queue.put({
                        'model': model,
                        'status': 'not_deployed',
                        'message': f'模型 {model} 正在部署中或尚未部署，请稍后再试。'
                    })
                    continue
            else:
                continue
                
            threads.append(thread)
            thread.start()
        
        # 等待结果并流式返回
        completed = 0
        total_models = len(threads)
        
        while completed < total_models:
            try:
                result = result_queue.get(timeout=1)
                completed += 1
                
                # 发送结果
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                
            except queue.Empty:
                # 发送心跳
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"
    
    return Response(
        generate(),
        mimetype='text/plain',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )

def call_claude4_internal(data):
    """Claude4推理的内部函数"""
    start_time = time.time()
    text = data.get('text', '')
    frames = data.get('frames', [])
    media_type = data.get('mediaType', 'image')
    max_tokens = data.get('max_tokens', 1024)
    temperature = data.get('temperature', 0.1)
    
    log_entry = {
        'time': datetime.now().isoformat(),
        'request': {'text': text, 'frames_count': len(frames), 'media_type': media_type, 'max_tokens': max_tokens, 'temperature': temperature}
    }
    
    try:
        content = [{"type": "text", "text": text}]
        
        # 处理视频和图片
        if media_type == 'video':
            # 处理视频：提取关键帧
            if len(frames) > 0:
                video_base64 = frames[0]  # 假设只有一个视频文件
                logging.info("开始从视频提取关键帧...")
                keyframes = extract_frames_from_video(video_base64, num_frames=8)
                
                if keyframes:
                    # 增强提示词以说明这些是视频关键帧
                    enhanced_text = enhance_prompt_for_video(text, len(keyframes))
                    content = [{"type": "text", "text": enhanced_text}]
                    
                    # 添加关键帧作为图片
                    for frame_base64 in keyframes:
                        content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": frame_base64
                            }
                        })
                    logging.info(f"成功添加了 {len(keyframes)} 个关键帧到请求中")
                else:
                    return jsonify({"error": "Failed to extract frames from video. Please check the video format."}), 400
            else:
                return jsonify({"error": "No video data received."}), 400
        else:  # 处理图片
            for img_base64 in frames:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_base64
                    }
                })
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ]
        }
        log_entry['bedrock_request'] = {k: v if k != 'messages' else 'omitted' for k, v in request_body.items()}
        # 动态构建Claude 4推理配置文件ARN
        model_id = build_inference_profile_arn('claude4')
        logging.info(f"Using Claude 4 model ID: {model_id}")
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        response_body = json.loads(response['body'].read())
        end_time = time.time()
        processing_time = f"{end_time - start_time:.2f}s"
        
        # 添加处理时间元数据
        response_with_metadata = {
            **response_body,
            'metadata': {
                'processingTime': processing_time,
                'startTime': start_time,
                'endTime': end_time
            }
        }
        
        log_entry['response'] = response_body
        log_entry['processing_time'] = processing_time
        logging.info(json.dumps(log_entry, ensure_ascii=False))
        return response_with_metadata
    except Exception as e:
        end_time = time.time()
        processing_time = f"{end_time - start_time:.2f}s"
        log_entry['error'] = str(e)
        log_entry['processing_time'] = processing_time
        logging.error(json.dumps(log_entry, ensure_ascii=False))
        raise Exception(str(e))

@app.route('/api/claude4', methods=['POST'])
def call_claude4():
    try:
        result = call_claude4_internal(request.json)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def call_claude35_internal(data):
    """Claude3.5推理的内部函数"""
    start_time = time.time()
    text = data.get('text', '')
    frames = data.get('frames', [])
    media_type = data.get('mediaType', 'image')
    max_tokens = data.get('max_tokens', 1024)
    temperature = data.get('temperature', 0.1)
    
    log_entry = {
        'time': datetime.now().isoformat(),
        'request': {'text': text, 'frames_count': len(frames), 'media_type': media_type, 'max_tokens': max_tokens, 'temperature': temperature}
    }
    
    try:
        content = [{"type": "text", "text": text}]
        
        # 处理视频和图片
        if media_type == 'video':
            # 处理视频：提取关键帧
            if len(frames) > 0:
                video_base64 = frames[0]  # 假设只有一个视频文件
                logging.info("开始从视频提取关键帧...")
                keyframes = extract_frames_from_video(video_base64, num_frames=8)
                
                if keyframes:
                    # 增强提示词以说明这些是视频关键帧
                    enhanced_text = enhance_prompt_for_video(text, len(keyframes))
                    content = [{"type": "text", "text": enhanced_text}]
                    
                    # 添加关键帧作为图片
                    for frame_base64 in keyframes:
                        content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": frame_base64
                            }
                        })
                    logging.info(f"成功添加了 {len(keyframes)} 个关键帧到请求中")
                else:
                    return jsonify({"error": "Failed to extract frames from video. Please check the video format."}), 400
            else:
                return jsonify({"error": "No video data received."}), 400
        else:  # 处理图片
            for img_base64 in frames:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_base64
                    }
                })
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ]
        }
        log_entry['bedrock_request'] = {k: v if k != 'messages' else 'omitted' for k, v in request_body.items()}
        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps(request_body)
        )
        response_body = json.loads(response['body'].read())
        end_time = time.time()
        processing_time = f"{end_time - start_time:.2f}s"
        
        # 添加处理时间元数据
        response_with_metadata = {
            **response_body,
            'metadata': {
                'processingTime': processing_time,
                'startTime': start_time,
                'endTime': end_time
            }
        }
        
        log_entry['response'] = response_body
        log_entry['processing_time'] = processing_time
        logging.info(json.dumps(log_entry, ensure_ascii=False))
        return response_with_metadata
    except Exception as e:
        end_time = time.time()
        processing_time = f"{end_time - start_time:.2f}s"
        log_entry['error'] = str(e)
        log_entry['processing_time'] = processing_time
        logging.error(json.dumps(log_entry, ensure_ascii=False))
        raise Exception(str(e))

@app.route('/api/claude35', methods=['POST'])
def call_claude35():
    try:
        result = call_claude35_internal(request.json)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def call_nova_internal(data):
    """Nova推理的内部函数"""
    start_time = time.time()
    text = data.get('text', '')
    frames = data.get('frames', [])
    media_type = data.get('mediaType', 'image')
    max_tokens = data.get('max_tokens', 1024)
    temperature = data.get('temperature', 0.1)
    
    log_entry = {
        'time': datetime.now().isoformat(),
        'request': {'text': text, 'frames_count': len(frames), 'media_type': media_type, 'max_tokens': max_tokens, 'temperature': temperature}
    }
    
    try:
        import base64
        # Nova Pro model supports both images and videos
        if media_type == 'image':
            content = [{"text": text}]
            for img_base64 in frames:
                content.append({
                    "image": {
                        "format": "jpeg",
                        "source": {"bytes": img_base64}
                    }
                })
        elif media_type == 'video':
            # 处理视频：提取关键帧并转换为图片格式
            if len(frames) > 0:
                video_base64 = frames[0]  # 假设只有一个视频文件
                logging.info("Nova开始从视频提取关键帧...")
                keyframes = extract_frames_from_video(video_base64, num_frames=8)
                
                if keyframes:
                    # 增强提示词以说明这些是视频关键帧
                    enhanced_text = enhance_prompt_for_video(text, len(keyframes))
                    content = [{"text": enhanced_text}]
                    
                    # 添加关键帧作为图片
                    for frame_base64 in keyframes:
                        content.append({
                            "image": {
                                "format": "jpeg",
                                "source": {"bytes": frame_base64}
                            }
                        })
                    logging.info(f"Nova成功添加了 {len(keyframes)} 个关键帧到请求中")
                else:
                    raise Exception("Failed to extract frames from video for Nova processing.")
            else:
                raise Exception("No video data received for Nova.")
        else:
            raise Exception("Unsupported media type")
        
        request_body = {
            "schemaVersion": "messages-v1",
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "inferenceConfig": {
                "max_new_tokens": max_tokens,
                "temperature": temperature
            }
        }
        
        log_entry['bedrock_request'] = {k: v if k != 'messages' else 'omitted' for k, v in request_body.items()}
        
        # 动态构建Nova推理配置文件ARN
        model_id = build_inference_profile_arn('nova')
        logging.info(f"Using Nova model ID: {model_id}")
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        end_time = time.time()
        processing_time = f"{end_time - start_time:.2f}s"
        
        # 添加处理时间元数据
        response_with_metadata = {
            **response_body,
            'metadata': {
                'processingTime': processing_time,
                'startTime': start_time,
                'endTime': end_time
            }
        }
        
        log_entry['response'] = response_body
        log_entry['processing_time'] = processing_time
        logging.info(json.dumps(log_entry, ensure_ascii=False))
        return response_with_metadata
        
    except Exception as e:
        end_time = time.time()
        processing_time = f"{end_time - start_time:.2f}s"
        log_entry['error'] = str(e)
        log_entry['processing_time'] = processing_time
        logging.error(json.dumps(log_entry, ensure_ascii=False))
        raise Exception(str(e))

@app.route('/api/nova', methods=['POST'])
def call_nova():
    try:
        # Convert media to frames format for internal function
        data = request.json.copy()
        if 'media' in data:
            data['frames'] = data['media']
        result = call_nova_internal(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def call_emd_model_internal(data, model_key):
    """EMD model inference internal function"""
    start_time = time.time()
    text = data.get('text', '')
    frames = data.get('frames', [])
    media_type = data.get('mediaType', 'image')
    max_tokens = data.get('max_tokens', 1024)
    temperature = data.get('temperature', 0.1)
    
    if model_key not in EMD_MODELS:
        raise Exception(f"Unsupported EMD model: {model_key}")
    
    # Check if model is actually deployed using dynamic function
    deployed_models = get_current_models()["deployed"]
    if model_key not in deployed_models:
        available_models = list(deployed_models.keys())
        raise Exception(f"Model {model_key} is not currently deployed. Available models: {available_models}. Please deploy this model first.")
    
    model_id = EMD_MODELS[model_key]["model_path"]
    deployed_tag = deployed_models[model_key]['tag']
    
    log_entry = {
        'time': datetime.now().isoformat(),
        'request': {'text': text, 'frames_count': len(frames), 'media_type': media_type, 'max_tokens': max_tokens, 'temperature': temperature, 'model': model_id}
    }
    
    try:
        logging.info(f"🚀 Starting EMD inference for model {model_id}")
        logging.info(f"✅ Using deployed model {model_key} with tag {deployed_tag}")
        
        # Update the default tag to the deployed one
        # original_tag = DEFAULT_EMD_TAG
        # set_emd_tag(deployed_tag)
        
        # First check deployment status
        # deployment_info = deployment_status.get(model_key)
        # if deployment_info:
        #     if deployment_info["status"] == "deploying":
        #         error_msg = f"模型 {model_key} 正在部署中，请稍后再试。部署状态: {deployment_info['message']}"
        #         raise Exception(error_msg)
        #     elif deployment_info["status"] == "failed":
        #         # For failed deployments, use the known deployed model tag
        #         logging.warning(f"⚠️ New deployment failed for {model_key}, using existing deployment with tag {deployed_tag}")
        #     elif deployment_info["status"] == "deployed":
        #         # Use the newly deployed model's tag
        #         newly_deployed_tag = deployment_info["tag"]
        #         logging.info(f"✅ Using newly deployed model {model_key} with tag {newly_deployed_tag}")
        #         set_emd_tag(newly_deployed_tag)
        #         deployed_tag = newly_deployed_tag
        
        # Try OpenAI client first (API endpoint)
        logging.info(f"🔍 Checking EMD OpenAI client availability...")
        # client = OpenAI(
        #     api_key="",
        #     base_url=base_url
        # )
        openai_client = create_emd_openai_client(model_id, deployed_tag)
        print("openai_client", openai_client)
        if openai_client:
            logging.info(f"✅ EMD OpenAI client available, proceeding with inference")
            result = call_emd_via_openai(openai_client, data, model_id, deployed_tag, model_key, log_entry)
            end_time = time.time()
            processing_time = f"{end_time - start_time:.2f}s"
            
            # 添加处理时间元数据
            if isinstance(result, dict):
                result['metadata'] = {
                    'processingTime': processing_time,
                    'startTime': start_time,
                    'endTime': end_time
                }
            return result
        
        # Fallback to SageMaker client
        # logging.info(f"🔍 Checking EMD SageMaker client availability...")
        # sagemaker_client = create_emd_sagemaker_client(model_id)
        # sagemaker_client = SageMakerClient(
        #     model_id=model_id,
        #     model_tag=deployed_tag
        # )
        # print("model_id", model_id, "deployed_tag", deployed_tag)
        # if sagemaker_client:
        #     logging.info(f"✅ EMD SageMaker client available, proceeding with inference")
        #     result = call_emd_via_sagemaker(sagemaker_client, data, model_id, model_key, log_entry)
        #     end_time = time.time()
        #     processing_time = f"{end_time - start_time:.2f}s"
            
        #     # 添加处理时间元数据
        #     if isinstance(result, dict):
        #         result['metadata'] = {
        #             'processingTime': processing_time,
        #             'startTime': start_time,
        #             'endTime': end_time
        #         }
        #     return result
        
        # No client available - provide helpful error message
        logging.error(f"❌ No EMD client available for {model_id}")
        error_msg = f"模型 {model_key} 的部署不可用。当前可用模型: {list(deployed_models.keys())}。"
        raise Exception(error_msg)
        
    except Exception as e:
        end_time = time.time()
        processing_time = f"{end_time - start_time:.2f}s"
        log_entry['error'] = str(e)
        log_entry['processing_time'] = processing_time
        logging.error(json.dumps(log_entry, ensure_ascii=False))
        raise Exception(str(e))

def call_emd_via_openai(client, data, model_id, tag, model_key, log_entry):
    """Call EMD model via OpenAI API - Updated with working pattern"""
    text = data.get('text', '')
    frames = data.get('frames', [])
    media_type = data.get('mediaType', 'image')
    max_tokens = data.get('max_tokens', 1024)
    temperature = data.get('temperature', 0.1)
    
    logging.info(f"🎯 Processing {media_type} input for EMD model {model_id}")
    logging.info(f"📊 Request details: text_len={len(text)}, frames={len(frames)}, type={media_type}")
    
    # For Qwen2.5-0.5B-Instruct, prioritize SageMaker client over OpenAI
    # if model_id == 'Qwen2.5-0.5B-Instruct':
    #     logging.info(f"🔄 Switching to SageMaker client for {model_id} (more reliable)")
    #     try:
    #         sagemaker_client = create_emd_sagemaker_client(model_id)
    #         if sagemaker_client:
    #             return call_emd_via_sagemaker(sagemaker_client, data, model_id, model_key, log_entry)
    #     except Exception as e:
    #         logging.warning(f"⚠️ SageMaker fallback failed, trying OpenAI: {e}")
    
    messages = []
    
    # Check if this is a text-only model (like Qwen2.5-0.5B-Instruct)
    if model_id == 'Qwen2.5-0.5B-Instruct':
        # Text-only model - just send the text prompt
        logging.info(f"📝 Processing text-only input for EMD model {model_id}")
        messages.append({
            "role": "user",
            "content": text
        })
    elif media_type == 'video':
        # Process video: extract keyframes
        if len(frames) > 0:
            video_base64 = frames[0]
            logging.info(f"📹 EMD {model_id} 开始从视频提取关键帧...")
            keyframes = extract_frames_from_video(video_base64, num_frames=8)
            
            if keyframes:
                enhanced_text = enhance_prompt_for_video(text, len(keyframes))
                content = [{"type": "text", "text": enhanced_text}]
                
                for frame_base64 in keyframes:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_base64}"
                        }
                    })
                
                messages.append({
                    "role": "user",
                    "content": content
                })
                logging.info(f"✅ EMD {model_id} 成功添加了 {len(keyframes)} 个关键帧到请求中")
            else:
                raise Exception("Failed to extract frames from video for EMD processing")
        else:
            raise Exception("No video data received for EMD")
    else:
        # Process images (for multimodal models)
        logging.info(f"🖼️ Processing {len(frames)} images for EMD model {model_id}")
        content = [{"type": "text", "text": text}]
        for img_base64 in frames:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_base64}"
                }
            })
        
        messages.append({
            "role": "user",
            "content": content
        })
    
    # Use the configured model tag
    model_endpoint = f"{model_id}/{tag}"
    logging.info(f"🔥 Calling EMD OpenAI API for {model_endpoint}...")
    logging.info(f"🌐 Using base URL: {client.base_url}")
    logging.info(f"📝 Message structure: {len(messages)} messages")
    
    try:
        # base_url = "http://EMD-EC-Publi-nOXevnWhCba1-203402465.us-west-2.elb.amazonaws.com/v1"

        # client = OpenAI(
        #     api_key="",
        #     base_url=base_url
        # )
        # 这部分目前有bug，如果从本地读入图片是可以正确预测的，但是从前端传入的图片似乎解析有问题
        # model_endpoint = "Qwen2-VL-7B-Instruct/dev"
        response = client.chat.completions.create(
            model=model_endpoint,
            messages=messages,
            # max_tokens=max_tokens,
            # temperature=temperature
        )

        # base_url = "http://EMD-EC-Publi-nOXevnWhCba1-203402465.us-west-2.elb.amazonaws.com/v1"

        # client = OpenAI(
        #     api_key="",
        #     base_url=base_url
        # )

        # image_path = "/home/ec2-user/efs_data/workspace/multimodal-platform/image.jpg"
        # base64_image = encode_image(image_path)
        # print('base64_image=', base64_image[:10])

        # response = client.chat.completions.create(
        #     model="Qwen2-VL-7B-Instruct/dev",  # Vision model ID with tag
        #     messages=[
        #         {
        #             "role": "user",
        #             "content": [
        #                 {"type": "text", "text": "What's in this image?"},
        #                 {
        #                     "type": "image_url",
        #                     "image_url": {
        #                         "url": f"data:image/jpeg;base64,{base64_image}"
        #                     }
        #                 }
        #             ]
        #         }
        #     ]
        # )
    except Exception as e:
        error_str = str(e).lower()
        logging.error(f"❌ EMD OpenAI API call failed: {str(e)}")
        logging.error(f"🔍 Model endpoint used: {model_endpoint}")
        logging.error(f"🌐 Base URL used: {client.base_url}")
        
        # Check if it's a deployment/startup issue
        if "404" in error_str or "not found" in error_str or "service unavailable" in error_str:
            # For deployed models that are detected but endpoints are not ready
            deployed_models = get_current_models()
            if model_key in deployed_models:
                raise Exception(f"模型 {model_key} 正在启动中，请稍等片刻后重试。SageMaker 端点可能需要几分钟时间完全启动。")
            else:
                raise Exception(f"模型 {model_key} 端点不可用。请检查部署状态或重新部署模型。")
        else:
            raise
    
    logging.info(f"✅ EMD OpenAI API call completed for {model_id}")
    log_entry['response'] = response.model_dump()
    logging.info(json.dumps(log_entry, ensure_ascii=False))
    
    # 统一返回格式，匹配Bedrock模型格式
    return {
        "content": [{"type": "text", "text": response.choices[0].message.content}],
        "usage": response.usage.model_dump() if response.usage else None
    }

def call_emd_via_sagemaker(client, data, model_id, model_key, log_entry):
    """Call EMD model via SageMaker SDK"""
    text = data.get('text', '')
    frames = data.get('frames', [])
    media_type = data.get('mediaType', 'image')
    max_tokens = data.get('max_tokens', 1024)
    temperature = data.get('temperature', 0.1)
    
    logging.info(f"🎯 Processing {media_type} input for EMD SageMaker model {model_id}")
    messages = []
    
    # Check if this is a text-only model (like Qwen2.5-0.5B-Instruct)
    if model_id == 'Qwen2.5-0.5B-Instruct':
        # Text-only model - just send the text prompt
        logging.info(f"📝 Processing text-only input for EMD SageMaker model {model_id}")
        messages.append({
            "role": "user",
            "content": text
        })
    elif media_type == 'video':
        # Process video: extract keyframes
        if len(frames) > 0:
            video_base64 = frames[0]
            logging.info(f"📹 EMD SageMaker {model_id} 开始从视频提取关键帧...")
            keyframes = extract_frames_from_video(video_base64, num_frames=8)
            
            if keyframes:
                enhanced_text = enhance_prompt_for_video(text, len(keyframes))
                content = [{"type": "text", "text": enhanced_text}]
                
                for frame_base64 in keyframes:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_base64}"
                        }
                    })
                
                messages.append({
                    "role": "user",
                    "content": content
                })
                logging.info(f"✅ EMD SageMaker {model_id} 成功添加了 {len(keyframes)} 个关键帧到请求中")
            else:
                raise Exception("Failed to extract frames from video for EMD SageMaker processing")
        else:
            raise Exception("No video data received for EMD SageMaker")
    else:
        # Process images (for multimodal models)
        logging.info(f"🖼️ Processing {len(frames)} images for EMD SageMaker model {model_id}")
        content = [{"type": "text", "text": text}]
        # print("[debug] text", text, "frames", frames)
        # for img_base64 in frames:
        #     content.append({
        #         "type": "image_url",
        #         "image_url": {
        #             "url": f"data:image/jpeg;base64,{img_base64}"
        #         }
        #     })
        
        messages.append({
            "role": "user",
            "content": content
        })
    
    logging.info(f"🔥 Calling EMD SageMaker SDK for {model_id}...")
    
    try:
        # client = SageMakerClient(
        #     model_id="Qwen2-VL-7B-Instruct",
        #     model_tag="dev"
        # )
        # messages = {
        #     "messages": [
        #         {
        #             "role": "user",
        #             "content": [
        #                 {"type": "text", "text": "Who are you?"},
        #             ]
        #         }
        #     ]
        # }
        # print(messages)
        # # response = client.invoke({"messages": messages})
        # response = client.invoke(messages)

        base_url = "http://EMD-EC-Publi-nOXevnWhCba1-203402465.us-west-2.elb.amazonaws.com/v1"

        client = OpenAI(
            api_key="",
            base_url=base_url
        )

        # image_path = "./image.jpg"
        # base64_image = encode_image(image_path)
        # print('base64_image=', base64_image[:10])

        response = client.chat.completions.create(
            model="Qwen2-VL-7B-Instruct/dev",  # Vision model ID with tag
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's in this image?"},
                        # {
                        #     "type": "image_url",
                        #     "image_url": {
                        #         "url": f"data:image/jpeg;base64,{base64_image}"
                        #     }
                        # }
                    ]
                }
            ]
        )
    except Exception as e:
        error_str = str(e).lower()
        logging.error(f"❌ EMD SageMaker SDK call failed: {str(e)}")
        
        # Check if it's a deployment/startup issue
        if "404" in error_str or "not found" in error_str or "service unavailable" in error_str or "model error" in error_str:
            # For deployed models that are detected but endpoints are not ready
            deployed_models = get_current_models()
            if model_key in deployed_models:
                raise Exception(f"模型 {model_key} 正在启动中，请稍等片刻后重试。SageMaker 端点可能需要几分钟时间完全启动。")
            else:
                raise Exception(f"模型 {model_key} 端点不可用。请检查部署状态或重新部署模型。")
        else:
            raise
    
    logging.info(f"✅ EMD SageMaker SDK call completed for {model_id}")
    log_entry['response'] = response.model_dump()
    logging.info(json.dumps(log_entry, ensure_ascii=False))
    
    # 统一返回格式，确保和其他模型格式一致
    # if isinstance(response, dict) and 'choices' in response:
    #     # 如果response已经有正确格式，确保content有type字段
    #     if isinstance(response['choices'], list) and len(response['choices']) > 0:
    #         for item in response['content']:
    #             if isinstance(item, dict) and 'text' in item and 'type' not in item:
    #                 item['type'] = 'text'
    #     return response
    # else:
    #     # 如果response是其他格式，尝试提取文本内容
    #     text_content = str(response) if response else "No response"
    #     return {
    #         "content": [{"type": "text", "text": text_content}],
    #         "usage": None
    #     }

    # return {
    #     "content": [{"type": "text", "text": response["choices"][0]["message"]["content"].strip()}],
    #     "usage": None
    # }

    return {
        "content": [{"type": "text", "text": response.choices[0].message.content.strip()}],
        "usage": None
    }

# EMD model endpoints
@app.route('/api/emd/<model_key>', methods=['POST'])
def call_emd_model(model_key):
    """Generic EMD model endpoint"""
    try:
        result = call_emd_model_internal(request.json, model_key)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/emd/status', methods=['GET'])
def emd_status():
    """Get EMD deployment status"""
    try:
        # Ensure subprocess inherits AWS environment variables
        env = os.environ.copy()
        logging.info("Getting EMD status...")
        result = subprocess.run(['emd', 'status'], capture_output=True, text=True, env=env, timeout=30)
        if result.returncode == 0:
            logging.info("✅ EMD status retrieved successfully")
            return jsonify({"status": "success", "output": result.stdout})
        else:
            logging.warning(f"❌ EMD status failed: {result.stderr}")
            # Check if it's a token issue
            if "InvalidClientTokenId" in result.stderr or "security token" in result.stderr.lower():
                return jsonify({
                    "status": "auth_error", 
                    "message": "AWS credentials expired. Please refresh your AWS session.",
                    "output": result.stderr
                }), 401
            else:
                return jsonify({"status": "error", "output": result.stderr}), 500
    except subprocess.TimeoutExpired:
        logging.error("EMD status command timed out")
        return jsonify({"error": "EMD status command timed out"}), 408
    except Exception as e:
        logging.error(f"EMD status exception: {e}")
        return jsonify({"error": str(e)}), 500

# @app.route('/api/emd/models', methods=['GET'])
# def emd_models():
#     """Get available EMD models"""
#     return jsonify({
#         "all_models": EMD_MODELS,
#         "deployed_models": get_current_models(),
#         "available_for_inference": list(DEPLOYED_MODELS.keys())
#     })

@app.route('/api/model-list', methods=['GET'])
def get_model_list():
    """获取所有模型列表信息"""
    try:
        logging.info("[DEBUG] 接收到 /api/model-list 请求")
        logging.info(f"[DEBUG] ALL_MODELS 结构: {ALL_MODELS}")
        logging.info(f"[DEBUG] EMD_MODELS keys: {list(EMD_MODELS.keys())}")
        logging.info(f"[DEBUG] BEDROCK_MODELS keys: {list(BEDROCK_MODELS.keys())}")
        
        response_data = {
            "status": "success",
            "models": ALL_MODELS
        }
        logging.info(f"[DEBUG] 返回的模型列表数据: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logging.error(f"[DEBUG] 获取模型列表信息失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/emd/config', methods=['GET'])
def emd_config():
    """Get EMD configuration information"""
    return jsonify(get_emd_info())

@app.route('/api/emd/config/tag', methods=['POST'])
def update_emd_tag():
    """Update the default EMD tag"""
    try:
        data = request.json
        new_tag = data.get('tag')
        if new_tag:
            set_emd_tag(new_tag)
            return jsonify({"status": "success", "new_tag": new_tag})
        else:
            return jsonify({"error": "Tag is required"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Global deployment tracking
deployment_status = {}
deployment_threads = {}
bootstrap_status = {"status": "unknown", "last_check": 0}

def check_emd_bootstrap_status():
    """Check if EMD environment is bootstrapped"""
    global bootstrap_status
    
    # Cache bootstrap status for 5 minutes
    current_time = time.time()
    if current_time - bootstrap_status["last_check"] < 300:  # 5 minutes cache
        return bootstrap_status["status"] == "ready"
    
    try:
        env = os.environ.copy()
        result = subprocess.run(['emd', 'status'], capture_output=True, text=True, env=env, timeout=30)
        
        if result.returncode == 0:
            bootstrap_status = {"status": "ready", "last_check": current_time}
            logging.info("✅ EMD environment is bootstrapped and ready")
            return True
        else:
            if "stack" in result.stderr.lower() or "environment" in result.stderr.lower():
                bootstrap_status = {"status": "not_bootstrapped", "last_check": current_time}
                logging.warning("⚠️ EMD environment needs bootstrapping")
                return False
            else:
                bootstrap_status = {"status": "error", "last_check": current_time}
                logging.error(f"❌ EMD status check failed: {result.stderr}")
                return False
    except Exception as e:
        bootstrap_status = {"status": "error", "last_check": current_time}
        logging.error(f"❌ EMD bootstrap check failed: {e}")
        return False

def run_emd_bootstrap():
    """Run EMD bootstrap command"""
    try:
        logging.info("🚀 Starting EMD bootstrap...")
        env = os.environ.copy()
        result = subprocess.run(['emd', 'bootstrap'], capture_output=True, text=True, env=env, timeout=600)  # 10 min timeout
        
        if result.returncode == 0:
            logging.info("✅ EMD bootstrap completed successfully")
            bootstrap_status["status"] = "ready"
            bootstrap_status["last_check"] = time.time()
            return True, result.stdout
        else:
            logging.error(f"❌ EMD bootstrap failed: {result.stderr}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        logging.error("❌ EMD bootstrap timed out")
        return False, "Bootstrap command timed out"
    except Exception as e:
        logging.error(f"❌ EMD bootstrap exception: {e}")
        return False, str(e)

def generate_deployment_tag(model_name):
    """Generate a unique deployment tag for the model"""
    timestamp = datetime.now().strftime("%m%d%H%M")
    clean_name = model_name.lower().replace('.', '').replace('-', '')
    return f"{timestamp}"

def deploy_emd_model_background(model_name, tag, config=None):
    """Deploy EMD model in background thread with deployment configuration"""
    global deployment_status
    
    # Extract configuration parameters
    if config is None:
        config = {}
    
    framework = config.get('framework', 'vllm')
    machine_type = config.get('machineType', 'g5.2xlarge')
    tp_size = config.get('tpSize', 1)
    dp_size = config.get('dpSize', 1)
    
    logging.info(f"EMD background deployment: {model_name}, framework={framework}, machine_type={machine_type}, tp_size={tp_size}, dp_size={dp_size}")
    
    try:
        # Step 1: Check bootstrap status
        deployment_status[model_name] = {
            "status": "checking_bootstrap",
            "tag": tag,
            "message": f"Checking EMD environment for {model_name}...",
            "start_time": datetime.now().isoformat()
        }
        
        # Check if EMD is bootstrapped
        if not check_emd_bootstrap_status():
            deployment_status[model_name]["status"] = "bootstrapping"
            deployment_status[model_name]["message"] = f"Bootstrapping EMD environment for {model_name}..."
            
            success, output = run_emd_bootstrap()
            if not success:
                deployment_status[model_name] = {
                    "status": "failed",
                    "tag": tag,
                    "message": f"Bootstrap failed for {model_name}",
                    "error": output,
                    "end_time": datetime.now().isoformat()
                }
                logging.error(f"❌ Bootstrap failed for {model_name}: {output}")
                return
        
        # Step 2: Start deployment
        deployment_status[model_name] = {
            "status": "deploying",
            "tag": tag,
            "message": f"Deploying {model_name} with tag {tag}...",
            "start_time": datetime.now().isoformat()
        }
        
        # Get model ID from EMD_MODELS mapping
        model_id = EMD_MODELS.get(model_name)["model_path"]
        if not model_id:
            raise ValueError(f"Unknown model: {model_name}")
        
        # Use configured instance type, with model-based fallback
        instance_type = machine_type  # Use the configured machine type
        if not instance_type or instance_type == 'auto':
            # Fallback to model-based instance type selection
            instance_type = "g5.2xlarge"  # Default for smaller models
            if "vl-32b" in model_name:
                instance_type = "g5.12xlarge"  # Larger instance for 32B model
            elif "vl-7b" in model_name or "ui-tars" in model_name:
                instance_type = "g5.4xlarge"  # Medium instance for 7B models
        
        logging.info(f"Using instance type: {instance_type} for model {model_name}")
        logging.info(f"Using framework: {framework} for model {model_name}")
        
        # Build EMD deploy command with configured parameters
        extra_params = {
            'tp_size': tp_size,
            'dp_size': dp_size
        }
        
        deploy_cmd = [
            'emd', 'deploy',
            '--model-id', model_id,
            '--instance-type', instance_type,
            '--engine-type', framework,  # Use configured framework
            '--service-type', 'sagemaker_realtime',
            '--model-tag', tag,
            '--extra-params', json.dumps(extra_params),
            '--skip-confirm'
        ]

        logging.info(f"🚀 Starting EMD deployment: model_id={model_id}, instance_type={instance_type}, engine={framework}, tag={tag}")
        logging.info(f"📋 Extra parameters: {extra_params}")
        result = deploy(
            model_id=model_id,
            instance_type=instance_type,
            engine_type=framework,  # Use configured framework
            service_type="sagemaker_realtime",
            model_tag=tag,
        )
        
        # Execute deployment command with inherited environment
        env = os.environ.copy()
        result = subprocess.run(deploy_cmd, capture_output=True, text=True, timeout=1800, env=env)  # 30 min timeout
        
        deployment_status[model_name] = {
            "status": "deployed",
            "tag": tag,
            "message": f"Successfully deployed {model_name}",
            "output": result.stdout,
            "end_time": datetime.now().isoformat()
        }
        # Deployment successful - models will be detected by get_current_models()
        logging.info(f"✅ EMD deployment successful for {model_name} with tag {tag}")
        logging.info(f"📝 Model {model_name} is now available for inference")
        # else:
        #     deployment_status[model_name] = {
        #         "status": "failed",
        #         "tag": tag,
        #         "message": f"Deployment failed for {model_name}",
        #         "error": result.stderr,
        #         "output": result.stdout,
        #         "end_time": datetime.now().isoformat()
        #     }
        #     logging.error(f"❌ EMD deployment failed for {model_name}: {result.stderr}")
            
    except Exception as e:
        deployment_status[model_name] = {
            "status": "failed",
            "tag": tag,
            "message": f"Deployment error for {model_name}: {str(e)}",
            "error": str(e),
            "end_time": datetime.now().isoformat()
        }
        logging.error(f"❌ EMD deployment exception for {model_name}: {e}")

##################
### flask api  ###
##################

@app.route('/api/deploy-models', methods=['POST'])
def deploy_models():
    """Deploy models with deployment configuration"""
    global deployment_threads
    
    try:
        data = request.json
        models = data.get('models', [])
        config = data.get('config', {})
        
        if not models:
            return jsonify({"error": "No models specified"}), 400
        
        # Extract deployment configuration
        deployment_method = config.get('method', 'SageMaker Endpoint')
        framework = config.get('framework', 'vllm')
        machine_type = config.get('machineType', 'g5.2xlarge')
        tp_size = config.get('tpSize', 1)
        dp_size = config.get('dpSize', 1)
        
        logging.info(f"Deployment request: models={models}, method={deployment_method}, framework={framework}, machine_type={machine_type}")
        
        # For now, only process the first model (single deployment)
        # TODO: Support batch deployment later
        model_name = models[0] if models else None
        
        if not model_name:
            return jsonify({"error": "No valid model specified"}), 400
        
        deployment_info = {}
        
        # Check deployment method
        if deployment_method == 'SageMaker Endpoint':
            # Use EMD deployment for SageMaker Endpoint
            if model_name not in EMD_MODELS:
                return jsonify({"error": f"Model {model_name} not supported for SageMaker Endpoint deployment"}), 400
                
            # Generate unique tag for this deployment
            tag = generate_deployment_tag(model_name)

            logging.info(f"Starting SageMaker Endpoint deployment: {model_name} with tag {tag}")
            
            # Check if already deploying
            if model_name in deployment_threads and deployment_threads[model_name].is_alive():
                deployment_info[model_name] = {
                    "status": "already_deploying",
                    "message": f"{model_name} is already being deployed"
                }
            else:
                # Start deployment thread with configuration
                thread = threading.Thread(
                    target=deploy_emd_model_background,
                    args=(model_name, tag, config),
                    daemon=True
                )
                thread.start()
                deployment_threads[model_name] = thread
                
                deployment_info[model_name] = {
                    "status": "started",
                    "tag": tag,
                    "message": f"Started SageMaker Endpoint deployment of {model_name}",
                    "config": {
                        "method": deployment_method,
                        "framework": framework,
                        "machine_type": machine_type,
                        "tp_size": tp_size,
                        "dp_size": dp_size
                    }
                }
                # Update global EMD tag to use the newest one
                set_emd_tag(tag)
                
        elif deployment_method == 'SageMaker HyperPod':
            # TODO: Implement SageMaker HyperPod deployment
            deployment_info[model_name] = {
                "status": "not_implemented",
                "message": f"SageMaker HyperPod deployment for {model_name} is not yet implemented",
                "config": config
            }
            logging.warning(f"SageMaker HyperPod deployment not implemented for {model_name}")
            
        elif deployment_method == 'EKS':
            # TODO: Implement EKS deployment
            deployment_info[model_name] = {
                "status": "not_implemented",
                "message": f"EKS deployment for {model_name} is not yet implemented",
                "config": config
            }
            logging.warning(f"EKS deployment not implemented for {model_name}")
            
        elif deployment_method == 'EC2':
            # TODO: Implement EC2 deployment
            deployment_info[model_name] = {
                "status": "not_implemented",
                "message": f"EC2 deployment for {model_name} is not yet implemented",
                "config": config
            }
            logging.warning(f"EC2 deployment not implemented for {model_name}")
            
        else:
            return jsonify({"error": f"Unsupported deployment method: {deployment_method}"}), 400
        
        return jsonify({
            "status": "success",
            "deployments": deployment_info,
            "deployment_method": deployment_method,
            "message": f"Started deployment for {len(deployment_info)} models using {deployment_method}"
        })
        
    except Exception as e:
        logging.error(f"Deploy models error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/check-model-status', methods=['POST'])
def check_model_status():
    """Check model deployment status for selected models"""
    data = request.json
    logging.info(f"[DEBUG] 接收到 /api/check-model-status 请求, data: {data}")
    
    selected_models = data.get('models', [])
    logging.info(f"[DEBUG] 选中的模型: {selected_models}, 类型: {type(selected_models)}")
    
    # 检查请求数据的完整性
    request_headers = {k: v for k, v in request.headers.items()}
    logging.info(f"[DEBUG] 请求头: {request_headers}")
    logging.info(f"[DEBUG] 请求数据: {request.get_data()}")    
    
    try:
        # Get currently deployed models
        current_models = get_current_models()
        logging.info(f"[DEBUG] 当前部署的模型: {current_models}")
        print(f"models:{current_models}")
        model_status = {}
        
        for model in BEDROCK_MODELS:
            print(model)
            # Bedrock models are always available
            model_status[model] = {
                "status": "available",
                "message": f"{model} 模型已准备好，随时可以使用",
                "type": "bedrock"
            }
        for model in EMD_MODELS:
            # EMD models need deployment check
            # current_models = {
            #     "inprogress": inprogress,
            #     "deployed": deployed,
            # }
            if model in current_models["deployed"]:
                model_status[model] = {
                    "status": "deployed",
                    "message": f"{model} 模型已部署，可以使用",
                    "tag": current_models["deployed"][model]['tag'],
                    "type": "emd"
                }
            elif model in current_models["inprogress"]:
                model_status[model] = {
                    "status": "inprogress",
                    "message": f"{model} 模型部署中，请等待",
                    "tag": current_models["inprogress"][model]['tag'],
                    "type": "emd"
                }
            elif model in current_models["failed"]:
                model_status[model] = {
                    "status": "failed",
                    "message": f"{model} 模型部署失败",
                    "tag": current_models["failed"][model]['tag'],
                    "type": "emd"
                }
            else:
                model_status[model] = {
                    "status": "not_deployed",
                    "message": f"{model} 模型需要部署，或部署失败",
                    "type": "emd"
                }
            # else:
            #     model_status[model] = {
            #         "status": "unknown",
            #         "message": f"未知模型: {model}",
            #         "type": "unknown"
            #     }
        print("model_status", model_status)
        return jsonify({
            "status": "success",
            "model_status": model_status,
            "deployed_models": current_models["deployed"]
        })
        
    except Exception as e:
        logging.error(f"Check model status error: {e}")
        return jsonify({"error": str(e)}), 500

# 压力测试相关功能
stress_test_sessions = {}

def run_stress_test_evalscope(model_key, test_params, session_id):
    """使用evalscope Python API运行压力测试"""
    global stress_test_sessions
    
    try:
        logging.info(f"[STRESS_TEST] Starting stress test for session {session_id} with model {model_key}")
        logging.info(f"[STRESS_TEST] Test params: {test_params}")
        
        # 初始化测试状态
        stress_test_sessions[session_id] = {
            "status": "preparing",
            "model": model_key,
            "start_time": datetime.now().isoformat(),
            "progress": 0,
            "message": "准备测试环境...",
            "results": None,
            "error": None
        }
        logging.info(f"[STRESS_TEST] Session {session_id} initialized")
        
        # 检查模型是否可用
        logging.info(f"[STRESS_TEST] Checking if model {model_key} is available")
        deployed_models = get_current_models()["deployed"]
        logging.info(f"[STRESS_TEST] Deployed models: {list(deployed_models.keys())}")
        logging.info(f"[STRESS_TEST] Bedrock models: {list(BEDROCK_MODELS.keys())}")
        
        if model_key not in deployed_models and model_key not in BEDROCK_MODELS:
            error_msg = f"模型 {model_key} 未部署或不可用"
            logging.error(f"[STRESS_TEST] {error_msg}")
            raise Exception(error_msg)
        
        logging.info(f"[STRESS_TEST] Model {model_key} is available. Setting status to running...")
        stress_test_sessions[session_id]["status"] = "running"
        stress_test_sessions[session_id]["message"] = "正在运行压力测试..."
        stress_test_sessions[session_id]["progress"] = 10
        logging.info(f"[STRESS_TEST] Session {session_id} status updated to running")
        
        # 获取测试参数
        num_requests = test_params.get('num_requests', 100)
        concurrency = test_params.get('concurrency', 10)
        input_tokens_range = test_params.get('input_tokens_range', [50, 100])
        output_tokens_range = test_params.get('output_tokens_range', [100, 200])
        temperature = test_params.get('temperature', 0.1)
        
        logging.info(f"[STRESS_TEST] Test parameters - requests: {num_requests}, concurrency: {concurrency}")
        logging.info(f"[STRESS_TEST] Token ranges - input: {input_tokens_range}, output: {output_tokens_range}")
        
        # 准备evalscope Python API
        stress_test_sessions[session_id]["progress"] = 30
        stress_test_sessions[session_id]["message"] = "配置evalscope参数..."
        
        # 根据模型类型构建API配置
        if model_key in EMD_MODELS:
            # EMD模型使用OpenAI格式API
            model_id = EMD_MODELS[model_key]["model_path"]
            deployed_tag = deployed_models[model_key]['tag']
            base_url = get_emd_base_url(model_id, deployed_tag)
            api_url = f"{base_url}/v1/chat/completions"
            model_endpoint = f"{model_id}/{deployed_tag}"
        else:
            # Bedrock模型暂不支持（需要本地API调用）
            raise Exception(f"Bedrock模型 {model_key} 暂不支持直接压力测试，请使用EMD模型")
        
        # 使用evalscope Python API
        try:
            # 动态导入evalscope模块（在evalscope环境中运行）
            import sys
            evalscope_env_path = "/home/ec2-user/SageMaker/efs/conda_envs/evalscope/lib/python3.10/site-packages"
            if evalscope_env_path not in sys.path:
                sys.path.insert(0, evalscope_env_path)
            
            # 创建临时Python脚本文件 - 包含修复EMD API兼容性的补丁
            evalscope_script_content = f"""
import sys
sys.path.insert(0, '/home/ec2-user/SageMaker/efs/conda_envs/evalscope/lib/python3.10/site-packages')

# 修复EMD API流式响应兼容性问题
def patch_openai_api():
    from evalscope.perf.plugin.api.openai_api import OpenaiPlugin
    
    # 保存原始方法
    original_calculate_tokens = OpenaiPlugin._OpenaiPlugin__calculate_tokens_from_content
    
    def patched_calculate_tokens(self, request, delta_contents):
        try:
            # 最强力的数据清洗和类型转换
            normalized_contents = []
            
            # 检查delta_contents本身的类型
            if delta_contents is None:
                return 0, 0
            
            # 确保delta_contents是可迭代的
            if not hasattr(delta_contents, '__iter__') or isinstance(delta_contents, (str, bytes)):
                # 如果不是列表，尝试包装成列表
                delta_contents = [delta_contents] if delta_contents is not None else []
            
            for i, choice_contents in enumerate(delta_contents):
                try:
                    if choice_contents is None:
                        normalized_contents.append([])
                    elif isinstance(choice_contents, (list, tuple)):
                        # 处理列表/元组：递归清理所有元素
                        clean_list = []
                        for item in choice_contents:
                            if item is not None:
                                if isinstance(item, (str, int, float, bool)):
                                    clean_list.append(str(item))
                                else:
                                    clean_list.append(str(item) if hasattr(item, '__str__') else '')
                        normalized_contents.append(clean_list)
                    elif isinstance(choice_contents, (str, int, float, bool)):
                        # 基础类型：转换为字符串列表
                        normalized_contents.append([str(choice_contents)])
                    elif isinstance(choice_contents, dict):
                        # 字典类型：提取文本内容
                        text_content = choice_contents.get('text', choice_contents.get('content', str(choice_contents)))
                        normalized_contents.append([str(text_content)])
                    else:
                        # 其他类型：强制转换为字符串
                        try:
                            str_content = str(choice_contents) if choice_contents is not None else ''
                            normalized_contents.append([str_content])
                        except:
                            normalized_contents.append([''])
                except Exception as item_error:
                    print(f"Error processing item {{i}}: {{item_error}}, type: {{type(choice_contents)}}")
                    normalized_contents.append([''])
            
            # 确保我们有有效的数据结构
            if not normalized_contents:
                return 0, 0
            
            return original_calculate_tokens(self, request, normalized_contents)
            
        except Exception as e:
            print(f"Primary patch failed: {{e}}, delta_contents type: {{type(delta_contents)}}")
            # 超级安全的回退策略
            try:
                # 尝试完全重构数据
                if delta_contents is None:
                    return 0, 0
                
                # 强制创建安全的字符串列表结构
                safe_structure = []
                
                if isinstance(delta_contents, (list, tuple)):
                    for item in delta_contents:
                        if item is None:
                            safe_structure.append([])
                        else:
                            # 无论什么类型，都转换为字符串列表
                            safe_structure.append([str(item)[:1000]])  # 限制长度防止内存问题
                else:
                    # 单个项目，包装成列表结构
                    safe_structure.append([str(delta_contents)[:1000]] if delta_contents is not None else [''])
                
                return original_calculate_tokens(self, request, safe_structure)
                
            except Exception as fallback_error:
                print(f"All fallback attempts failed: {{fallback_error}}")
                # 最终安全网：返回保守的token估计
                try:
                    # 尝试基于请求内容估算token数
                    if hasattr(request, 'get'):
                        content = request.get('messages', [])
                        if content:
                            text_content = str(content)
                            estimated_tokens = max(len(text_content) // 4, 10)  # 粗略估计
                            return estimated_tokens, estimated_tokens
                except:
                    pass
                
                return 10, 10  # 最保守的默认值
    
    # 应用补丁
    OpenaiPlugin._OpenaiPlugin__calculate_tokens_from_content = patched_calculate_tokens

# 应用补丁
patch_openai_api()

from evalscope.perf.main import run_perf_benchmark
from evalscope.perf.arguments import Arguments
import json

# 创建测试配置 - 保持流式传输以获得TTFT和延迟指标
task_cfg = Arguments(
    parallel=[{concurrency}],
    number=[{num_requests}],
    model='{model_endpoint}',
    url='{api_url}',
    api='openai',
    dataset='random',
    max_tokens={max(output_tokens_range)},
    min_tokens={min(output_tokens_range)},
    min_prompt_length={min(input_tokens_range)},
    max_prompt_length={max(input_tokens_range)},
    tokenizer_path='/home/ec2-user/SageMaker/efs/Models/Qwen3-32B-AWQ',
    temperature={temperature},
    stream=True  # 保持流式传输以获得准确的TTFT和延迟指标
)

# 运行基准测试
try:
    results = run_perf_benchmark(task_cfg)
    print("EVALSCOPE_SUCCESS:", json.dumps(results) if results else "{{}}")
except Exception as e:
    print("EVALSCOPE_ERROR:", str(e))
    import traceback
    traceback.print_exc()
"""
            
            # 创建临时脚本文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
                script_file.write(evalscope_script_content)
                script_path = script_file.name
            
            stress_test_sessions[session_id]["progress"] = 20
            stress_test_sessions[session_id]["message"] = "准备执行evalscope基准测试..."
            
            # 在evalscope环境中执行脚本
            env = os.environ.copy()
            evalscope_cmd = f"source /opt/conda/etc/profile.d/conda.sh && conda activate evalscope && python {script_path}"
            
            logging.info(f"[STRESS_TEST] Executing evalscope Python API...")
            stress_test_sessions[session_id]["progress"] = 30
            stress_test_sessions[session_id]["message"] = "执行evalscope基准测试..."
            
            try:
                result = subprocess.run(
                    evalscope_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=1800,  # 30分钟超时
                    env=env,
                    executable='/bin/bash'
                )
                
                logging.info(f"[STRESS_TEST] Evalscope Python API completed with return code: {result.returncode}")
                if result.stdout:
                    logging.info(f"[STRESS_TEST] Evalscope stdout: {result.stdout}")
                if result.stderr:
                    logging.error(f"[STRESS_TEST] Evalscope stderr: {result.stderr}")
                
                stress_test_sessions[session_id]["progress"] = 90
                stress_test_sessions[session_id]["message"] = "正在处理测试结果..."
                
            finally:
                # 清理临时脚本文件
                try:
                    os.unlink(script_path)
                except:
                    pass
            
            # 解析结果
            if "EVALSCOPE_SUCCESS:" in result.stdout:
                # 提取成功结果
                success_line = [line for line in result.stdout.split('\n') if 'EVALSCOPE_SUCCESS:' in line][0]
                results_str = success_line.replace('EVALSCOPE_SUCCESS:', '').strip()
                
                try:
                    # 尝试解析JSON结果
                    import json
                    raw_results = json.loads(results_str) if results_str else []
                    
                    # 转换为前端期望的格式
                    if isinstance(raw_results, list) and len(raw_results) >= 2:
                        summary_data = raw_results[0]
                        percentile_data = raw_results[1] if len(raw_results) > 1 else {}
                        
                        # 创建前端兼容的结果格式
                        results = {
                            "qps": summary_data.get("Request throughput (req/s)", 0),
                            "avg_ttft": summary_data.get("Average time to first token (s)", 0),
                            "avg_latency": summary_data.get("Average latency (s)", 0),
                            "tokens_per_second": summary_data.get("Total token throughput (tok/s)", 0),
                            "p50_ttft": percentile_data.get("TTFT (s)", [0] * 10)[4] if "TTFT (s)" in percentile_data else 0,
                            "p99_ttft": percentile_data.get("TTFT (s)", [0] * 10)[9] if "TTFT (s)" in percentile_data else 0,
                            "p50_latency": percentile_data.get("Latency (s)", [0] * 10)[4] if "Latency (s)" in percentile_data else 0,
                            "p99_latency": percentile_data.get("Latency (s)", [0] * 10)[9] if "Latency (s)" in percentile_data else 0,
                            "summary": summary_data,
                            "percentiles": percentile_data,
                            "detailed_metrics": {
                                "ttft_distribution": percentile_data.get("TTFT (s)", []),
                                "latency_distribution": percentile_data.get("Latency (s)", []),
                                "input_tokens": percentile_data.get("Input tokens", []),
                                "output_tokens": percentile_data.get("Output tokens", [])
                            }
                        }
                    else:
                        # 备用解析方案
                        results = {
                            "summary": raw_results[0] if raw_results else {},
                            "raw_data": raw_results
                        }
                        
                except Exception as parse_error:
                    logging.error(f"[STRESS_TEST] JSON parsing failed: {parse_error}")
                    # 如果解析失败，尝试文本解析
                    results = parse_evalscope_output(result.stdout)
                
                stress_test_sessions[session_id].update({
                    "status": "completed",
                    "progress": 100,
                    "message": "测试完成",
                    "results": results,
                    "end_time": datetime.now().isoformat(),
                    "raw_output": result.stdout
                })
                
            elif "EVALSCOPE_ERROR:" in result.stdout:
                # 提取错误信息
                error_line = [line for line in result.stdout.split('\n') if 'EVALSCOPE_ERROR:' in line][0]
                error_msg = error_line.replace('EVALSCOPE_ERROR:', '').strip()
                
                stress_test_sessions[session_id].update({
                    "status": "failed",
                    "progress": 100,
                    "message": "测试失败",
                    "error": error_msg,
                    "raw_output": result.stdout,
                    "end_time": datetime.now().isoformat()
                })
            else:
                # 未找到明确的成功或错误标记
                if result.returncode == 0:
                    # 进程成功但输出格式可能不符合预期
                    results = parse_evalscope_output(result.stdout)
                    stress_test_sessions[session_id].update({
                        "status": "completed",
                        "progress": 100,
                        "message": "测试完成",
                        "results": results,
                        "end_time": datetime.now().isoformat(),
                        "raw_output": result.stdout
                    })
                else:
                    stress_test_sessions[session_id].update({
                        "status": "failed",
                        "progress": 100,
                        "message": "测试失败",
                        "error": result.stderr or "未知错误",
                        "raw_output": result.stdout,
                        "end_time": datetime.now().isoformat()
                    })
                    
        except Exception as api_error:
            logging.error(f"[STRESS_TEST] Evalscope API error: {str(api_error)}")
            raise Exception(f"Evalscope API调用失败: {str(api_error)}")
                
    except Exception as e:
        logging.error(f"[STRESS_TEST] Exception in stress test session {session_id}: {str(e)}")
        logging.error(f"[STRESS_TEST] Exception traceback: {traceback.format_exc()}")
        stress_test_sessions[session_id].update({
            "status": "failed",
            "progress": 100,
            "message": f"测试异常: {str(e)}",
            "error": str(e),
            "end_time": datetime.now().isoformat()
        })

def parse_evalscope_output(output):
    """解析evalscope输出结果"""
    try:
        # 简单的输出解析，实际可能需要根据evalscope的具体输出格式调整
        lines = output.split('\n')
        results = {
            "summary": {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "average_latency": 0,
                "min_latency": 0,
                "max_latency": 0,
                "p95_latency": 0,
                "p99_latency": 0,
                "requests_per_second": 0,
                "average_ttft": 0,
                "tokens_per_second": 0
            },
            "detailed_metrics": [],
            "errors": []
        }
        
        # 这里可以添加更详细的解析逻辑
        for line in lines:
            if "Total requests" in line:
                try:
                    results["summary"]["total_requests"] = int(line.split(":")[-1].strip())
                except:
                    pass
            elif "Successful" in line:
                try:
                    results["summary"]["successful_requests"] = int(line.split(":")[-1].strip())
                except:
                    pass
            elif "Average latency" in line:
                try:
                    results["summary"]["average_latency"] = float(line.split(":")[-1].strip().replace('ms', ''))
                except:
                    pass
        
        return results
    except Exception as e:
        return {"error": f"Failed to parse results: {str(e)}", "raw_output": output}

@app.route('/api/stress-test/start', methods=['POST'])
def start_stress_test():
    """启动压力测试"""
    try:
        data = request.json
        model_key = data.get('model')
        test_params = data.get('params', {})
        
        if not model_key:
            return jsonify({"error": "Model is required"}), 400
        
        # 生成唯一的测试会话ID
        import uuid
        session_id = str(uuid.uuid4())[:8]
        
        # 在后台线程中运行测试
        thread = threading.Thread(
            target=run_stress_test_evalscope,
            args=(model_key, test_params, session_id),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "status": "success",
            "session_id": session_id,
            "message": "压力测试已启动"
        })
        
    except Exception as e:
        logging.error(f"Start stress test error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stress-test/status/<session_id>', methods=['GET'])
def get_stress_test_status(session_id):
    """获取压力测试状态"""
    try:
        if session_id not in stress_test_sessions:
            logging.warning(f"[STRESS_TEST_STATUS] Session {session_id} not found in sessions")
            return jsonify({"error": "Test session not found"}), 404
        
        session_data = stress_test_sessions[session_id]
        logging.info(f"[STRESS_TEST_STATUS] Session {session_id} status: {session_data.get('status')}, progress: {session_data.get('progress')}")
        
        return jsonify({
            "status": "success",
            "test_session": session_data
        })
        
    except Exception as e:
        logging.error(f"Get stress test status error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stress-test/download/<session_id>', methods=['GET'])
def download_stress_test_report(session_id):
    """下载压力测试PDF报告"""
    try:
        if session_id not in stress_test_sessions:
            return jsonify({"error": "Test session not found"}), 404
        
        session_data = stress_test_sessions[session_id]
        
        if session_data.get("status") != "completed" or not session_data.get("results"):
            return jsonify({"error": "Test not completed or no results available"}), 400
        
        # 生成PDF报告
        pdf_content = generate_pdf_report(session_data, session_id)
        
        # 返回PDF文件
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=stress_test_report_{session_id}.pdf'
        return response
        
    except Exception as e:
        logging.error(f"Download stress test report error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def generate_pdf_report(session_data, session_id):
    """生成PDF格式的压力测试报告"""
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from datetime import datetime
    import io
    import os
    
    # 注册中文字体
    try:
        # 尝试注册中文字体，使用系统字体路径
        chinese_font_paths = [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',  # 优先使用Noto CJK
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',  # WenQuanYi微米黑
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',  # WenQuanYi正黑
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',  # Linux Noto
            '/System/Library/Fonts/PingFang.ttc',  # macOS
        ]
        
        font_registered = False
        for font_path in chinese_font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                    font_registered = True
                    break
                except:
                    continue
        
        # 如果没有找到中文字体，使用Helvetica作为回退
        if not font_registered:
            chinese_font_name = 'Helvetica'
        else:
            chinese_font_name = 'ChineseFont'
            
    except Exception as e:
        print(f"Font registration error: {e}")
        chinese_font_name = 'Helvetica'
    
    # 创建PDF缓冲区
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # 获取样式
    styles = getSampleStyleSheet()
    
    # 自定义样式（使用中文字体）
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=chinese_font_name,
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName=chinese_font_name,
        fontSize=16,
        spaceAfter=15,
        spaceBefore=20,
        textColor=colors.darkblue
    )
    
    # 构建PDF内容
    story = []
    
    # 标题
    story.append(Paragraph("压力测试报告", title_style))
    story.append(Spacer(1, 20))
    
    # 测试信息
    story.append(Paragraph("测试基本信息", heading_style))
    
    test_info_data = [
        ['项目', '值'],
        ['模型', session_data.get('model', 'N/A')],
        ['会话ID', session_id],
        ['开始时间', session_data.get('start_time', 'N/A')],
        ['结束时间', session_data.get('end_time', 'N/A')],
        ['状态', '完成' if session_data.get('status') == 'completed' else session_data.get('status', 'N/A')]
    ]
    
    test_info_table = Table(test_info_data, colWidths=[2*inch, 4*inch])
    test_info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), chinese_font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTNAME', (0, 1), (-1, -1), chinese_font_name),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(test_info_table)
    story.append(Spacer(1, 20))
    
    # 性能指标概览
    results = session_data.get('results', {})
    if results:
        story.append(Paragraph("性能指标概览", heading_style))
        
        metrics_data = [
            ['指标', '数值', '单位'],
            ['QPS (每秒查询数)', f"{results.get('qps', 0):.2f}", 'queries/sec'],
            ['平均首字延迟', f"{results.get('avg_ttft', 0):.3f}", 'seconds'],
            ['平均端到端延迟', f"{results.get('avg_latency', 0):.3f}", 'seconds'],
            ['吞吐量', f"{results.get('tokens_per_second', 0):.2f}", 'tokens/sec'],
            ['P50 首字延迟', f"{results.get('p50_ttft', 0):.3f}", 'seconds'],
            ['P99 首字延迟', f"{results.get('p99_ttft', 0):.3f}", 'seconds'],
            ['P50 端到端延迟', f"{results.get('p50_latency', 0):.3f}", 'seconds'],
            ['P99 端到端延迟', f"{results.get('p99_latency', 0):.3f}", 'seconds']
        ]
        
        metrics_table = Table(metrics_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), chinese_font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
            ('FONTNAME', (0, 1), (-1, -1), chinese_font_name),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10)
        ]))
        
        story.append(metrics_table)
        story.append(Spacer(1, 20))
        
        # 百分位数据详细表
        percentiles = results.get('percentiles', {})
        if percentiles and 'Percentiles' in percentiles:
            story.append(PageBreak())
            story.append(Paragraph("百分位数据详细表", heading_style))
            
            percentile_labels = percentiles['Percentiles']
            percentile_data = [['百分位', 'TTFT (s)', '延迟 (s)', 'ITL (s)', 'TPOT (s)', '输入Token', '输出Token', '吞吐量 (tok/s)']]
            
            for i, label in enumerate(percentile_labels):
                row = [
                    label,
                    f"{percentiles.get('TTFT (s)', [0]*len(percentile_labels))[i]:.4f}",
                    f"{percentiles.get('Latency (s)', [0]*len(percentile_labels))[i]:.4f}",
                    f"{percentiles.get('ITL (s)', [0]*len(percentile_labels))[i]:.4f}",
                    f"{percentiles.get('TPOT (s)', [0]*len(percentile_labels))[i]:.4f}",
                    str(percentiles.get('Input tokens', [0]*len(percentile_labels))[i]),
                    str(percentiles.get('Output tokens', [0]*len(percentile_labels))[i]),
                    f"{percentiles.get('Output (tok/s)', [0]*len(percentile_labels))[i]:.2f}"
                ]
                percentile_data.append(row)
            
            percentile_table = Table(percentile_data, colWidths=[0.8*inch]*8)
            percentile_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), chinese_font_name),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
                ('FONTNAME', (0, 1), (-1, -1), chinese_font_name),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))
            
            story.append(percentile_table)
            story.append(Spacer(1, 20))
        
        # 详细摘要信息
        summary = results.get('summary', {})
        if summary:
            story.append(Paragraph("测试执行摘要", heading_style))
            
            summary_data = [
                ['项目', '值'],
                ['测试耗时', f"{summary.get('Time taken for tests (s)', 0):.2f} 秒"],
                ['并发数', str(summary.get('Number of concurrency', 0))],
                ['总请求数', str(summary.get('Total requests', 0))],
                ['成功请求数', str(summary.get('Succeed requests', 0))],
                ['失败请求数', str(summary.get('Failed requests', 0))],
                ['平均输入Token数', f"{summary.get('Average input tokens per request', 0):.1f}"],
                ['平均输出Token数', f"{summary.get('Average output tokens per request', 0):.1f}"],
                ['平均Token间延迟', f"{summary.get('Average inter-token latency (s)', 0):.4f} 秒"],
                ['平均每输出Token时间', f"{summary.get('Average time per output token (s)', 0):.4f} 秒"]
            ]
            
            summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), chinese_font_name),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lavender),
                ('FONTNAME', (0, 1), (-1, -1), chinese_font_name),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 10)
            ]))
            
            story.append(summary_table)
    
    # 页脚信息
    footer_style = ParagraphStyle('Footer', fontName=chinese_font_name, fontSize=10, alignment=TA_CENTER, textColor=colors.grey)
    story.append(Spacer(1, 30))
    story.append(Paragraph(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
    story.append(Paragraph("由 EMD 推理平台生成", footer_style))
    
    # 构建PDF
    doc.build(story)
    
    # 获取PDF数据
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

# @app.route('/api/deploy-selected-models', methods=['POST'])
# def deploy_selected_models():
#     """Deploy selected EMD models (called when user clicks 下一步,上传材料)"""
#     data = request.json
#     selected_models = data.get('models', [])
#     # Keep model keys as they are (simplified names like 'qwen2-vl-7b')
#     emd_models = [x for x in selected_models if x in EMD_MODELS]
    
#     if not emd_models:
#         return jsonify({"error": "No EMD models specified"}), 400
    
#     try:
#         # Filter to only EMD models that need deployment
#         deployed_models = get_current_models()
#         models_to_deploy = []
        
#         for model in emd_models:
#             if model not in deployed_models:
#                 models_to_deploy.append(model)
        
#         if not models_to_deploy:
#             return jsonify({
#                 "status": "success",
#                 "message": "所有所选模型都已部署或不需要部署",
#                 "models_to_deploy": []
#             })
        
#         # Start deployment for models that need it
#         deployment_info = {}
#         for model_name in models_to_deploy:
#             try:
#                 tag = deploy_model_if_not_exist(model_name)
#                 deployment_info[model_name] = {
#                     "status": "deploying",
#                     "tag": tag,
#                     "message": f"开始部署 {model_name}，请耐心等待..."
#                 }
#             except Exception as e:
#                 deployment_info[model_name] = {
#                     "status": "error",
#                     "message": f"部署 {model_name} 失败: {str(e)}"
#                 }
        
#         return jsonify({
#             "status": "success",
#             "deployment_info": deployment_info,
#             "models_deployed": len(deployment_info),
#             "message": f"开始部署 {len(deployment_info)} 个模型"
#         })
        
#     except Exception as e:
#         logging.error(f"Deploy selected models error: {e}")
#         return jsonify({"error": str(e)}), 500

# @app.route('/api/emd/deployment-stream', methods=['GET'])
# def stream_emd_deployment_status():
#     """Stream real-time deployment status updates"""
#     def generate():
#         """Generator for streaming deployment updates"""
#         models_to_watch = request.args.get('models', '').split(',') if request.args.get('models') else []
        
#         # Send initial status
#         yield f"data: {json.dumps({'type': 'initial', 'deployments': deployment_status, 'bootstrap_status': bootstrap_status})}\n\n"
        
#         last_status = {}
#         check_interval = 2  # Check every 2 seconds
#         max_duration = 1800  # Maximum 30 minutes
#         start_time = time.time()
        
#         while time.time() - start_time < max_duration:
#             try:
#                 # Check if any deployments are still active
#                 any_active = any(
#                     status.get("status") in ["checking_bootstrap", "bootstrapping", "deploying"]
#                     for status in deployment_status.values()
#                 )
                
#                 # If watching specific models, check if they're still active
#                 if models_to_watch:
#                     models_active = any(
#                         model in deployment_status and 
#                         deployment_status[model].get("status") in ["checking_bootstrap", "bootstrapping", "deploying"]
#                         for model in models_to_watch
#                     )
#                     if not models_active and models_to_watch:
#                         # Send final status and close
#                         yield f"data: {json.dumps({'type': 'complete', 'deployments': deployment_status})}\n\n"
#                         break
#                 elif not any_active:
#                     # No active deployments, send final status
#                     yield f"data: {json.dumps({'type': 'complete', 'deployments': deployment_status})}\n\n"
#                     break
                
#                 # Check for status changes
#                 current_status = {k: v for k, v in deployment_status.items()}
#                 if current_status != last_status:
#                     # Send update
#                     update_data = {
#                         'type': 'update',
#                         'deployments': current_status,
#                         'bootstrap_status': bootstrap_status,
#                         'deployed_models': get_current_models(),
#                         'timestamp': datetime.now().isoformat()
#                     }
#                     yield f"data: {json.dumps(update_data)}\n\n"
#                     last_status = current_status.copy()
                
#                 # Send heartbeat
#                 yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"
                
#                 time.sleep(check_interval)
                
#             except Exception as e:
#                 yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
#                 break
        
#         # Send final completion message
#         yield f"data: {json.dumps({'type': 'stream_ended'})}\n\n"
    
#     return Response(
#         generate(),
#         mimetype='text/plain',
#         headers={
#             'Cache-Control': 'no-cache',
#             'Connection': 'keep-alive',
#             'Content-Type': 'text/event-stream',
#             'Access-Control-Allow-Origin': '*'
#         }
#     )

def test_emd_integration():
    """Test EMD integration - useful for debugging"""
    print("🧪 Testing EMD Integration...")
    
    # Test SageMaker client
    try:
        client = create_emd_sagemaker_client("Qwen2.5-0.5B-Instruct")
        if client:
            print(f"✅ SageMaker client created: {client.endpoint_name}")
        else:
            print("❌ SageMaker client creation failed")
    except Exception as e:
        print(f"❌ SageMaker test error: {e}")
    
    # Test OpenAI client
    try:
        client = create_emd_openai_client()
        if client:
            print(f"✅ OpenAI client created with base URL: {client.base_url}")
        else:
            print("❌ OpenAI client creation failed")
    except Exception as e:
        print(f"❌ OpenAI test error: {e}")

if __name__ == '__main__':
    
    # 通过boto3获取当前区域
    try:
        session = boto3.session.Session()
        region = session.region_name or 'us-west-2'  # 如果获取失败，使用默认值
        logging.info(f"使用boto3获取到区域: {region}")
    except Exception as e:
        region = 'us-west-2'  # 默认区域
        logging.warning(f"无法通过boto3获取区域，使用默认值: {e}")
    
    # emd初始化
    try:
        init_emd_env(region=region)
        logging.info(f"EMD initialized at startup with region: {region}")
    except Exception as e:
        logging.error(f"Startup EMD initialization failed: {e}")

    print("🚀 Starting EMD-integrated Multimodal Inference Platform")
    print(f"📋 Available EMD models: {list(EMD_MODELS.keys())}")
    
    # Get currently deployed models dynamically
    try:
        deployed_models = get_current_models()
        print(f"🏷️ Currently deployed models: {list(deployed_models.keys())}")
        if deployed_models:
            for model, info in deployed_models.items():
                print(f"   - {model}: tag={info['tag']}, endpoint={info.get('endpoint', 'N/A')}")
        else:
            print("⚠️ No models currently deployed")
    except Exception as e:
        logging.warning(f"Could not get deployed models at startup: {e}")
    
    print(f"🏷️ Default EMD tag: {DEFAULT_EMD_TAG}")
    print("🌐 Server running on http://localhost:5000")
    
    # Uncomment to test EMD integration on startup
    # test_emd_integration()
    
    app.run(host='0.0.0.0', port=5000) 