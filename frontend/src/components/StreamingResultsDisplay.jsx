import React, { useState, useEffect, useRef } from 'react';
import { Card, Typography, Tag, Space, Progress, Alert, Button } from 'antd';
import { CheckCircleOutlined, ClockCircleOutlined, ExclamationCircleOutlined, PlayCircleOutlined, StopOutlined } from '@ant-design/icons';

const { Title, Paragraph, Text } = Typography;

const StreamingResultsDisplay = ({ dataset, selectedModels, params, onStreamComplete }) => {
  const [results, setResults] = useState({});
  const [isStreaming, setIsStreaming] = useState(false);
  const [completedCount, setCompletedCount] = useState(0);
  const [streamStatus, setStreamStatus] = useState('idle'); // idle, connecting, streaming, completed, error
  const eventSourceRef = useRef(null);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'processing':
        return <ClockCircleOutlined style={{ color: '#1890ff', animation: 'spin 1s linear infinite' }} />;
      default:
        return <ClockCircleOutlined style={{ color: '#faad14' }} />;
    }
  };

  const getStatusTag = (status) => {
    switch (status) {
      case 'success':
        return <Tag color="success">完成</Tag>;
      case 'error':
        return <Tag color="error">失败</Tag>;
      case 'processing':
        return <Tag color="processing">处理中</Tag>;
      default:
        return <Tag color="default">等待中</Tag>;
    }
  };

  const formatResponse = (response) => {
    if (typeof response === 'string') {
      return response;
    }
    
    // Extract text from Claude API response
    if (response && response.content && Array.isArray(response.content)) {
      const textContent = response.content
        .filter(item => item.type === 'text')
        .map(item => item.text)
        .join('\\n');
      if (textContent) return textContent;
    }
    
    // Extract text from Nova API response  
    if (response && response.output && response.output.message && response.output.message.content) {
      const content = response.output.message.content;
      if (Array.isArray(content)) {
        const textContent = content
          .filter(item => item.text)
          .map(item => item.text)
          .join('\\n');
        if (textContent) return textContent;
      }
    }
    
    // Extract text from EMD API response
    if (response && response.content && Array.isArray(response.content)) {
      const textContent = response.content
        .filter(item => item.text)
        .map(item => item.text)
        .join('\\n');
      if (textContent) return textContent;
    }
    
    return JSON.stringify(response, null, 2);
  };

  const startStreaming = async () => {
    if (!dataset.files || dataset.files.length === 0) {
      alert('请先上传文件');
      return;
    }
    if (selectedModels.length === 0) {
      alert('请选择至少一个模型');
      return;
    }
    if (!dataset.prompt) {
      alert('请输入Prompt');
      return;
    }

    setIsStreaming(true);
    setStreamStatus('connecting');
    setResults({});
    setCompletedCount(0);

    // 初始化结果状态
    const initialResults = {};
    selectedModels.forEach(model => {
      initialResults[model] = {
        status: 'processing',
        message: '等待开始处理...'
      };
    });
    setResults(initialResults);

    try {
      // 将文件转换为base64
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

      const base64Data = await filesToBase64(dataset.files);

      // 准备请求数据
      const requestData = {
        text: dataset.prompt,
        frames: base64Data,
        media: base64Data, // 为Nova准备的字段
        mediaType: dataset.type,
        max_tokens: params.max_tokens || 4096,
        temperature: params.temperature || 0.1,
        models: selectedModels
      };

      // 发起推理请求
      const response = await fetch('http://localhost:5000/api/multi-inference', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      setStreamStatus('streaming');

      // 读取流式响应
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      try {
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            setStreamStatus('completed');
            setIsStreaming(false);
            if (onStreamComplete) {
              onStreamComplete(results);
            }
            break;
          }

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\\n\\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                console.log('收到流式数据:', data);

                switch (data.type) {
                  case 'start':
                    console.log('开始处理模型:', data.models);
                    break;

                  case 'model_start':
                    setResults(prev => ({
                      ...prev,
                      [data.model]: {
                        ...prev[data.model],
                        status: 'processing',
                        message: '正在处理中...',
                        startTime: new Date().toISOString()
                      }
                    }));
                    break;

                  case 'heartbeat':
                    console.log('收到心跳:', data.timestamp);
                    break;

                  case 'complete':
                    setStreamStatus('completed');
                    setIsStreaming(false);
                    if (onStreamComplete) {
                      onStreamComplete(results);
                    }
                    break;

                  default:
                    // 模型结果
                    if (data.model) {
                      setResults(prev => ({
                        ...prev,
                        [data.model]: {
                          status: data.status,
                          processing_time: data.processing_time,
                          result: data.result,
                          error: data.error,
                          timestamp: data.timestamp
                        }
                      }));

                      if (data.status === 'success' || data.status === 'error') {
                        setCompletedCount(prev => prev + 1);
                      }
                    }
                    break;
                }
              } catch (error) {
                console.error('解析流式数据失败:', error, line);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }

    } catch (error) {
      console.error('启动流式推理失败:', error);
      setStreamStatus('error');
      setIsStreaming(false);
    }
  };

  const stopStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
    setStreamStatus('idle');
  };

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const renderModelCard = (modelName, result) => (
    <Card
      key={modelName}
      size="small"
      style={{ marginBottom: 16 }}
      title={
        <Space>
          {getStatusIcon(result?.status)}
          <Text strong>{modelName}</Text>
          {getStatusTag(result?.status)}
          {result?.processing_time && (
            <Text type="secondary">({result.processing_time}s)</Text>
          )}
        </Space>
      }
    >
      {result?.status === 'success' ? (
        <div>
          <Paragraph
            style={{
              background: '#f5f5f5',
              padding: 12,
              borderRadius: 6,
              whiteSpace: 'pre-wrap',
              maxHeight: 200,
              overflow: 'auto',
              margin: 0
            }}
          >
            {formatResponse(result.result)}
          </Paragraph>
        </div>
      ) : result?.status === 'error' ? (
        <Alert
          type="error"
          message="推理失败"
          description={result.error}
          showIcon
        />
      ) : (
        <div style={{ textAlign: 'center', padding: 20 }}>
          <ClockCircleOutlined style={{ fontSize: 24, color: '#1890ff' }} />
          <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
            {result?.message || '等待处理...'}
          </Paragraph>
        </div>
      )}
    </Card>
  );

  const progress = selectedModels.length > 0 ? (completedCount / selectedModels.length) * 100 : 0;

  return (
    <div style={{ marginTop: 24 }}>
      <Card>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Title level={4} style={{ margin: 0 }}>流式多模型推理</Title>
            {!isStreaming ? (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={startStreaming}
                disabled={streamStatus === 'connecting'}
              >
                开始推理
              </Button>
            ) : (
              <Button
                danger
                icon={<StopOutlined />}
                onClick={stopStreaming}
              >
                停止推理
              </Button>
            )}
          </Space>
        </div>

        {selectedModels.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <Text>进度: {completedCount}/{selectedModels.length}</Text>
            <Progress
              percent={progress}
              status={streamStatus === 'error' ? 'exception' : 'active'}
              showInfo={false}
              style={{ marginTop: 8 }}
            />
          </div>
        )}

        {streamStatus === 'error' && (
          <Alert
            type="error"
            message="连接失败"
            description="无法连接到流式推理服务，请检查服务是否启动"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <div>
          {selectedModels.map(modelName => 
            renderModelCard(modelName, results[modelName])
          )}
        </div>
      </Card>
    </div>
  );
};

export default StreamingResultsDisplay;
