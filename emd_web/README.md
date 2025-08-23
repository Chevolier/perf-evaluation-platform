# EMD Web API 使用说明

## 概述

EMD Web API 是一个基于 FastAPI 构建的模型部署管理服务，提供模型部署、状态查询和销毁功能。该服务集成了 EMD SDK，支持在 AWS SageMaker 等平台上部署和管理机器学习模型。

## 启动服务

```bash
cd emd_web
python main.py
```

服务将在 `http://localhost:3000` 启动。

## 访问测试页面

服务启动后，你可以通过以下方式访问集成的 Web 测试界面：

- **主页**: `http://localhost:3000/`
- **测试页面**: `http://localhost:3000/test`

无需单独打开 HTML 文件，所有功能都集成在同一个服务器中。

## 特性

- **跨域支持**: 已配置 CORS 中间件，支持跨域请求
- **RESTful API**: 提供标准的 REST API 接口
- **模型生命周期管理**: 支持模型部署、状态监控和销毁
- **灵活配置**: 支持多种框架类型和部署参数
- **Web 测试界面**: 提供友好的 HTML 测试页面

## API 端点

### 1. 健康检查 - GET /ping

检查 API 服务是否正常运行。

**请求示例:**
```bash
curl -X GET "http://localhost:3000/ping"
```

**响应示例:**
```json
{
  "success": true,
  "message": "EMD Web API is running"
}
```

### 2. 部署模型 - POST /emd_deploy

使用指定配置部署模型到 AWS SageMaker 或其他平台。

**请求参数:**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| model_id | string | 是 | - | 模型唯一标识符 (如: Qwen3-8B) |
| instance_type | string | 是 | - | AWS 实例类型 (如: g5.2xlarge) |
| engine_type | string | 是 | - | 推理引擎类型 (如: vllm) |
| service_type | string | 是 | - | 服务类型 (如: sagemaker) |
| framework_type | string | 否 | "fastapi" | 框架类型 (fastapi/flask/django) |
| model_tag | string | 否 | "dev" | 模型标签 |
| region | string | 否 | - | AWS 区域 (如: us-east-1) |
| model_stack_name | string | 否 | - | CloudFormation 堆栈名称 |
| extra_params | object | 否 | - | 额外配置参数 |
| env_stack_on_failure | string | 否 | "ROLLBACK" | 失败时的堆栈行为 |
| force_env_stack_update | boolean | 否 | false | 是否强制更新堆栈 |

**请求示例:**
```bash
curl -X POST "http://localhost:3000/emd_deploy" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "Qwen3-8B",
    "instance_type": "g5.2xlarge",
    "engine_type": "vllm",
    "service_type": "sagemaker",
    "framework_type": "fastapi",
    "model_tag": "dev",
    "region": "us-east-1",
    "model_stack_name": "qwen3-8b-stack",
    "extra_params": {
      "max_tokens": 2048,
      "temperature": 0.7
    }
  }'
```

**响应示例:**
```json
{
  "success": true,
  "message": "Deployment initiated successfully",
  "deployment_config": {
    "model_id": "Qwen3-8B",
    "instance_type": "g5.2xlarge",
    "engine_type": "vllm",
    "service_type": "sagemaker",
    "framework_type": "fastapi",
    "model_tag": "dev",
    "region": "us-east-1",
    "model_stack_name": "qwen3-8b-stack",
    "extra_params": {
      "max_tokens": 2048,
      "temperature": 0.7
    },
    "env_stack_on_failure": "ROLLBACK",
    "force_env_stack_update": false,
    "waiting_until_deploy_complete": false,
    "dockerfile_local_path": null
  }
}
```

### 3. 获取模型状态 - POST /emd_status

检索指定模型的当前部署状态。

**请求参数:**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| model_id | string | 是 | - | 模型唯一标识符 |
| model_tag | string | 否 | "dev" | 模型标签 |

**请求示例:**
```bash
curl -X POST "http://localhost:3000/emd_status" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "Qwen3-8B",
    "model_tag": "dev"
  }'
```

**响应示例:**
```json
{
  "status": "InService",
  "endpoint_name": "Qwen3-8B-dev-endpoint",
  "endpoint_url": "https://runtime.sagemaker.us-east-1.amazonaws.com/endpoints/Qwen3-8B-dev-endpoint/invocations",
  "instance_type": "g5.2xlarge",
  "instance_count": 1,
  "creation_time": "2024-01-15T10:30:00Z",
  "last_modified_time": "2024-01-15T10:35:00Z"
}
```

### 4. 销毁模型 - POST /emd_destroy

销毁指定的模型部署，释放相关资源。

**请求参数:**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| model_id | string | 是 | - | 模型唯一标识符 |
| model_tag | string | 否 | "dev" | 模型标签 |

**请求示例:**
```bash
curl -X POST "http://localhost:3000/emd_destroy" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "Qwen3-8B",
    "model_tag": "dev"
  }'
```

**响应示例:**
```json
{
  "success": true
}
```

### 5. 获取支持的模型列表 - POST /emd_supported_models

获取 EMD 支持的所有模型列表（基础信息）。

**请求参数:**

无需参数。

**请求示例:**
```bash
curl -X POST "http://localhost:3000/emd_supported_models" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**响应示例:**
```json
{
  "Qwen3-8B": {
    "model_id": "Qwen3-8B",
    "model_name": "Qwen3 8B",
    "provider": "Alibaba",
    "supported_engines": ["vllm", "transformers"],
    "supported_instance_types": ["g5.2xlarge", "g5.4xlarge", "g5.12xlarge"]
  },
  "Llama-3.1-8B": {
    "model_id": "Llama-3.1-8B",
    "model_name": "Llama 3.1 8B",
    "provider": "Meta",
    "supported_engines": ["vllm", "transformers"],
    "supported_instance_types": ["g5.2xlarge", "g5.4xlarge", "g5.12xlarge"]
  }
}
```

### 6. 获取模型详细信息 - POST /emd_details

获取指定模型的详细信息。

**请求参数:**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| model_id | string | 是 | - | 模型唯一标识符 |
| detail | boolean | 否 | false | 是否返回详细信息 |

**请求示例:**
```bash
curl -X POST "http://localhost:3000/emd_details" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "Qwen3-8B",
    "detail": true
  }'
```

**响应示例:**
```json
{
  "Qwen3-8B": {
    "model_id": "Qwen3-8B",
    "model_name": "Qwen3 8B",
    "provider": "Alibaba",
    "model_size": "8B",
    "context_length": 32768,
    "supported_engines": ["vllm", "transformers"],
    "supported_instance_types": ["g5.2xlarge", "g5.4xlarge", "g5.12xlarge"],
    "recommended_instance_type": "g5.2xlarge",
    "memory_requirements": "16GB",
    "description": "Qwen3-8B 是阿里巴巴开发的大型语言模型",
    "capabilities": ["text-generation", "chat", "code-generation"],
    "license": "Apache-2.0"
  }
}
```

### 7. 列出已部署的模型 - POST /emd_models

获取所有已部署模型的状态信息，包括正在进行中和已完成的部署。

**请求参数:**

无需参数。

**请求示例:**
```bash
curl -X POST "http://localhost:3000/emd_models" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**响应示例:**
```json
[
  {
    "model_id": "Qwen3-8B",
    "model_tag": "dev",
    "status": "InService",
    "service_type": "sagemaker",
    "instance_type": "g5.2xlarge",
    "create_time": "2024-01-15T10:30:00Z",
    "outputs": {
      "endpoint_name": "Qwen3-8B-dev-endpoint",
      "endpoint_url": "https://runtime.sagemaker.us-east-1.amazonaws.com/endpoints/Qwen3-8B-dev-endpoint/invocations"
    }
  },
  {
    "model_id": "Llama-3.1-8B",
    "model_tag": "prod",
    "status": "Creating (Infrastructure)",
    "service_type": "sagemaker",
    "instance_type": "g5.4xlarge",
    "create_time": "2024-01-15T11:00:00Z",
    "outputs": {}
  }
]
```

## 使用测试页面

测试页面提供了友好的 Web 界面来测试所有 API 端点。

### 启动步骤：

1. **启动 API 服务**：
   ```bash
   cd emd_web
   python main.py
   ```

2. **访问测试页面**：
   在浏览器中访问以下任一地址：
   - 主页: `http://localhost:3000/`
   - 测试页面: `http://localhost:3000/test`

3. **开始测试**：
   - 页面会自动配置正确的 API URL
   - 点击"测试 Ping"验证服务连接
   - 使用"填充示例数据"快速填充表单
   - 测试部署、状态查询和销毁功能

### 测试页面特性：

- **响应式设计**: 支持桌面和移动设备
- **实时响应显示**: JSON 格式化显示 API 响应
- **错误处理**: 区分成功和错误状态
- **示例数据**: 一键填充常用测试数据
- **参数验证**: 前端验证必需参数

## Python 客户端示例

```python
import requests
import json

# API 基础URL
BASE_URL = "http://localhost:3000"

class EMDClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url.rstrip('/')
    
    def ping(self):
        """健康检查"""
        response = requests.get(f"{self.base_url}/ping")
        return response.json()
    
    def deploy_model(self, model_id, instance_type, engine_type, service_type, **kwargs):
        """部署模型"""
        url = f"{self.base_url}/emd_deploy"
        data = {
            "model_id": model_id,
            "instance_type": instance_type,
            "engine_type": engine_type,
            "service_type": service_type,
            **kwargs
        }
        
        response = requests.post(url, json=data)
        return response.json()
    
    def get_model_status(self, model_id, model_tag="dev"):
        """获取模型状态"""
        url = f"{self.base_url}/emd_status"
        data = {
            "model_id": model_id,
            "model_tag": model_tag
        }
        
        response = requests.post(url, json=data)
        return response.json()
    
    def destroy_model(self, model_id, model_tag="dev"):
        """销毁模型"""
        url = f"{self.base_url}/emd_destroy"
        data = {
            "model_id": model_id,
            "model_tag": model_tag
        }
        
        response = requests.post(url, json=data)
        return response.json()
    
    def get_supported_models(self):
        """获取支持的模型列表"""
        url = f"{self.base_url}/emd_supported_models"
        response = requests.post(url, json={})
        return response.json()
    
    def get_model_details(self, model_id, detail=False):
        """获取模型详细信息"""
        url = f"{self.base_url}/emd_details"
        data = {
            "model_id": model_id,
            "detail": detail
        }
        
        response = requests.post(url, json=data)
        return response.json()
    
    def list_models(self):
        """列出已部署的模型"""
        url = f"{self.base_url}/emd_models"
        response = requests.post(url, json={})
        return response.json()

# 使用示例
if __name__ == "__main__":
    client = EMDClient()
    
    # 健康检查
    print("健康检查:", client.ping())
    
    # 部署模型
    deploy_result = client.deploy_model(
        model_id="Qwen3-8B",
        instance_type="g5.2xlarge",
        engine_type="vllm",
        service_type="sagemaker",
        region="us-east-1",
        extra_params={"max_tokens": 2048}
    )
    print("部署结果:", deploy_result)
    
    # 获取状态
    status_result = client.get_model_status("Qwen3-8B")
    print("状态结果:", status_result)
    
    # 销毁模型
    destroy_result = client.destroy_model("Qwen3-8B")
    print("销毁结果:", destroy_result)
```

## JavaScript 客户端示例

```javascript
class EMDClient {
    constructor(baseUrl = "http://localhost:3000") {
        this.baseUrl = baseUrl.replace(/\/$/, '');
    }

    async makeRequest(endpoint, method = 'GET', body = null) {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            }
        };
        
        if (body) {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, options);
        return await response.json();
    }

    async ping() {
        return await this.makeRequest('/ping', 'GET');
    }

    async deployModel(config) {
        return await this.makeRequest('/emd_deploy', 'POST', config);
    }

    async getModelStatus(modelId, modelTag = 'dev') {
        return await this.makeRequest('/emd_status', 'POST', {
            model_id: modelId,
            model_tag: modelTag
        });
    }

    async destroyModel(modelId, modelTag = 'dev') {
        return await this.makeRequest('/emd_destroy', 'POST', {
            model_id: modelId,
            model_tag: modelTag
        });
    }

    async getSupportedModels() {
        return await this.makeRequest('/emd_supported_models', 'POST', {});
    }

    async getModelDetails(modelId, detail = false) {
        return await this.makeRequest('/emd_details', 'POST', {
            model_id: modelId,
            detail: detail
        });
    }

    async listModels() {
        return await this.makeRequest('/emd_models', 'POST', {});
    }
}

// 使用示例
async function example() {
    const client = new EMDClient();
    
    try {
        // 健康检查
        const pingResult = await client.ping();
        console.log('健康检查:', pingResult);
        
        // 部署模型
        const deployResult = await client.deployModel({
            model_id: "Qwen3-8B",
            instance_type: "g5.2xlarge",
            engine_type: "vllm",
            service_type: "sagemaker",
            region: "us-east-1"
        });
        console.log('部署结果:', deployResult);
        
        // 获取状态
        const statusResult = await client.getModelStatus("Qwen3-8B");
        console.log('状态结果:', statusResult);
        
    } catch (error) {
        console.error('API 调用错误:', error);
    }
}

// 运行示例
example();
```

## 常见用例

### 1. 部署 Qwen 模型

```python
client = EMDClient()

# 部署 Qwen3-8B 模型
result = client.deploy_model(
    model_id="Qwen3-8B",
    instance_type="g5.2xlarge",
    engine_type="vllm",
    service_type="sagemaker",
    region="us-east-1",
    framework_type="fastapi"
)
```

### 2. 监控部署状态

```python
import time

def wait_for_deployment(client, model_id, model_tag="dev", timeout=1800):
    """等待部署完成"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status = client.get_model_status(model_id, model_tag)
        
        if status.get("status") == "InService":
            print(f"模型 {model_id} 部署成功!")
            return status
        elif status.get("status") == "Failed":
            print(f"模型 {model_id} 部署失败!")
            return status
        
        print(f"部署中... 状态: {status.get('status', 'Unknown')}")
        time.sleep(30)
    
    print("部署超时!")
    return None
```

### 3. 批量管理模型

```python
def manage_models(client, models_config):
    """批量管理多个模型"""
    results = {}
    
    for model_config in models_config:
        model_id = model_config["model_id"]
        
        try:
            # 部署模型
            deploy_result = client.deploy_model(**model_config)
            results[model_id] = {
                "deploy": deploy_result,
                "status": "deploying"
            }
            
        except Exception as e:
            results[model_id] = {
                "error": str(e),
                "status": "failed"
            }
    
    return results
```

## 错误处理

### HTTP 状态码

- `200`: 请求成功
- `400`: 请求参数错误
- `404`: 资源未找到
- `422`: 请求参数验证失败
- `500`: 服务器内部错误

### 错误响应格式

```json
{
  "detail": [
    {
      "loc": ["body", "model_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 常见错误及解决方案

1. **CORS 错误**: 确保服务已启动且 CORS 中间件已配置
2. **参数缺失**: 检查必需参数是否都已提供
3. **实例类型无效**: 使用有效的 AWS 实例类型
4. **权限错误**: 确保 AWS 凭证配置正确
5. **资源限制**: 检查 AWS 账户的资源配额

## 最佳实践

### 1. 安全性

- 在生产环境中限制 CORS 允许的域名
- 使用 HTTPS 协议
- 实施 API 密钥认证
- 定期轮换 AWS 凭证

### 2. 性能优化

- 使用适当的实例类型
- 监控资源使用情况
- 实施请求限流
- 缓存频繁查询的状态信息

### 3. 监控和日志

- 记录所有 API 调用
- 监控部署状态变化
- 设置告警机制
- 定期检查资源使用情况

## 依赖项

### Python 包

```bash
pip install fastapi uvicorn requests
```

### EMD SDK

根据实际情况安装 EMD SDK：

```bash
# 示例安装命令（具体命令可能不同）
pip install emd-sdk
```

### AWS 配置

确保 AWS 凭证已正确配置：

```bash
aws configure
```

或设置环境变量：

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

## 故障排除

### 1. 服务无法启动

- 检查端口 3000 是否被占用
- 确认所有依赖包已安装
- 检查 Python 版本兼容性

### 2. API 调用失败

- 验证 API URL 是否正确
- 检查请求参数格式
- 查看服务器日志

### 3. 部署失败

- 检查 AWS 凭证配置
- 验证实例类型可用性
- 确认账户权限和配额

### 4. CORS 问题

- 确保服务已启动
- 检查浏览器控制台错误
- 验证 CORS 中间件配置

## 版本信息

- **API 版本**: 1.0.0
- **FastAPI 版本**: 建议使用最新稳定版
- **Python 版本**: 3.8+

## 联系支持

如遇到问题，请检查：
1. 服务日志输出
2. AWS CloudFormation 控制台
3. SageMaker 端点状态
4. 网络连接和防火墙设置
