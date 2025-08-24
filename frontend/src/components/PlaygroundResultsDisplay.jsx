import React from 'react';
import { Card, Typography, Tag, Space, Divider, Spin } from 'antd';
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
          正在处理推理请求...
        </Title>
        <Text type="secondary">请耐心等待模型响应</Text>
      </div>
    );
  }

  return (
    <div style={{ padding: '8px 0' }}>
      {Object.entries(results).map(([modelName, result]) => (
        <Card
          key={modelName}
          size="small"
          style={{ 
            marginBottom: 16,
            border: result.status === 'success' ? '1px solid #52c41a' : 
                   result.status === 'error' ? '1px solid #ff4d4f' : '1px solid #d9d9d9'
          }}
          title={
            <Space>
              <RobotOutlined />
              <Text strong>{modelName}</Text>
              {getStatusTag(result.status)}
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
          {result.status === 'success' && result.result ? (
            <div>
              <div
                style={{
                  marginBottom: 12,
                  maxHeight: '400px',
                  overflowY: 'auto',
                  backgroundColor: '#fafafa',
                  padding: '12px',
                  borderRadius: '6px',
                  border: '1px solid #f0f0f0'
                }}
              >
                {renderFormattedContent(formatResponse(result.result))}
              </div>
              
              {result.result.usage && (
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
            </div>
          ) : result.status === 'error' ? (
            <div>
              <Text type="danger" style={{ display: 'block', marginBottom: '8px' }}>
                推理失败
              </Text>
              <div style={{
                backgroundColor: '#fff2f0',
                border: '1px solid #ffccc7',
                borderRadius: '6px',
                padding: '12px',
                maxHeight: '200px',
                overflowY: 'auto',
                fontSize: '12px',
                fontFamily: 'monospace'
              }}>
                {(() => {
                  const errorMsg = result.error || result.message || '推理过程中发生错误';
                  // 尝试美化JSON错误信息
                  try {
                    const parsed = JSON.parse(errorMsg);
                    return JSON.stringify(parsed, null, 2);
                  } catch {
                    return errorMsg;
                  }
                })()}
              </div>
              {result.error && result.error.includes('500') && (
                <div style={{ marginTop: '8px', padding: '8px', backgroundColor: '#fffbe6', border: '1px solid #ffe58f', borderRadius: '4px' }}>
                  <Text type="secondary" style={{ fontSize: '12px', display: 'block', marginBottom: '4px' }}>
                    <strong>💡 500错误常见原因和解决方案：</strong>
                  </Text>
                  <ul style={{ margin: '4px 0', paddingLeft: '16px', fontSize: '11px', color: '#666' }}>
                    <li><strong>模型资源不足：</strong>端点实例可能内存不足或过载，尝试稍后重试</li>
                    <li><strong>输入过大：</strong>减少图片数量、降低图片分辨率或压缩文件大小</li>
                    <li><strong>推理超时：</strong>多媒体处理时间过长，建议使用更小的文件</li>
                    <li><strong>模型故障：</strong>如果持续失败，可能是模型端点需要重新部署</li>
                  </ul>
                </div>
              )}
            </div>
          ) : result.status === 'not_deployed' ? (
            <div>
              <Text type="warning">
                {result.message || '模型尚未部署，请稍后再试'}
              </Text>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <Spin />
              <Text type="secondary" style={{ display: 'block', marginTop: '8px' }}>
                处理中...
              </Text>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
};

export default PlaygroundResultsDisplay;