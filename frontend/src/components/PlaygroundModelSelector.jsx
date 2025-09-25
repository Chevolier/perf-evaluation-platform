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
  const [modelCategories, setModelCategories] = useState({});

  const categoryPresets = React.useMemo(() => ({
    bedrock: {
      title: 'Bedrock 模型',
      icon: <CloudOutlined />,
      color: '#1890ff',
      alwaysAvailable: true
    },
    emd: {
      title: 'EMD 部署模型',
      icon: <ThunderboltOutlined />,
      color: '#52c41a',
      alwaysAvailable: false
    },
    external: {
      title: '外部部署',
      icon: <RobotOutlined />,
      color: '#fa8c16',
      alwaysAvailable: true
    }
  }), []);

  const buildCategories = React.useCallback((modelsData = {}) => {
    const categories = {};
    const modelKeys = [];

    Object.entries(modelsData).forEach(([categoryKey, categoryModels]) => {
      const preset = categoryPresets[categoryKey] || {
        title: categoryKey,
        icon: <RobotOutlined />,
        color: '#722ed1',
        alwaysAvailable: true
      };

      const models = Object.entries(categoryModels || {}).map(([key, info]) => {
        modelKeys.push(key);
        const statusInfo = info.deployment_status || {};
        const alwaysAvailable = Object.prototype.hasOwnProperty.call(info, 'always_available')
          ? Boolean(info.always_available)
          : (preset.alwaysAvailable ?? true);

        return {
          key,
          name: info.name || key,
          description: info.description || '',
          alwaysAvailable,
          deployment_method: info.deployment_method,
          status: statusInfo,
          raw: info
        };
      });

      categories[categoryKey] = {
        title: preset.title,
        icon: preset.icon,
        color: preset.color,
        models
      };
    });

    return { categories, modelKeys };
  }, [categoryPresets]);

  useEffect(() => {
    if (!visible) {
      return;
    }

    let cancelled = false;

    const initData = async () => {
      setLoading(true);
      try {
        const response = await fetch('/api/model-list');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        if (data.status !== 'success' || !data.models) {
          throw new Error(data.message || '获取模型数据失败');
        }

        const { categories, modelKeys } = buildCategories(data.models);
        if (!cancelled) {
          setModelCategories(categories);
        }

        if (modelKeys.length === 0) {
          if (!cancelled) {
            setModelStatus({});
          }
          return;
        }

        const statusResponse = await fetch('/api/check-model-status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ models: modelKeys })
        });

        if (!statusResponse.ok) {
          const errorText = await statusResponse.text();
          throw new Error(errorText || `Status check failed with ${statusResponse.status}`);
        }

        const statusData = await statusResponse.json();
        if (!cancelled && statusData.model_status) {
          setModelStatus(statusData.model_status);
        }
      } catch (error) {
        if (!cancelled) {
          console.error('[PlaygroundModelSelector] 初始化数据异常:', error);
          message.error(error?.message || '获取模型数据失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    initData();
    return () => {
      cancelled = true;
    };
  }, [visible, buildCategories]);

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
      <div>
        <Space align="start" style={{ width: '100%' }}>
          <Checkbox 
            checked={selectedModels.includes(model.key)}
            onChange={(e) => {
              e.stopPropagation();
              handleModelToggle(model.key);
            }}
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
          <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text type="secondary">
              已选择 <Text strong style={{ color: '#1890ff' }}>{selectedModels.length}</Text> 个模型
              （共 {availableModelsCount} 个可用模型）
            </Text>
            <div>
              {selectedModels.length > 0 && (
                <Button 
                  type="link" 
                  size="small"
                  onClick={() => onModelChange([])}
                  style={{ color: '#999', marginRight: 8 }}
                >
                  清除所有选择
                </Button>
              )}
              <Button 
                type="link" 
                size="small"
                onClick={() => {
                  // Clear localStorage cache
                  localStorage.removeItem('playground_selectedModels');
                  localStorage.removeItem('playground_dataset');
                  localStorage.removeItem('playground_params');
                  localStorage.removeItem('playground_inferenceResults');
                  localStorage.removeItem('playground_originalFiles');
                  localStorage.removeItem('playground_inputMode');
                  localStorage.removeItem('playground_manualConfig');
                  onModelChange([]);
                  window.location.reload();
                }}
                style={{ color: '#ff4d4f' }}
              >
                清除缓存
              </Button>
            </div>
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
