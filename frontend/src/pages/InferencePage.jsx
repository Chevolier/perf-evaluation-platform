import React, { useState, useEffect, useRef } from 'react';
import { Card, Button, Row, Col, Typography, Space, Steps, Switch, message } from 'antd';
import { ArrowLeftOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons';
import ResultsDisplay from '../components/ResultsDisplay';

const { Title, Paragraph } = Typography;

const InferencePage = ({ 
  selectedModels, 
  dataset, 
  params, 
  onPrev, 
  onReset 
}) => {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState({});
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshTime, setLastRefreshTime] = useState(null);
  const refreshIntervalRef = useRef(null);
  const currentModelsRef = useRef([]);


  // Convert files to base64
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

  // Check if any models are still processing
  const hasProcessingModels = () => {
    return Object.values(results).some(result => result.status === 'loading');
  };

  // Manual refresh function
  const handleManualRefresh = async () => {
    if (currentModelsRef.current.length === 0) {
      message.info('没有正在进行的推理任务');
      return;
    }
    
    try {
      // Only refresh models that are still processing
      const processingModels = Object.entries(results)
        .filter(([_, result]) => result.status === 'loading')
        .map(([modelName]) => modelName);
      
      if (processingModels.length === 0) {
        message.info('所有模型推理已完成');
        return;
      }
      
      message.info(`正在刷新 ${processingModels.length} 个处理中的模型结果...`);
      setLastRefreshTime(new Date().toLocaleTimeString());
      
      // Trigger a new request for processing models
      await refreshProcessingModels(processingModels);
      
    } catch (error) {
      console.error('Manual refresh error:', error);
      message.error('刷新失败，请稍后重试');
    }
  };

  // Refresh processing models function
  const refreshProcessingModels = async (modelNames) => {
    const base64Data = await filesToBase64(dataset.files);
    
    const modelMapping = {
      'Claude3.5': 'claude35',
      'Claude4': 'claude4',
      'Nova Pro': 'nova',
      'qwen2-vl-7b': 'qwen2-vl-7b',
      'qwen2.5-vl-32b': 'qwen2.5-vl-32b',
      'qwen2.5-0.5b': 'qwen2.5-0.5b',
      'gemma-3-4b': 'gemma-3-4b',
      'ui-tars-1.5-7b': 'ui-tars-1.5-7b'
    };
    
    const mappedModels = modelNames.map(model => modelMapping[model] || model);
    
    const response = await fetch('/api/multi-inference', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        models: mappedModels,
        text: dataset.prompt,
        frames: base64Data,
        mediaType: dataset.type,
        max_tokens: params.max_tokens || 1024,
        temperature: params.temperature || 0.6
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'heartbeat' || data.type === 'complete') {
              continue;
            }

            if (data.model) {
              const reverseMapping = Object.fromEntries(
                Object.entries(modelMapping).map(([k, v]) => [v, k])
              );

              const frontendModelName = reverseMapping[data.model] || data.model;

              // Only update if this model was in our refresh list
              if (modelNames.includes(frontendModelName)) {
                let resultData;

                if (data.status === 'success') {
                  let tokens = 'N/A';
                  if (data.result.usage) {
                    const usage = data.result.usage;
                    const inputTokens = usage.input_tokens || usage.prompt_tokens || 0;
                    const outputTokens = usage.output_tokens || usage.completion_tokens || 0;
                    const totalTokens = usage.total_tokens || (inputTokens + outputTokens);
                    tokens = totalTokens > 0 ? `${totalTokens} (${inputTokens}+${outputTokens})` : 'N/A';
                  }

                  resultData = {
                    status: 'success',
                    response: data.result,
                    metadata: {
                      processingTime: 'N/A',
                      tokens: tokens,
                      modelVersion: frontendModelName
                    }
                  };
                } else if (data.status === 'not_deployed') {
                  resultData = {
                    status: 'error',
                    error: data.message || `模型 ${frontendModelName} 正在部署中或尚未部署，请稍后再试。`,
                    errorType: 'deployment_needed',
                    metadata: { processingTime: 'N/A' }
                  };
                } else {
                  resultData = {
                    status: 'error',
                    error: data.error || '未知错误',
                    metadata: { processingTime: 'N/A' }
                  };
                }

                setResults(prevResults => ({
                  ...prevResults,
                  [frontendModelName]: resultData
                }));
              }
            }
          } catch (e) {
            console.error('Error parsing refresh SSE data:', e);
          }
        }
      }
    }
  };

  // Auto refresh effect
  useEffect(() => {
    if (autoRefresh && hasProcessingModels() && !loading) {
      refreshIntervalRef.current = setInterval(async () => {
        const processingModels = Object.entries(results)
          .filter(([_, result]) => result.status === 'loading')
          .map(([modelName]) => modelName);

        if (processingModels.length > 0) {
          try {
            console.log('Auto-refreshing processing models:', processingModels);
            setLastRefreshTime(new Date().toLocaleTimeString());
            await refreshProcessingModels(processingModels);
          } catch (error) {
            console.error('Auto refresh error:', error);
          }
        } else {
          // No more processing models, clear interval
          if (refreshIntervalRef.current) {
            clearInterval(refreshIntervalRef.current);
            refreshIntervalRef.current = null;
          }
        }
      }, 15000); // 15 seconds

      return () => {
        if (refreshIntervalRef.current) {
          clearInterval(refreshIntervalRef.current);
          refreshIntervalRef.current = null;
        }
      };
    }
  }, [autoRefresh, results, loading]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, []);

  const handleRun = async () => {
    setLoading(true);
    setResults({});
    setLastRefreshTime(null);
    currentModelsRef.current = selectedModels;
    
    try {
      // Prepare data for multi-inference
      const base64Data = await filesToBase64(dataset.files);
      
      // Map frontend model names to backend names
      const modelMapping = {
        'Claude3.5': 'claude35',
        'Claude4': 'claude4',
        'Nova Pro': 'nova',
        'qwen2-vl-7b': 'qwen2-vl-7b',
        'qwen2.5-vl-32b': 'qwen2.5-vl-32b',
        'qwen2.5-0.5b': 'qwen2.5-0.5b',
        'gemma-3-4b': 'gemma-3-4b',
        'ui-tars-1.5-7b': 'ui-tars-1.5-7b'
      };
      
      const mappedModels = selectedModels.map(model => modelMapping[model] || model);
      
      // Initialize loading states for all models
      const initialResults = {};
      for (const modelName of selectedModels) {
        initialResults[modelName] = {
          status: 'loading',
          message: '正在处理中...',
          metadata: { processingTime: 'N/A' }
        };
      }
      setResults(initialResults);
      
      // Use streaming multi-inference endpoint
      const response = await fetch('/api/multi-inference', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          models: mappedModels,
          text: dataset.prompt,
          frames: base64Data,
          mediaType: dataset.type,
          max_tokens: params.max_tokens || 1024,
          temperature: params.temperature || 0.1
        })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep the incomplete line in buffer
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'heartbeat') {
                continue;
              }
              
              if (data.type === 'complete') {
                break;
              }
              
              if (data.model) {
                // Map backend model names back to frontend names
                const reverseMapping = Object.fromEntries(
                  Object.entries(modelMapping).map(([k, v]) => [v, k])
                );
                
                const frontendModelName = reverseMapping[data.model] || data.model;
                
                let resultData;
                
                if (data.status === 'success') {
                  // Parse token usage
                  let tokens = 'N/A';
                  if (data.result.usage) {
                    const usage = data.result.usage;
                    const inputTokens = usage.input_tokens || usage.prompt_tokens || 0;
                    const outputTokens = usage.output_tokens || usage.completion_tokens || 0;
                    const totalTokens = usage.total_tokens || (inputTokens + outputTokens);
                    tokens = totalTokens > 0 ? `${totalTokens} (${inputTokens}+${outputTokens})` : 'N/A';
                  }
                  
                  resultData = {
                    status: 'success',
                    response: data.result,
                    metadata: {
                      processingTime: 'N/A', // Will be calculated on backend
                      tokens: tokens,
                      modelVersion: frontendModelName
                    }
                  };
                } else if (data.status === 'not_deployed') {
                  resultData = {
                    status: 'error',
                    error: data.message || `模型 ${frontendModelName} 正在部署中或尚未部署，请稍后再试。`,
                    errorType: 'deployment_needed',
                    metadata: { processingTime: 'N/A' }
                  };
                } else {
                  resultData = {
                    status: 'error',
                    error: data.error || '未知错误',
                    metadata: { processingTime: 'N/A' }
                  };
                }
                
                setResults(prevResults => ({
                  ...prevResults,
                  [frontendModelName]: resultData
                }));
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
      
    } catch (error) {
      console.error('Multi-inference error:', error);
      
      // Set error for all models
      const errorResults = {};
      for (const modelName of selectedModels) {
        errorResults[modelName] = {
          status: 'error',
          error: `网络请求失败: ${error.message}`,
          metadata: { processingTime: 'N/A' }
        };
      }
      setResults(errorResults);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Row gutter={[24, 24]} justify="center">
        <Col span={24}>
          <Card>
            <div style={{ textAlign: 'center', marginBottom: '32px' }}>
              <Title level={2}>步骤 4: 开始评测推理</Title>
              <Paragraph style={{ fontSize: '16px', color: '#666' }}>
                所有配置已完成，现在可以开始进行模型推理评测。
              </Paragraph>
            </div>
            
            <Steps
              current={3}
              style={{ marginBottom: '32px' }}
              items={[
                { title: '选择模型', description: `已选择 ${selectedModels.length} 个模型` },
                { title: '上传材料', description: `已上传 ${dataset.files?.length || 0} 个文件` },
                { title: '配置参数', description: `温度: ${params.temperature}, 最大Token: ${params.max_tokens}` },
                { title: '开始评测', description: '执行推理测试' }
              ]}
            />
            
            <Row justify="center" style={{ marginBottom: '24px' }}>
              <Button 
                type="primary" 
                size="large" 
                loading={loading} 
                onClick={handleRun}
              >
                开始批量推理评测
              </Button>
            </Row>
            
            <ResultsDisplay results={results} loading={loading} />
            
            {/* Auto-refresh controls */}
            {Object.keys(results).length > 0 && (
              <Card 
                size="small" 
                style={{ 
                  marginTop: '16px', 
                  marginBottom: '16px', 
                  background: '#fafafa',
                  border: '1px dashed #d9d9d9'
                }}
              >
                <Row align="middle" justify="space-between">
                  <Col>
                    <Space align="center">
                      <Switch 
                        checked={autoRefresh} 
                        onChange={setAutoRefresh}
                        size="small"
                      />
                      <span style={{ fontSize: '12px', color: '#666' }}>
                        自动刷新 (每15秒)
                      </span>
                      {lastRefreshTime && (
                        <span style={{ fontSize: '11px', color: '#999' }}>
                          上次刷新: {lastRefreshTime}
                        </span>
                      )}
                    </Space>
                  </Col>
                  <Col>
                    <Space>
                      {hasProcessingModels() && (
                        <span style={{ fontSize: '11px', color: '#fa8c16' }}>
                          {Object.values(results).filter(r => r.status === 'loading').length} 个模型处理中
                        </span>
                      )}
                      <Button 
                        type="text" 
                        size="small" 
                        icon={<SyncOutlined />}
                        onClick={handleManualRefresh}
                        disabled={loading}
                      >
                        立即刷新
                      </Button>
                    </Space>
                  </Col>
                </Row>
              </Card>
            )}
            
            <div style={{ textAlign: 'center', marginTop: '32px' }}>
              <Space size="large">
                <Button 
                  size="large" 
                  onClick={onPrev}
                  icon={<ArrowLeftOutlined />}
                >
                  上一步
                </Button>
                <Button 
                  size="large" 
                  onClick={onReset}
                  icon={<ReloadOutlined />}
                >
                  重新开始
                </Button>
              </Space>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default InferencePage;