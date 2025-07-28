from flask import Flask, request, jsonify, Response
import boto3
import json
import logging
from datetime import datetime
from flask_cors import CORS
import threading
import queue
import os
import subprocess
import tempfile
import base64
from PIL import Image
import io
from openai import OpenAI
from emd.sdk.clients.sagemaker_client import SageMakerClient
from emd.sdk.status import get_model_status

app = Flask(__name__)
CORS(app)

# 配置日志
logging.basicConfig(
    filename='claude35_api.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

bedrock_client = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-west-2'
)

# EMD client configurations
EMD_MODELS = {
    'qwen2-vl-7b': 'Qwen2-VL-7B-Instruct',
    'qwen2.5-vl-32b': 'Qwen2.5-VL-32B-Instruct',
    'gemma-3-4b': 'gemma-3-4b-it',
    'ui-tars-1.5-7b': 'UI-TARS-1.5-7B'
}

def get_emd_base_url():
    """Get EMD base URL from emd status command"""
    try:
        result = subprocess.run(['emd', 'status'], capture_output=True, text=True)
        if result.returncode == 0:
            # Parse the output to find the base URL
            lines = result.stdout.split('\n')
            for line in lines:
                if 'http://' in line and 'elb.amazonaws.com' in line:
                    return line.strip()
        return None
    except Exception as e:
        logging.error(f"Error getting EMD base URL: {e}")
        return None

def create_emd_openai_client():
    """Create OpenAI client for EMD endpoints"""
    base_url = get_emd_base_url()
    if base_url:
        return OpenAI(api_key="", base_url=f"{base_url}/v1")
    return None

def create_emd_sagemaker_client(model_id, model_tag="dev"):
    """Create SageMaker client for EMD endpoints"""
    try:
        return SageMakerClient(model_id=model_id, model_tag=model_tag)
    except Exception as e:
        logging.error(f"Error creating EMD SageMaker client: {e}")
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
        return "022499040310"  # 默认账户ID

def build_inference_profile_arn(model_type, account_id=None, region='us-west-2'):
    """构建推理配置文件ARN"""
    if account_id is None:
        account_id = get_account_id()
    
    model_mappings = {
        'claude4': 'us.anthropic.claude-sonnet-4-20250514-v1:0',
        'nova': 'us.amazon.nova-pro-v1:0'
    }
    
    if model_type in model_mappings:
        return f"arn:aws:bedrock:{region}:{account_id}:inference-profile/{model_mappings[model_type]}"
    else:
        # 如果不需要推理配置文件，返回直接的模型ID
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
                duration = float(subprocess.check_output(duration_cmd, shell=True).decode().strip())
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
                    subprocess.run(ffmpeg_cmd, shell=True, check=True)
                    
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
    try:
        result = endpoint_func(data)
        result_queue.put({
            'model': model_name,
            'status': 'success',
            'result': result
        })
    except Exception as e:
        result_queue.put({
            'model': model_name,
            'status': 'error',
            'error': str(e)
        })

@app.route('/api/multi-inference', methods=['POST'])
def multi_inference():
    """同时调用多个模型进行推理，支持流式返回结果"""
    data = request.json
    models = data.get('models', ['claude4', 'claude35', 'nova'])
    
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
                # EMD model
                thread = threading.Thread(
                    target=process_model_async,
                    args=(model, lambda d: call_emd_model_internal(d, model), data, result_queue)
                )
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
        log_entry['response'] = response_body
        logging.info(json.dumps(log_entry, ensure_ascii=False))
        return response_body
    except Exception as e:
        log_entry['error'] = str(e)
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
        log_entry['response'] = response_body
        logging.info(json.dumps(log_entry, ensure_ascii=False))
        return response_body
    except Exception as e:
        log_entry['error'] = str(e)
        logging.error(json.dumps(log_entry, ensure_ascii=False))
        raise Exception(str(e))

@app.route('/api/claude35', methods=['POST'])
def call_claude35():
    try:
        result = call_claude35_internal(request.json)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/nova', methods=['POST'])
def call_nova():
    data = request.json
    text = data.get('text', '')
    media = data.get('media', [])
    media_type = data.get('mediaType', 'image')
    max_tokens = data.get('max_tokens', 1024)
    temperature = data.get('temperature', 0.1)
    
    log_entry = {
        'time': datetime.now().isoformat(),
        'request': {'text': text, 'media_count': len(media), 'media_type': media_type, 'max_tokens': max_tokens, 'temperature': temperature}
    }
    
    try:
        import base64
        # Nova Pro model supports both images and videos
        if media_type == 'image':
            content = [{"text": text}]
            for img_base64 in media:
                content.append({
                    "image": {
                        "format": "jpeg",
                        "source": {"bytes": img_base64}
                    }
                })
        elif media_type == 'video':
            # 处理视频：提取关键帧并转换为图片格式
            if len(media) > 0:
                video_base64 = media[0]  # 假设只有一个视频文件
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
                    return jsonify({"error": "Failed to extract frames from video for Nova processing."}), 400
            else:
                return jsonify({"error": "No video data received for Nova."}), 400
        else:
            return jsonify({"error": "Unsupported media type"}), 400
        
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
        log_entry['response'] = response_body
        logging.info(json.dumps(log_entry, ensure_ascii=False))
        return jsonify(response_body)
        
    except Exception as e:
        log_entry['error'] = str(e)
        logging.error(json.dumps(log_entry, ensure_ascii=False))
        return jsonify({"error": str(e)}), 500

def call_emd_model_internal(data, model_key):
    """EMD model inference internal function"""
    text = data.get('text', '')
    frames = data.get('frames', [])
    media_type = data.get('mediaType', 'image')
    max_tokens = data.get('max_tokens', 1024)
    temperature = data.get('temperature', 0.1)
    
    if model_key not in EMD_MODELS:
        raise Exception(f"Unsupported EMD model: {model_key}")
    
    model_id = EMD_MODELS[model_key]
    
    log_entry = {
        'time': datetime.now().isoformat(),
        'request': {'text': text, 'frames_count': len(frames), 'media_type': media_type, 'max_tokens': max_tokens, 'temperature': temperature, 'model': model_id}
    }
    
    try:
        logging.info(f"🚀 Starting EMD inference for model {model_id}")
        
        # Try OpenAI client first (API endpoint)
        logging.info(f"🔍 Checking EMD OpenAI client availability...")
        openai_client = create_emd_openai_client()
        if openai_client:
            logging.info(f"✅ EMD OpenAI client available, proceeding with inference")
            return call_emd_via_openai(openai_client, data, model_id, log_entry)
        
        # Fallback to SageMaker client
        logging.info(f"🔍 Checking EMD SageMaker client availability...")
        sagemaker_client = create_emd_sagemaker_client(model_id)
        if sagemaker_client:
            logging.info(f"✅ EMD SageMaker client available, proceeding with inference")
            return call_emd_via_sagemaker(sagemaker_client, data, model_id, log_entry)
        
        # No client available - provide helpful error message
        logging.error(f"❌ No EMD client available for {model_id}")
        error_msg = f"EMD model {model_id} is not deployed yet. Please deploy the model first using: emd deploy --model-id {model_id} --instance-type g5.12xlarge --engine-type vllm --service-type sagemaker_realtime --model-tag dev"
        raise Exception(error_msg)
        
    except Exception as e:
        log_entry['error'] = str(e)
        logging.error(json.dumps(log_entry, ensure_ascii=False))
        raise Exception(str(e))

def call_emd_via_openai(client, data, model_id, log_entry):
    """Call EMD model via OpenAI API"""
    text = data.get('text', '')
    frames = data.get('frames', [])
    media_type = data.get('mediaType', 'image')
    max_tokens = data.get('max_tokens', 1024)
    temperature = data.get('temperature', 0.1)
    
    logging.info(f"🎯 Processing {media_type} input for EMD model {model_id}")
    messages = []
    
    if media_type == 'video':
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
        # Process images
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
    
    logging.info(f"🔥 Calling EMD OpenAI API for {model_id}/dev...")
    response = client.chat.completions.create(
        model=f"{model_id}/dev",
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature
    )
    
    logging.info(f"✅ EMD OpenAI API call completed for {model_id}")
    log_entry['response'] = response.model_dump()
    logging.info(json.dumps(log_entry, ensure_ascii=False))
    
    return {
        "content": [{"text": response.choices[0].message.content}],
        "usage": response.usage.model_dump() if response.usage else None
    }

def call_emd_via_sagemaker(client, data, model_id, log_entry):
    """Call EMD model via SageMaker SDK"""
    text = data.get('text', '')
    frames = data.get('frames', [])
    media_type = data.get('mediaType', 'image')
    max_tokens = data.get('max_tokens', 1024)
    temperature = data.get('temperature', 0.1)
    
    logging.info(f"🎯 Processing {media_type} input for EMD SageMaker model {model_id}")
    messages = []
    
    if media_type == 'video':
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
        # Process images
        logging.info(f"🖼️ Processing {len(frames)} images for EMD SageMaker model {model_id}")
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
    
    logging.info(f"🔥 Calling EMD SageMaker SDK for {model_id}...")
    response = client.invoke({"messages": messages})
    
    logging.info(f"✅ EMD SageMaker SDK call completed for {model_id}")
    log_entry['response'] = response
    logging.info(json.dumps(log_entry, ensure_ascii=False))
    
    return response

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
        result = subprocess.run(['emd', 'status'], capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({"status": "success", "output": result.stdout})
        else:
            return jsonify({"status": "error", "output": result.stderr}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/emd/models', methods=['GET'])
def emd_models():
    """Get available EMD models"""
    return jsonify({"models": EMD_MODELS})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 