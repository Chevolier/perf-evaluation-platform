import React from 'react';
import { Card, Table, Typography, Divider, Tag, Space, Collapse } from 'antd';
import { CheckCircleOutlined, ClockCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons';

const { Title, Paragraph, Text } = Typography;
const { Panel } = Collapse;

const ResultsDisplay = ({ results, loading }) => {
  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <ClockCircleOutlined style={{ fontSize: '48px', color: '#1890ff' }} />
          <Title level={4} style={{ marginTop: '16px' }}>正在处理评测请求...</Title>
          <Paragraph type="secondary">请耐心等待模型推理完成</Paragraph>
        </div>
      </Card>
    );
  }

  if (!results || Object.keys(results).length === 0) {
    return null;
  }

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
    
    if (typeof response === 'string') {
      // Try to parse string as JSON in case it's a stringified response
      try {
        const parsed = JSON.parse(response);
        return formatResponse(parsed); // Recursive call with parsed object
      } catch (e) {
        return response;
      }
    }
    
    // Extract text from EMD/OpenAI API response (choices format)
    if (response && typeof response === 'object' && response.choices && Array.isArray(response.choices) && response.choices.length > 0) {
      const choice = response.choices[0];
      if (choice && choice.message && typeof choice.message.content === 'string') {
        return choice.message.content;
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
    
    // Fallback to JSON display if text extraction fails
    return JSON.stringify(response, null, 2);
  };

  const renderSingleResult = (modelName, result) => (
    <Card
      key={modelName}
      title={
        <Space>
          {getStatusIcon(result.status)}
          <Text strong>{modelName}</Text>
          {getStatusTag(result.status)}
        </Space>
      }
      style={{ marginBottom: '16px' }}
    >
      {result.status === 'success' ? (
        <div>
          <Paragraph>
            <Text strong>响应内容：</Text>
          </Paragraph>
          <Paragraph
            copyable
            style={{
              background: '#f5f5f5',
              padding: '12px',
              borderRadius: '6px',
              whiteSpace: 'pre-wrap',
              maxHeight: '300px',
              overflow: 'auto'
            }}
          >
            {formatResponse(result.response)}
          </Paragraph>
          {result.metadata && (
            <div>
              <Divider />
              <Collapse ghost>
                <Panel header="详细信息" key="metadata">
                  <Text type="secondary">
                    处理时间: {result.metadata.processingTime || 'N/A'}<br/>
                    Token数量: {result.metadata.tokens || 'N/A'}<br/>
                    模型版本: {result.metadata.modelVersion || 'N/A'}
                  </Text>
                </Panel>
              </Collapse>
            </div>
          )}
        </div>
      ) : result.status === 'loading' ? (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <ClockCircleOutlined style={{ fontSize: '24px', color: '#1890ff' }} />
          <Paragraph style={{ marginTop: '8px' }}>
            {result.message || '正在处理中...'}
          </Paragraph>
        </div>
      ) : (
        <div>
          <Paragraph type="danger">
            <Text strong>错误信息：</Text>
            {result.error || '未知错误'}
          </Paragraph>
          {result.errorType === 'deployment_needed' && (
            <div style={{ marginTop: '12px', padding: '12px', background: '#fff7e6', borderRadius: '6px', border: '1px solid #ffd591' }}>
              <Text type="warning">
                <strong>💡 提示：</strong> 
                这是一个EMD本地模型，需要先部署才能使用。请使用以下命令部署模型：
              </Text>
              <div style={{ marginTop: '8px', padding: '8px', background: '#f0f0f0', borderRadius: '4px', fontFamily: 'monospace', fontSize: '12px' }}>
                emd deploy --model-id {modelName.includes('qwen2-vl-7b') ? 'Qwen2-VL-7B-Instruct' : 
                             modelName.includes('qwen2.5-vl-32b') ? 'Qwen2.5-VL-32B-Instruct' :
                             modelName.includes('gemma-3-4b') ? 'gemma-3-4b-it' :
                             modelName.includes('ui-tars-1.5-7b') ? 'UI-TARS-1.5-7B' : 'MODEL_ID'} --instance-type g5.12xlarge --engine-type vllm --service-type sagemaker_realtime --model-tag dev
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );

  const renderComparisonView = () => {
    const modelNames = Object.keys(results || {});
    const tableData = modelNames.map(modelName => {
      const result = results[modelName] || {};
      return {
        key: modelName,
        model: modelName,
        status: result.status || 'loading',
        response: formatResponse(result.response || result.error || '处理中...'),
        tokens: result.metadata?.tokens || 'N/A',
        time: result.metadata?.processingTime || 'N/A'
      };
    });

    const columns = [
      {
        title: '模型',
        dataIndex: 'model',
        key: 'model',
        width: 150,
        render: (text) => <Text strong>{text}</Text>
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        render: (status) => getStatusTag(status)
      },
      {
        title: '响应内容',
        dataIndex: 'response',
        key: 'response',
        render: (text) => (
          <div style={{ maxWidth: '400px', maxHeight: '200px', overflow: 'auto' }}>
            <Text copyable style={{ whiteSpace: 'pre-wrap', fontSize: '12px' }}>
              {text && text.length > 200 ? text.substring(0, 200) + '...' : text || 'N/A'}
            </Text>
          </div>
        )
      },
      {
        title: 'Token数',
        dataIndex: 'tokens',
        key: 'tokens',
        width: 100
      },
      {
        title: '处理时间',
        dataIndex: 'time',
        key: 'time',
        width: 120
      }
    ];

    return (
      <Card title="模型对比结果">
        <Table
          dataSource={tableData}
          columns={columns}
          pagination={false}
          scroll={{ x: 800 }}
        />
      </Card>
    );
  };

  const modelCount = Object.keys(results || {}).length;

  return (
    <div style={{ marginTop: '24px' }}>
      <Title level={3}>评测结果</Title>
      
      {modelCount > 1 ? (
        <Collapse defaultActiveKey={['comparison']}>
          <Panel header={`对比视图 (${modelCount}个模型)`} key="comparison">
            {renderComparisonView()}
          </Panel>
          <Panel header="详细结果" key="detailed">
            {Object.entries(results || {}).map(([modelName, result]) =>
              renderSingleResult(modelName, result)
            )}
          </Panel>
        </Collapse>
      ) : (
        Object.entries(results || {}).map(([modelName, result]) =>
          renderSingleResult(modelName, result)
        )
      )}
    </div>
  );
};

export default ResultsDisplay;