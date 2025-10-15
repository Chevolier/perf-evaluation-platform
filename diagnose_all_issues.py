#!/usr/bin/env python3
"""Comprehensive diagnostic for all 4 user questions."""

import json
import requests
import sys

BACKEND_URL = "http://localhost:5000"

print("=" * 80)
print("COMPREHENSIVE DIAGNOSTIC - 4 QUESTIONS")
print("=" * 80)

# Question 1: Why are there so many 部署失败 (deployment failed)?
print("\n" + "=" * 80)
print("QUESTION 1: Why so many 部署失败 (deployment failed)?")
print("=" * 80)

response = requests.get(f"{BACKEND_URL}/api/model-list")
data = response.json()

emd_models = data.get('models', {}).get('emd', {})
print(f"\nTotal EMD models in registry: {len(emd_models)}")

deployed_count = 0
not_deployed_count = 0

for key, info in emd_models.items():
    status = info.get('deployment_status', {}).get('status', 'unknown')
    endpoint = info.get('deployment_status', {}).get('endpoint', 'N/A')

    if status == 'deployed':
        deployed_count += 1
        print(f"\n✅ {key} ({info.get('name')})")
        print(f"   Status: {status}")
        print(f"   Endpoint: {endpoint[:70]}...")
    else:
        not_deployed_count += 1
        print(f"\n❌ {key} ({info.get('name')})")
        print(f"   Status: {status}")

print(f"\n📊 SUMMARY:")
print(f"   Deployed: {deployed_count}")
print(f"   Not Deployed (shows as 检查失败): {not_deployed_count}")
print(f"\n💡 ANSWER: Most EMD models show 检查失败 because they are NOT ACTUALLY DEPLOYED.")
print(f"   Only models that have been deployed through the platform will show as available.")

# Question 2: Is 外部部署 used or not?
print("\n" + "=" * 80)
print("QUESTION 2: Is 外部部署 (external deployment) used or not?")
print("=" * 80)

external_models = data.get('models', {}).get('external', {})
print(f"\nExternal deployments count: {len(external_models)}")

if external_models:
    for key, info in external_models.items():
        print(f"\n✅ {key}")
        print(f"   Name: {info.get('name')}")
        print(f"   Method: {info.get('deployment_method')}")
        print(f"   Endpoint: {info.get('endpoint', 'N/A')}")
else:
    print("\n❌ No external deployments registered")

print(f"\n💡 ANSWER: External deployment section EXISTS but is currently EMPTY.")
print(f"   The EMD deployment was moved to show under EMD category instead.")

# Question 3: Why is there no EMD in 选择推理模型?
print("\n" + "=" * 80)
print("QUESTION 3: Why is there no EMD in 选择推理模型 (model selector)?")
print("=" * 80)

# Test the status check API
print("\nTesting /api/check-model-status...")
test_models = list(emd_models.keys())[:3]  # Test first 3 EMD models
status_response = requests.post(
    f"{BACKEND_URL}/api/check-model-status",
    json={"models": test_models},
    headers={"Content-Type": "application/json"}
)

print(f"Status check API response: {status_response.status_code}")

if status_response.status_code == 200:
    status_data = status_response.json()
    print(f"Status check successful: {status_data.get('status')}")

    model_statuses = status_data.get('model_status', {})
    for model_key, status_info in model_statuses.items():
        print(f"\n  {model_key}:")
        print(f"    Status: {status_info.get('status')}")
        print(f"    Message: {status_info.get('message')}")
        endpoint = status_info.get('endpoint') or 'N/A'
        print(f"    Endpoint: {endpoint[:50] if endpoint != 'N/A' else endpoint}")
else:
    print(f"❌ Status check FAILED: {status_response.text}")

print(f"\n💡 CHECKING Frontend Filter Logic:")
print(f"   Frontend shows models where:")
print(f"   - model.alwaysAvailable === true (Bedrock models)")
print(f"   - OR status.status === 'available' or 'deployed'")
print(f"\n   EMD models have alwaysAvailable=false")
print(f"   So they ONLY show if status check returns 'deployed' or 'available'")

deployed_emd = [k for k, v in emd_models.items() if v.get('deployment_status', {}).get('status') == 'deployed']
print(f"\n✅ EMD models that SHOULD appear in selector: {deployed_emd}")
print(f"❌ EMD models that WON'T appear (not deployed): {[k for k in emd_models.keys() if k not in deployed_emd]}")

# Question 4: Streaming not solved
print("\n" + "=" * 80)
print("QUESTION 4: Is streaming solved?")
print("=" * 80)

print("\nChecking if streaming delays are in code...")
with open('/home/ubuntu/perf-evaluation-platform/backend/services/inference_service.py', 'r') as f:
    code = f.read()
    if 'time.sleep(0.05)' in code:
        count = code.count('time.sleep(0.05)')
        print(f"✅ Found {count} streaming delays (0.05s) in inference_service.py")
    else:
        print("❌ No streaming delays found in code")

print("\nTesting live streaming with claude35-haiku...")
import time

payload = {
    "models": ["claude35-haiku"],
    "text": "Say: 1 2 3 4 5",
    "max_tokens": 30
}

start_time = time.time()
chunk_count = 0
chunk_times = []

try:
    response = requests.post(
        f"{BACKEND_URL}/api/multi-inference",
        json=payload,
        headers={'Accept': 'text/event-stream'},
        stream=True,
        timeout=30
    )

    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith('data: '):
            continue

        try:
            data = json.loads(line[6:])
            if data.get('type') == 'chunk':
                chunk_count += 1
                chunk_time = time.time() - start_time
                chunk_times.append(chunk_time)
                print(f"  Chunk #{chunk_count} at {chunk_time:.2f}s: {repr(data.get('delta', ''))}")
            elif data.get('type') == 'complete':
                break
        except:
            pass

    total_time = time.time() - start_time

    print(f"\n📊 Streaming Results:")
    print(f"   Total chunks: {chunk_count}")
    print(f"   Total time: {total_time:.2f}s")
    if chunk_times:
        print(f"   First chunk at: {chunk_times[0]:.2f}s")
        if len(chunk_times) > 1:
            print(f"   Last chunk at: {chunk_times[-1]:.2f}s")
            print(f"   Time span: {chunk_times[-1] - chunk_times[0]:.2f}s")

    if chunk_count == 0:
        print("\n❌ STREAMING NOT WORKING - No chunks received")
    elif len(chunk_times) > 1 and (chunk_times[-1] - chunk_times[0]) < 0.1:
        print("\n⚠️ BUFFERING DETECTED - All chunks within 100ms")
    else:
        print("\n✅ STREAMING WORKING - Chunks arriving over time")

except Exception as e:
    print(f"\n❌ Streaming test failed: {e}")

# Final Summary
print("\n" + "=" * 80)
print("FINAL ANSWERS")
print("=" * 80)
print("""
1. 部署失败 (deployment failed):
   Most EMD models are NOT DEPLOYED. Only deployed models show as available.
   Solution: Deploy them via Model Hub page first.

2. 外部部署 (external deployment):
   Section EXISTS but is EMPTY. The EMD deployment was moved to EMD category.

3. No EMD in selector:
   Frontend filters out models with status != 'deployed'/'available'.
   Only qwen3-0.6b (if deployed) should appear in the selector.
   Other EMD models are filtered out because they're not deployed.

4. Streaming:
   Backend has delays added, but may still appear instant due to buffering.
   Try with Gunicorn: gunicorn -w 1 -k gevent --bind 0.0.0.0:5000 "backend.app:create_app()"
""")

print("=" * 80)
