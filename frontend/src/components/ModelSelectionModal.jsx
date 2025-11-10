import React, { useState, useEffect } from 'react';
import { Modal, Card, Checkbox, Button, Typography, Tag, Row, Col, Space, Divider, Spin, message } from 'antd';
import { 
  RobotOutlined, 
  CloudOutlined, 
  ThunderboltOutlined,
  CheckCircleOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const ModelSelectionModal = ({ 
  visible, 
  onCancel, 
  onOk, 
  selectedModels, 
  onModelChange 
}) => {
  const [loading, setLoading] = useState(false);
  const [modelStatus, setModelStatus] = useState({});

  // 模型分类
  const modelCategories = {
    bedrock: {
      title: 'Bedrock 模型',
      icon: <CloudOutlined />,
      color: '#1890ff',
      models: [
        {
          key: 'claude4',
          name: 'Claude 4',
          description: '最新的Claude模型，具备强大的推理能力',
          capabilities: []
        },
        {
          key: 'claude35',
          name: 'Claude 3.5 Sonnet',
          description: '平衡性能与速度的高效模型',
          capabilities: []
        },
        {
          key: 'nova',
          name: 'Amazon Nova Pro',
          description: 'AWS原生多模态大模型',
          capabilities: []
        }
      ]
    },
    emd: {
      title: 'EMD 部署模型',
      icon: <ThunderboltOutlined />,
      color: '#52c41a',
      models: [
        {
          key: 'qwen2-vl-7b',
          name: 'Qwen2-VL-7B',
          description: '通义千问视觉语言模型，7B参数',
          capabilities: []
        },
        {
          key: 'qwen2.5-vl-7b',
          name: 'Qwen2.5-VL-7B',
          description: '通义千问视觉语言模型，7B参数',
          capabilities: []
        },
        {
          key: 'qwen2.5-vl-32b',
          name: 'Qwen2.5-VL-32B',
          description: '通义千问视觉语言模型，32B参数',
          capabilities: []
        },
        {
          key: 'qwen2.5-0.5b',
          name: 'Qwen2.5-0.5B',
          description: '轻量级文本模型，适合快速推理',
          capabilities: []
        },
        {
          key: 'gemma-3-4b',
          name: 'Gemma-3-4B',
          description: 'Google开源语言模型',
          capabilities: []
        },
        {
          key: 'qwen3-0.6b',
          name: 'Qwen3-0.6B',
          description: '最新Qwen3模型，0.6B参数，高效轻量',
          capabilities: []
        },
        {
          key: 'qwen3-8b',
          name: 'Qwen3-8B',
          description: 'Qwen3模型，8B参数，平衡性能与效率',
          capabilities: []
        },
        {
          key: 'ui-tars-1.5-7b',
          name: 'UI-TARS-1.5-7B',
          description: '用户界面理解专用模型',
          capabilities: []
        }
      ]
    }
  };

  // 检查模型状态
  const checkModelStatus = async () => {
    if (!visible) return;
    
    setLoading(true);
    try {
      // 获取所有模型列表
      const allModels = [
        ...modelCategories.bedrock.models.map(m => m.key),
        ...modelCategories.ec2.models.map(m => m.key)
      ];
      
      const response = await fetch('/api/check-model-status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ models: allModels })
      });
      
      if (response.ok) {
        const data = await response.json();
        setModelStatus(data.model_status || {});
      }
    } catch (error) {
      console.error('检查模型状态失败:', error);
      message.error('获取模型状态失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkModelStatus();
  }, [visible]);

  const handleModelToggle = (modelKey) => {
    const newSelected = selectedModels.includes(modelKey)
      ? selectedModels.filter(m => m !== modelKey)
      : [...selectedModels, modelKey];
    onModelChange(newSelected);
  };

  const getStatusTag = (modelKey) => {
    const status = modelStatus[modelKey];
    if (!status) return <Tag color="default">检查中</Tag>;

    switch (status.status) {
      case 'available':
      case 'deployed':
        return <Tag color="success" icon={<CheckCircleOutlined />}>可用</Tag>;
      case 'not_deployed':
        return <Tag color="warning">需部署</Tag>;
      case 'deploying':
        return <Tag color="processing">部署中</Tag>;
      default:
        return <Tag color="default">未知</Tag>;
    }
  };

  const renderModelCard = (model, category) => (
    <Card
      key={model.key}
      size="small"
      style={{ 
        marginBottom: 12,
        border: selectedModels.includes(model.key) 
          ? `2px solid ${category.color}` 
          : '1px solid #d9d9d9',
        borderRadius: 8
      }}
      hoverable
    >
      <div onClick={() => handleModelToggle(model.key)} style={{ cursor: 'pointer' }}>
        <Space align="start" style={{ width: '100%' }}>
          <Checkbox 
            checked={selectedModels.includes(model.key)}
            onChange={() => handleModelToggle(model.key)}
          />
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text strong>{model.name}</Text>
              {getStatusTag(model.key)}
            </div>
            <Paragraph 
              style={{ margin: '4px 0', color: '#666', fontSize: '12px' }}
            >
              {model.description}
            </Paragraph>
            <div>
              {model.capabilities.map(cap => (
                <Tag key={cap} size="small" color={category.color}>
                  {cap}
                </Tag>
              ))}
            </div>
          </div>
        </Space>
      </div>
    </Card>
  );

  return (
    <Modal
      title={
        <Space>
          <RobotOutlined />
          选择推理模型
        </Space>
      }
      open={visible}
      onCancel={onCancel}
      onOk={onOk}
      width={800}
      okText="确认选择"
      cancelText="取消"
      okButtonProps={{
        disabled: selectedModels.length === 0
      }}
    >
      <div style={{ maxHeight: '60vh', overflowY: 'auto' }}>
        <Spin spinning={loading}>
          <div style={{ marginBottom: 16 }}>
            <Text type="secondary">
              已选择 <Text strong style={{ color: '#1890ff' }}>{selectedModels.length}</Text> 个模型
            </Text>
          </div>

          {Object.entries(modelCategories).map(([categoryKey, category]) => (
            <div key={categoryKey}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                marginBottom: 12,
                marginTop: categoryKey !== 'bedrock' ? 20 : 0
              }}>
                <Space>
                  {category.icon}
                  <Title level={5} style={{ margin: 0, color: category.color }}>
                    {category.title}
                  </Title>
                </Space>
              </div>
              
              <Row gutter={[16, 0]}>
                {category.models.map(model => (
                  <Col key={model.key} xs={24} sm={12} lg={8}>
                    {renderModelCard(model, category)}
                  </Col>
                ))}
              </Row>
              
              {categoryKey !== 'emd' && <Divider />}
            </div>
          ))}
        </Spin>
      </div>
    </Modal>
  );
};

export default ModelSelectionModal;