#!/usr/bin/env python3
"""
流式多模态推理API
支持多模型并发推理和实时结果返回
"""

from flask import Flask, request, Response
from flask_cors import CORS
import json
import threading
import queue
import time
from datetime import datetime
import requests
import logging

app = Flask(__name__)
CORS(app)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def call_model_api(model_name, endpoint, data):
    """调用单个模型的API"""
    try:
        start_time = time.time()
        response = requests.post(
            f"http://localhost:5000{endpoint}",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=300
        )
        
        processing_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            return {
                'model': model_name,
                'status': 'success',
                'processing_time': round(processing_time, 2),
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
        else:
            return {
                'model': model_name,
                'status': 'error',
                'processing_time': round(processing_time, 2),
                'error': f"HTTP {response.status_code}: {response.text}",
                'timestamp': datetime.now().isoformat()
            }
    except Exception as e:
        return {
            'model': model_name,
            'status': 'error',
            'processing_time': 0,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def model_worker(model_config, data, result_queue):
    """模型推理工作线程"""
    try:
        logging.info(f"开始处理模型: {model_config['name']}")
        result = call_model_api(
            model_config['name'],
            model_config['endpoint'],
            data
        )
        logging.info(f"模型 {model_config['name']} 处理完成: {result['status']}")
        result_queue.put(result)
    except Exception as e:
        logging.error(f"模型 {model_config['name']} 处理异常: {e}")
        result_queue.put({
            'model': model_config['name'],
            'status': 'error',
            'error': str(e),
            'processing_time': 0
        })

@app.route('/api/stream-inference', methods=['POST', 'GET'])
def stream_inference():
    """流式多模型推理接口"""
    if request.method == 'GET':
        # 从查询参数获取数据（用于EventSource）
        data_param = request.args.get('data')
        if data_param:
            data = json.loads(data_param)
        else:
            return Response('Missing data parameter', status=400)
    else:
        data = request.json
    
    # 模型配置
    models = [
        {'name': 'Claude 4', 'endpoint': '/api/claude4'},
        {'name': 'Claude 3.5', 'endpoint': '/api/claude35'},
        {'name': 'Nova Pro', 'endpoint': '/api/nova'},
        # EMD models
        {'name': 'qwen2-vl-7b', 'endpoint': '/api/emd/qwen2-vl-7b'},
        {'name': 'qwen2.5-vl-32b', 'endpoint': '/api/emd/qwen2.5-vl-32b'},
        {'name': 'gemma-3-4b', 'endpoint': '/api/emd/gemma-3-4b'},
        {'name': 'ui-tars-1.5-7b', 'endpoint': '/api/emd/ui-tars-1.5-7b'}
    ]
    
    # 允许客户端选择模型
    selected_models = data.get('models', ['Claude 4', 'Claude 3.5', 'Nova Pro'])
    active_models = [m for m in models if m['name'] in selected_models]
    
    def generate():
        """生成器函数，用于流式返回结果"""
        result_queue = queue.Queue()
        threads = []
        
        # 发送开始信号
        yield f"data: {json.dumps({'type': 'start', 'models': [m['name'] for m in active_models]}, ensure_ascii=False)}\n\n"
        
        # 启动所有模型的推理线程
        logging.info(f"准备启动 {len(active_models)} 个模型的线程")
        for model_config in active_models:
            logging.info(f"启动线程: {model_config['name']}")
            thread = threading.Thread(
                target=model_worker,
                args=(model_config, data, result_queue)
            )
            threads.append(thread)
            thread.start()
            
            # 发送模型开始处理信号
            yield f"data: {json.dumps({'type': 'model_start', 'model': model_config['name']}, ensure_ascii=False)}\n\n"
        
        # 收集结果
        completed = 0
        total_models = len(active_models)
        
        while completed < total_models:
            try:
                # 等待结果，1秒超时
                result = result_queue.get(timeout=1)
                completed += 1
                
                # 发送模型结果
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                
                logging.info(f"模型 {result['model']} 完成，状态: {result['status']}, 用时: {result.get('processing_time', 0)}秒")
                
            except queue.Empty:
                # 发送心跳信号
                yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 发送完成信号
        yield f"data: {json.dumps({'type': 'complete', 'completed_models': completed})}\n\n"
    
    return Response(
        generate(),
        mimetype='text/plain',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    )

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)