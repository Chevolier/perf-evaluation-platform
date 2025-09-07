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
  const [modelCategories, setModelCategories] = useState({
    bedrock: {
      title: 'Bedrock 模型',
      icon: <CloudOutlined />,
      color: '#1890ff',
      models: []
    },
    emd: {
      title: 'EMD 部署模型',
      icon: <ThunderboltOutlined />,
      color: '#52c41a',
      models: []
    }
  });

  // 从后端获取模型列表
  const fetchModelList = async () => {
    try {
      const response = await fetch('/api/model-list');
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success' && data.models) {
          // 处理Bedrock模型
          if (data.models.bedrock) {
            const bedrockModels = Object.entries(data.models.bedrock).map(([key, info]) => ({
              key,
              name: info.name,
              description: info.description,
              alwaysAvailable: true
            }));
            
            setModelCategories(prev => {
              const newState = {
                ...prev,
                bedrock: {
                  ...prev.bedrock,
                  models: bedrockModels
                }
              };
              return newState;
            });
          }
          
          // 处理EMD模型
          if (data.models.emd) {
            const emdModels = Object.entries(data.models.emd).map(([key, info]) => ({
              key,
              name: info.name,
              description: info.description,
              alwaysAvailable: false
            }));
            
            setModelCategories(prev => {
              const newState = {
                ...prev,
                emd: {
                  ...prev.emd,
                  models: emdModels
                }
              };
              return newState;
            });
          }
          
          // 在成功获取模型列表后检查模型状态
          return true;
        }
      } else {
      }
      return false;
    } catch (error) {
      return false;
    }
  };

  // 检查模型状态
  // const checkModelStatus = async () => {
  //   if (!visible) return;
    
  //   setLoading(true);
  //   try {
  //     // 获取所有模型列表
  //     const allModels = [
  //       ...modelCategories.bedrock.models.map(m => m.key),
  //       ...modelCategories.emd.models.map(m => m.key)
  //     ];
      
  //     const response = await fetch('/api/check-model-status', {
  //       method: 'POST',
  //       headers: {
  //         'Content-Type': 'application/json'
  //       },
  //       body: JSON.stringify({ models: allModels })
  //     });
      
  //     if (response.ok) {
  //       const data = await response.json();
  //       setModelStatus(data.model_status || {});
  //     }
  //   } catch (error) {
  //     console.error('检查模型状态失败:', error);
  //     message.error('获取模型状态失败');
  //   } finally {
  //     setLoading(false);
  //   }
  // };

  useEffect(() => {
    if (visible) {
      const initData = async () => {
        console.log('[Debug-PlaygroundSelector] 初始化组件数据');
        
        try {
          // 直接获取数据并处理，而不使用中间状态
          setLoading(true);
          const response = await fetch('/api/model-list');
          
          if (response.ok) {
            const data = await response.json();
            console.log('[Debug-PlaygroundSelector] 获取到模型列表数据:', data);
            
            if (data.status === 'success' && data.models) {
              // 构建bedrock模型列表
              const bedrockModels = data.models.bedrock ? 
                Object.entries(data.models.bedrock).map(([key, info]) => ({
                  key,
                  name: info.name,
                  description: info.description,
                  alwaysAvailable: true
                })) : [];
                
              // 构建emd模型列表
              const emdModels = data.models.emd ? 
                Object.entries(data.models.emd).map(([key, info]) => ({
                  key,
                  name: info.name,
                  description: info.description,
                  alwaysAvailable: false
                })) : [];
                
              console.log('[Debug-PlaygroundSelector] 处理后的模型列表:', { bedrockModels, emdModels });
                
              // 更新模型分类信息
              setModelCategories({
                bedrock: {
                  title: 'Bedrock 模型',
                  icon: <CloudOutlined />,
                  color: '#1890ff',
                  models: bedrockModels
                },
                emd: {
                  title: 'EMD 部署模型',
                  icon: <ThunderboltOutlined />,
                  color: '#52c41a',
                  models: emdModels
                }
              });
                
              // 立即准备模型列表并发送请求
              const allModels = [...bedrockModels.map(m => m.key), ...emdModels.map(m => m.key)];
              console.log('[Debug-PlaygroundSelector] 将发送到后端的模型列表:', allModels);
                
              if (allModels.length > 0) {
                // 直接调用API检查状态，而不使用中间函数
                const statusResponse = await fetch('/api/check-model-status', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json'
                  },
                  body: JSON.stringify({ models: allModels })
                });
                  
                if (statusResponse.ok) {
                  const statusData = await statusResponse.json();
                  console.log('[Debug-PlaygroundSelector] 获取到模型状态响应:', statusData);
                    
                  if (statusData.model_status) {
                    setModelStatus(statusData.model_status);
                  }
                } else {
                  console.log('[Debug-PlaygroundSelector] 状态检查失败, HTTP状态码:', statusResponse.status);
                  const errorText = await statusResponse.text();
                  console.log('[Debug-PlaygroundSelector] 错误内容:', errorText);
                }
              }
            }
          }
        } catch (error) {
          console.error('[Debug-PlaygroundSelector] 初始化数据异常:', error);
          message.error('获取模型数据失败');
        } finally {
          setLoading(false);
        }
      };
      
      initData();
    }
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