import React from 'react';
import { Card, Typography, Tag, Space, Divider, Spin, Alert } from 'antd';
import { 
  CheckCircleOutlined, 
  ClockCircleOutlined, 
  ExclamationCircleOutlined,
  RobotOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;

const PlaygroundResultsDisplay = ({ results, loading }) => {
  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'not_deployed':
        return <ExclamationCircleOutlined style={{ color: '#faad14' }} />;
      case 'loading':
      case 'processing':
      case 'streaming':
        return <ClockCircleOutlined style={{ color: '#1890ff' }} />;
      default:
        return <ClockCircleOutlined style={{ color: '#d9d9d9' }} />;
    }
  };

  const getStatusTag = (status) => {
    switch (status) {
      case 'success':
        return <Tag color="success">成功</Tag>;
      case 'error':
        return <Tag color="error">失败</Tag>;
      case 'not_deployed':
        return <Tag color="warning">等待部署</Tag>;
      case 'loading':
      case 'processing':
      case 'streaming':
        return <Tag color="processing">处理中</Tag>;
      default:
        return <Tag color="default">等待</Tag>;
    }
  };

  const formatResponse = (response) => {
    if (!response) {
      return 'N/A';
    }
    
    // FIRST: Extract the content field from our backend response format
    if (response && typeof response === 'object' && response.content) {
      // This is our backend response format: {content: "...", usage: {...}, raw_response: {...}}
      return response.content;
    }
    
    if (typeof response === 'string') {
      // Try to parse string as JSON in case it's a stringified response
      try {
        const parsed = JSON.parse(response);
        return formatResponse(parsed); // Recursive call with parsed object
      } catch (e) {
        return response;
      }
    }
    
    // Extract text from OpenAI format response (for models like Qwen2.5-0.5B) - check first
    if (response && typeof response === 'object' && response.choices && Array.isArray(response.choices) && response.choices.length > 0) {
      const firstChoice = response.choices[0];
      if (firstChoice && firstChoice.message && typeof firstChoice.message.content === 'string') {
        return firstChoice.message.content;
      }
    }
    
    // Extract text from Claude API response
    if (response && response.content && Array.isArray(response.content)) {
      const textContent = response.content
        .filter(item => item.type === 'text')
        .map(item => item.text)
        .join('\n');
      if (textContent) return textContent;
    }
    
    // Extract text from Nova API response  
    if (response && response.output && response.output.message && response.output.message.content) {
      const content = response.output.message.content;
      if (Array.isArray(content)) {
        const textContent = content
          .filter(item => item.text)
          .map(item => item.text)
          .join('\n');
        if (textContent) return textContent;
      } else if (typeof content === 'string') {
        return content;
      }
    }
    
    // Fallback to JSON string for debugging
    return JSON.stringify(response, null, 2);
  };

  const renderFormattedContent = (content) => {
    if (!content) return 'N/A';
    
    // Check if content has reasoning structure (with or without response)
    if (typeof content === 'string' && content.includes('**Reasoning:**')) {
      let reasoningPart = '';
      let responsePart = '';
      let notePart = '';
      
      if (content.includes('**Response:**')) {
        // Full format with reasoning and response
        const parts = content.split('**Response:**');
        reasoningPart = parts[0].replace('**Reasoning:**', '').trim();
        responsePart = parts[1] ? parts[1].trim() : '';
      } else if (content.includes('**Note:**')) {
        // Reasoning only with note about token limits
        const parts = content.split('**Note:**');
        reasoningPart = parts[0].replace('**Reasoning:**', '').trim();
        notePart = parts[1] ? parts[1].trim() : '';
      } else {
        // Just reasoning
        reasoningPart = content.replace('**Reasoning:**', '').trim();
      }
      
      return (
        <div>
          {reasoningPart && (
            <div style={{ marginBottom: '16px' }}>
              <div style={{ 
                fontSize: '13px', 
                fontWeight: 'bold', 
                color: '#722ed1', 
                marginBottom: '8px',
                display: 'flex',
                alignItems: 'center'
              }}>
                🧠 Reasoning Process
              </div>
              <div style={{
                backgroundColor: '#f6f8fa',
                border: '1px solid #e1e4e8',
                borderRadius: '6px',
                padding: '12px',
                fontSize: '13px',
                fontStyle: 'italic',
                color: '#586069',
                lineHeight: '1.5'
              }}>
                {reasoningPart}
              </div>
            </div>
          )}
          
          {responsePart && (
            <div style={{ marginBottom: '16px' }}>
              <div style={{ 
                fontSize: '13px', 
                fontWeight: 'bold', 
                color: '#28a745', 
                marginBottom: '8px',
                display: 'flex',
                alignItems: 'center'
              }}>
                💬 Final Response
              </div>
              <div style={{
                backgroundColor: '#f8fff8',
                border: '1px solid #d1f2d1',
                borderRadius: '6px',
                padding: '12px',
                fontSize: '14px',
                lineHeight: '1.6',
                whiteSpace: 'pre-wrap'
              }}>
                {responsePart}
              </div>
            </div>
          )}
          
          {notePart && (
            <div>
              <div style={{ 
                fontSize: '13px', 
                fontWeight: 'bold', 
                color: '#fa8c16', 
                marginBottom: '8px',
                display: 'flex',
                alignItems: 'center'
              }}>
                ⚠️ Note
              </div>
              <div style={{
                backgroundColor: '#fffbe6',
                border: '1px solid #ffe58f',
                borderRadius: '6px',
                padding: '12px',
                fontSize: '13px',
                color: '#ad6800',
                lineHeight: '1.5'
              }}>
                {notePart}
              </div>
            </div>
          )}
        </div>
      );
    }
    
    // Regular content without reasoning
    return (
      <div style={{
        whiteSpace: 'pre-wrap',
        lineHeight: '1.6'
      }}>
        {content}
      </div>
    );
  };

  if (loading && Object.keys(results).length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <Spin size="large" />
        <Title level={4} style={{ marginTop: '16px', color: '#1890ff' }}>
          正在连接模型...
        </Title>
        <Text type="secondary">建立连接中，即将开始流式输出</Text>
      </div>
    );
  }

  return (
    <div style={{ padding: '8px 0' }}>
      {Object.entries(results).map(([modelName, result]) => {
        const displayName = result.label || result.displayName || modelName;
        const showTechnicalName = displayName !== modelName;
        const displayContent = (result?.result && (result.result.content ?? (typeof result.result === "string" ? result.result : null))) ?? result?.partialContent ?? null;
        const isStreaming = result.status === "streaming";
        const showContent = displayContent !== null && displayContent !== undefined && displayContent !== "";

        return (
        <Card
          key={modelName}
          size="small"
          style={{ 
            marginBottom: 16,
            border: result.status === 'success' ? '1px solid #52c41a' : 
                   result.status === 'error' ? '1px solid #ff4d4f' :
                   result.status === 'streaming' ? '1px solid #1890ff' : '1px solid #d9d9d9'
          }}
          title={
            <Space direction="vertical" size={0} style={{ gap: 0 }}>
              <Space>
                <RobotOutlined />
                <Text strong>{displayName}</Text>
                {getStatusTag(result.status)}
              </Space>
              {showTechnicalName && (
                <Text type="secondary" style={{ fontSize: '11px' }}>
                  {modelName}
                </Text>
              )}
            </Space>
          }
          extra={
            <Space>
              {result.metadata?.processingTime && (
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  {result.metadata.processingTime}
                </Text>
              )}
              {getStatusIcon(result.status)}
            </Space>
          }
        >
          {result.status === 'error' ? (
            <Alert
              type="error"
              message="推理失败"
              description={result.message || '推理请求发生错误'}
              showIcon
            />
          ) : (
            <div>
              {showContent && (
                <div
                  style={{
                    marginBottom: 12,
                    maxHeight: '400px',
                    overflowY: 'auto',
                    backgroundColor: isStreaming ? '#f0f9ff' : '#fafafa',
                    padding: '12px',
                    borderRadius: '6px',
                    border: isStreaming ? '1px solid #bae7ff' : '1px solid #f0f0f0'
                  }}
                >
                  {renderFormattedContent(displayContent)}
                  {isStreaming && (
                    <span
                      style={{
                        display: 'inline-block',
                        width: '8px',
                        height: '16px',
                        backgroundColor: '#1890ff',
                        animation: 'blink 1s infinite',
                        marginLeft: '2px',
                        verticalAlign: 'middle'
                      }}
                    />
                  )}
                </div>
              )}

              {!showContent && isStreaming && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: 12 }}>
                  <Spin size="small" />
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    等待首个响应...
                  </Text>
                </div>
              )}

              {isStreaming && (
                <Space size="small" align="center">
                  <Spin size="small" />
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    模型正在生成...
                  </Text>
                </Space>
              )}

              {result.status === 'success' && result.result?.usage && (
                <div>
                  <Divider style={{ margin: '8px 0' }} />
                  <Space size="large">
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      输入: {result.result.usage.input_tokens || result.result.usage.prompt_tokens || 'N/A'} tokens
                    </Text>
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      输出: {result.result.usage.output_tokens || result.result.usage.completion_tokens || 'N/A'} tokens
                    </Text>
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      总计: {result.result.usage.total_tokens || 'N/A'} tokens
                    </Text>
                  </Space>
                </div>
              )}

              {!isStreaming && result.status !== 'success' && !showContent && (
                <div style={{ textAlign: 'center', padding: '20px' }}>
                  <Spin />
                  <Text type="secondary" style={{ display: 'block', marginTop: '8px' }}>
                    处理中...
                  </Text>
                </div>
              )}
            </div>
          )}
        </Card>
      )})}
    </div>
  );
};

export default PlaygroundResultsDisplay;
