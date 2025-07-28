# API Documentation

## Base URL
```
http://localhost:5000
```

## Authentication
- AWS credentials required for Bedrock models
- EMD authentication handled automatically via CLI

## Endpoints

### Bedrock Models

#### Claude 4 Inference
```http
POST /api/claude4
Content-Type: application/json

{
  "text": "What is in this image?",
  "frames": ["base64_encoded_image"],
  "max_tokens": 1024,
  "temperature": 0.1
}
```

#### Nova Inference
```http
POST /api/nova
Content-Type: application/json

{
  "text": "Analyze this video",
  "frames": ["base64_frame1", "base64_frame2"],
  "max_tokens": 1024,
  "temperature": 0.1
}
```

### EMD Models

#### EMD Model Inference
```http
POST /api/emd/{model_key}
Content-Type: application/json

{
  "text": "Describe this image",
  "frames": ["base64_encoded_image"],
  "mediaType": "image",
  "max_tokens": 1024,
  "temperature": 0.1
}
```

**Supported model_key values:**
- `qwen2-vl-7b`
- `qwen2.5-vl-32b`
- `gemma-3-4b`
- `ui-tars-1.5-7b`

#### EMD Status
```http
GET /api/emd/status
```

Returns deployment status of all EMD models.

#### EMD Models List
```http
GET /api/emd/models
```

Returns list of available EMD models and their deployment status.

### Multi-Model

#### Batch Inference
```http
POST /api/multi-inference
Content-Type: application/json

{
  "text": "What is in this image?",
  "frames": ["base64_encoded_image"],
  "mediaType": "image",
  "max_tokens": 100,
  "temperature": 0.1,
  "models": ["claude4", "qwen2-vl-7b", "nova"]
}
```

### Streaming

#### Real-time Inference
```http
POST /api/stream/{model_name}
Content-Type: application/json

{
  "text": "Describe this image",
  "frames": ["base64_encoded_image"],
  "max_tokens": 1024,
  "temperature": 0.1
}
```

## Response Format

### Success Response
```json
{
  "time": "2025-07-28T06:44:48.117281",
  "request": {
    "text": "What is in this image?",
    "frames_count": 1,
    "media_type": "image",
    "max_tokens": 100,
    "temperature": 0.1
  },
  "response": {
    "id": "msg_12345",
    "content": [{"type": "text", "text": "Response text"}],
    "usage": {"input_tokens": 17, "output_tokens": 34}
  }
}
```

### Error Response
```json
{
  "time": "2025-07-28T06:44:48.117281",
  "request": {...},
  "error": "EMD model not deployed. Please deploy using: emd deploy..."
}
```

## Error Codes

- `200` - Success
- `400` - Bad Request (invalid parameters)
- `500` - Internal Server Error (model/deployment issues)
- `503` - Service Unavailable (model not deployed)

## Rate Limits

- Bedrock models: AWS service limits apply
- EMD models: Based on deployed instance capacity
- Streaming: Connection-based limits

## Examples

### Python Example
```python
import requests
import base64

# Load and encode image
with open('image.jpg', 'rb') as f:
    image_b64 = base64.b64encode(f.read()).decode()

# Make inference request
response = requests.post('http://localhost:5000/api/claude4', json={
    'text': 'What is in this image?',
    'frames': [image_b64],
    'max_tokens': 1024,
    'temperature': 0.1
})

print(response.json())
```

### JavaScript Example
```javascript
const fileToBase64 = (file) => {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.readAsDataURL(file);
  });
};

const inferenceRequest = async (imageFile) => {
  const imageB64 = await fileToBase64(imageFile);
  
  const response = await fetch('/api/claude4', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      text: 'Analyze this image',
      frames: [imageB64],
      max_tokens: 1024,
      temperature: 0.1
    })
  });
  
  return response.json();
};
```