import React, { useState } from 'react';
import { Layout, Card, Button, Row, Col, message, Switch, Space, Typography } from 'antd';
import DatasetUploader from './components/DatasetUploader';
import BatchDatasetUploader from './components/BatchDatasetUploader';
import ModelSelector from './components/ModelSelector';
import ParamConfigurator from './components/ParamConfigurator';
import TaskRunner from './components/TaskRunner';
import ResultsDisplay from './components/ResultsDisplay';
import StreamingResultsDisplay from './components/StreamingResultsDisplay';
import 'antd/dist/reset.css';

const { Header, Content } = Layout;

function App() {
  const [dataset, setDataset] = useState({ type: 'image', files: [], prompt: '' });
  const [selectedModels, setSelectedModels] = useState([]);
  const [params, setParams] = useState({ max_tokens: 1024, temperature: 0.1 });
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState({});
  const [useStreaming, setUseStreaming] = useState(true);

  // 将图片文件转为base64
  const filesToBase64 = (files) => {
    return Promise.all(
      files.map(
        (file) =>
          new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(',')[1]);
            reader.onerror = reject;
            reader.readAsDataURL(file);
          })
      )
    );
  };

  const handleRun = async () => {
    console.log('handleRun called');
    console.log('dataset:', dataset);
    console.log('selectedModels:', selectedModels);
    
    if (!dataset.files || dataset.files.length === 0) {
      message.error('请先上传图片或视频');
      return;
    }
    if (selectedModels.length === 0) {
      message.error('请选择至少一个模型');
      return;
    }
    if (!dataset.prompt) {
      message.error('请输入Prompt');
      return;
    }
    setLoading(true);
    setResults({});
    
    console.log('Starting evaluation...');

    // 初始化所有模型的loading状态
    const initialResults = {};
    for (const modelName of selectedModels) {
      initialResults[modelName] = {
        status: 'loading',
        message: '正在处理中...',
        metadata: { processingTime: 'N/A' }
      };
    }
    setResults(initialResults);
    
    // 并发处理所有选中的模型
    const modelPromises = selectedModels.map(async (modelName) => {
      try {
        if ((modelName === 'Claude3.5' || modelName === 'Claude4') && (dataset.type === 'image' || dataset.type === 'video')) {
          console.log(`Processing ${modelName} with ${dataset.files.length} ${dataset.type}(s)`);
          const base64Data = await filesToBase64(dataset.files);
          const endpoint = modelName === 'Claude4' ? '/api/claude4' : '/api/claude35';
          
          console.log(`Calling ${endpoint}`);
          const startTime = Date.now();
          const resp = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: dataset.prompt,
              frames: base64Data,
              mediaType: dataset.type,
              max_tokens: params.max_tokens || 1024,
              temperature: params.temperature || 0.1
            })
          });
          const endTime = Date.now();
          const processingTime = ((endTime - startTime) / 1000).toFixed(2) + 's';
          
          console.log(`Response status: ${resp.status}, Processing time: ${processingTime}`);
          
          const data = await resp.json();
          if (data.error) {
            const errorResult = {
              status: 'error',
              error: data.error,
              metadata: { processingTime: processingTime }
            };
            setResults(prevResults => ({ ...prevResults, [modelName]: errorResult }));
            return { modelName, result: errorResult };
          } else {
            // Extract token count from Claude API response
            const inputTokens = data.usage?.input_tokens || 0;
            const outputTokens = data.usage?.output_tokens || 0;
            const totalTokens = inputTokens + outputTokens;
            
            const successResult = {
              status: 'success',
              response: data,
              metadata: {
                processingTime: processingTime,
                tokens: totalTokens > 0 ? `${totalTokens} (${inputTokens}+${outputTokens})` : 'N/A',
                modelVersion: data.model || modelName
              }
            };
            setResults(prevResults => ({ ...prevResults, [modelName]: successResult }));
            return { modelName, result: successResult };
          }
        } else if (modelName === 'Nova Pro' && (dataset.type === 'image' || dataset.type === 'video')) {
          const base64Data = await filesToBase64(dataset.files);
          
          const startTime = Date.now();
          const resp = await fetch('/api/nova', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: dataset.prompt,
              media: base64Data,
              mediaType: dataset.type,
              max_tokens: params.max_tokens || 1024,
              temperature: params.temperature || 0.1
            })
          });
          const endTime = Date.now();
          const processingTime = ((endTime - startTime) / 1000).toFixed(2) + 's';
          
          const data = await resp.json();
          if (data.error) {
            const errorResult = {
              status: 'error',
              error: data.error,
              metadata: { processingTime: processingTime }
            };
            setResults(prevResults => ({ ...prevResults, [modelName]: errorResult }));
            return { modelName, result: errorResult };
          } else {
            // Extract token count from Nova API response  
            const inputTokens = data.usage?.inputTokens || 0;
            const outputTokens = data.usage?.outputTokens || 0;
            const totalTokens = inputTokens + outputTokens;
            
            const successResult = {
              status: 'success',
              response: data,
              metadata: {
                processingTime: processingTime,
                tokens: totalTokens > 0 ? `${totalTokens} (${inputTokens}+${outputTokens})` : 'N/A',
                modelVersion: modelName
              }
            };
            setResults(prevResults => ({ ...prevResults, [modelName]: successResult }));
            return { modelName, result: successResult };
          }
        } else if (['qwen2-vl-7b', 'qwen2.5-vl-32b', 'gemma-3-4b', 'ui-tars-1.5-7b'].includes(modelName) && (dataset.type === 'image' || dataset.type === 'video')) {
          // EMD models handling
          const base64Data = await filesToBase64(dataset.files);
          
          const startTime = Date.now();
          const resp = await fetch(`/api/emd/${modelName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: dataset.prompt,
              frames: base64Data,
              mediaType: dataset.type,
              max_tokens: params.max_tokens || 1024,
              temperature: params.temperature || 0.1
            })
          });
          const endTime = Date.now();
          const processingTime = ((endTime - startTime) / 1000).toFixed(2) + 's';
          
          const data = await resp.json();
          if (data.error) {
            let errorMessage = data.error;
            let errorType = 'error';
            
            // Check if this is an EMD deployment error
            if (data.error.includes('not deployed yet') || data.error.includes('No EMD client available')) {
              errorType = 'deployment_needed';
              errorMessage = `${modelName} 模型未部署。请先部署模型后再使用。`;
            }
            
            const errorResult = {
              status: 'error',
              error: errorMessage,
              errorType: errorType,
              metadata: { processingTime: processingTime }
            };
            setResults(prevResults => ({ ...prevResults, [modelName]: errorResult }));
            return { modelName, result: errorResult };
          } else {
            // Extract token count from EMD API response
            const inputTokens = data.usage?.prompt_tokens || 0;
            const outputTokens = data.usage?.completion_tokens || 0;
            const totalTokens = data.usage?.total_tokens || (inputTokens + outputTokens);
            
            const successResult = {
              status: 'success',
              response: data,
              metadata: {
                processingTime: processingTime,
                tokens: totalTokens > 0 ? `${totalTokens} (${inputTokens}+${outputTokens})` : 'N/A',
                modelVersion: modelName
              }
            };
            setResults(prevResults => ({ ...prevResults, [modelName]: successResult }));
            return { modelName, result: successResult };
          }
        } else {
          const errorResult = {
            status: 'error',
            error: `${modelName} 暂不支持 ${dataset.type} 类型的输入`,
            metadata: { processingTime: 'N/A' }
          };
          setResults(prevResults => ({ ...prevResults, [modelName]: errorResult }));
          return { modelName, result: errorResult };
        }
      } catch (e) {
        const errorResult = {
          status: 'error',
          error: `网络请求失败: ${e.message}`,
          metadata: { processingTime: 'N/A' }
        };
        setResults(prevResults => ({ ...prevResults, [modelName]: errorResult }));
        return { modelName, result: errorResult };
      }
    });
    
    // 等待所有模型处理完成
    await Promise.all(modelPromises);
    setLoading(false);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ color: '#fff', fontSize: 20 }}>多模态大模型评测平台</Header>
      <Content style={{ padding: 24 }}>
        <Row gutter={24}>
          <Col span={8}>
            <Card title="1. 上传数据集" bordered={false}>
              <DatasetUploader onChange={setDataset} />
            </Card>
          </Col>
          <Col span={8}>
            <Card title="2. 选择模型" bordered={false}>
              <ModelSelector value={selectedModels} onChange={setSelectedModels} />
            </Card>
          </Col>
          <Col span={8}>
            <Card title="3. 配置参数" bordered={false}>
              <ParamConfigurator value={params} onChange={setParams} />
            </Card>
          </Col>
        </Row>
        <Row justify="center" style={{ marginTop: 32 }}>
          <Space>
            <Switch 
              checked={useStreaming} 
              onChange={setUseStreaming}
              checkedChildren="流式" 
              unCheckedChildren="批量"
            />
            {!useStreaming && (
              <Button type="primary" size="large" loading={loading} onClick={handleRun}>
                4. 发起评测
              </Button>
            )}
          </Space>
        </Row>
        
        {useStreaming ? (
          <StreamingResultsDisplay 
            dataset={dataset}
            selectedModels={selectedModels}
            params={params}
            onStreamComplete={(streamResults) => {
              console.log('Stream completed:', streamResults);
              setResults(streamResults);
            }}
          />
        ) : (
          <ResultsDisplay results={results} loading={loading} />
        )}
        
        <TaskRunner />
      </Content>
    </Layout>
  );
}

export default App;
