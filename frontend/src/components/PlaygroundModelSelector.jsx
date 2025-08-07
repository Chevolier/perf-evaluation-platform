import React, { useState, useEffect } from 'react';
import { Modal, Card, Checkbox, Button, Typography, Tag, Row, Col, Space, Spin, message } from 'antd';
import { 
  RobotOutlined, 
  CloudOutlined, 
  ThunderboltOutlined,
  CheckCircleOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const PlaygroundModelSelector = ({ 
  visible, 
  onCancel, 
  onOk, 
  selectedModels, 
  onModelChange 
}) => {
  const [loading, setLoading] = useState(false);
  const [modelStatus, setModelStatus] = useState({});

  // 模型分类（只包含已部署的模型）
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
          alwaysAvailable: true
        },
        {
          key: 'claude35',
          name: 'Claude 3.5 Sonnet',
          description: '平衡性能与速度的高效模型',
          alwaysAvailable: true
        },
        {
          key: 'nova',
          name: 'Amazon Nova Pro',
          description: 'AWS原生多模态大模型',
          alwaysAvailable: true
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
          alwaysAvailable: false
        },
        {
          key: 'qwen2.5-vl-7b',
          name: 'Qwen2.5-VL-7B',
          description: '通义千问视觉语言模型，7B参数',
          alwaysAvailable: false
        },
        {
          key: 'qwen2.5-vl-32b',
          name: 'Qwen2.5-VL-32B',
          description: '通义千问视觉语言模型，32B参数',
          alwaysAvailable: false
        },
        {
          key: 'qwen2.5-0.5b',
          name: 'Qwen2.5-0.5B',
          description: '轻量级文本模型，适合快速推理',
          alwaysAvailable: false
        },
        {
          key: 'gemma-3-4b',
          name: 'Gemma-3-4B',
          description: 'Google开源语言模型',
          alwaysAvailable: false
        },
        {
          key: 'ui-tars-1.5-7b',
          name: 'UI-TARS-1.5-7B',
          description: '用户界面理解专用模型',
          alwaysAvailable: false
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
        ...modelCategories.emd.models.map(m => m.key)
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

  // 判断模型是否可用
  const isModelAvailable = (model) => {
    if (model.alwaysAvailable) return true;
    const status = modelStatus[model.key];
    return status?.status === 'available' || status?.status === 'deployed';
  };

  // 获取可用的模型列表
  const getAvailableModels = () => {
    const availableCategories = {};
    
    Object.entries(modelCategories).forEach(([categoryKey, category]) => {
      const availableModels = category.models.filter(isModelAvailable);
      if (availableModels.length > 0) {
        availableCategories[categoryKey] = {
          ...category,
          models: availableModels
        };
      }
    });
    
    return availableCategories;
  };

  const handleModelToggle = (modelKey) => {
    const newSelected = selectedModels.includes(modelKey)
      ? selectedModels.filter(m => m !== modelKey)
      : [...selectedModels, modelKey];
    onModelChange(newSelected);
  };

  const getStatusTag = (model) => {
    if (model.alwaysAvailable || isModelAvailable(model)) {
      return <Tag color="success" icon={<CheckCircleOutlined />}>可用</Tag>;
    }
    return null;
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
              {getStatusTag(model)}
            </div>
            <Paragraph 
              style={{ margin: '4px 0', color: '#666', fontSize: '12px' }}
            >
              {model.description}
            </Paragraph>
          </div>
        </Space>
      </div>
    </Card>
  );

  const availableCategories = getAvailableModels();
  const availableModelsCount = Object.values(availableCategories).reduce(
    (total, category) => total + category.models.length, 0
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
              （共 {availableModelsCount} 个可用模型）
            </Text>
          </div>

          {Object.keys(availableCategories).length === 0 && !loading && (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <Text type="secondary">暂无可用模型，请先到 Model Hub 部署模型</Text>
            </div>
          )}

          {Object.entries(availableCategories).map(([categoryKey, category], index) => (
            <div key={categoryKey}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                marginBottom: 12,
                marginTop: index !== 0 ? 20 : 0
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
              
              {index < Object.keys(availableCategories).length - 1 && (
                <div style={{ margin: '20px 0', borderTop: '1px solid #f0f0f0' }} />
              )}
            </div>
          ))}
        </Spin>
      </div>
    </Modal>
  );
};

export default PlaygroundModelSelector;