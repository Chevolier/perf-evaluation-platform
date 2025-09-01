import React, { useState, useEffect, useRef } from 'react';
import { 
  Card, 
  Typography, 
  Tag, 
  Row, 
  Col, 
  Space, 
  Divider, 
  Spin, 
  message, 
  Button,
  Checkbox,
  Select,
  Form,
  InputNumber 
} from 'antd';
import { 
  RobotOutlined, 
  CloudOutlined, 
  ThunderboltOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  RocketOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const ModelHubPage = () => {
  const [loading, setLoading] = useState(false);
  
  // Load state from localStorage
  const [modelStatus, setModelStatus] = useState(() => {
    try {
      const saved = localStorage.getItem('modelHub_modelStatus');
      return saved ? JSON.parse(saved) : {};
    } catch (error) {
      console.error('Failed to load model status from localStorage:', error);
      return {};
    }
  });
  
  const [selectedModels, setSelectedModels] = useState(() => {
    try {
      const saved = localStorage.getItem('modelHub_selectedModels');
      return saved ? JSON.parse(saved) : [];
    } catch (error) {
      console.error('Failed to load selected models from localStorage:', error);
      return [];
    }
  });
  
  const [deploymentConfig, setDeploymentConfig] = useState(() => {
    try {
      const saved = localStorage.getItem('modelHub_deploymentConfig');
      return saved ? JSON.parse(saved) : {
        method: 'SageMaker Endpoint',
        framework: 'vllm',
        machineType: 'g5.2xlarge',
        tpSize: 1,
        dpSize: 1
      };
    } catch (error) {
      console.error('Failed to load deployment config from localStorage:', error);
      return {
        method: 'SageMaker Endpoint',
        framework: 'vllm',
        machineType: 'g5.2xlarge',
        tpSize: 1,
        dpSize: 1
      };
    }
  });
  // const [deployingModels, setDeployingModels] = useState(new Set());
  // const deployingModelsRef = useRef(new Set());
  const [modelCategories, setModelCategories] = useState({
    bedrock: {
      title: 'Bedrock 模型',
      icon: <CloudOutlined />,
      color: '#1890ff',
      models: []
    },
    emd: {
      title: '部署模型',
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

  // 批量部署模型
  const handleBatchDeploy = async () => {
    if (selectedModels.length === 0) {
      message.warning('请选择要部署的模型');
      return;
    }
    
    try {
      const response = await fetch('/api/deploy-models', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          models: selectedModels,
          config: deploymentConfig
        })
      });
      
      if (response.ok) {
        message.success(`已开始部署 ${selectedModels.length} 个模型`);
        
        // 更新所有选中模型的状态为部署中
        const newStatus = {};
        selectedModels.forEach(modelKey => {
          newStatus[modelKey] = { status: 'init', message: '初始化' };
        });
        
        setModelStatus(prev => ({
          ...prev,
          ...newStatus
        }));
        
        // 清空选择
        setSelectedModels([]);
        
      } else {
        message.error('批量部署请求失败');
      }
    } catch (error) {
      console.error('批量部署模型失败:', error);
      message.error('部署请求失败');
    }
  };

  // 处理模型选择
  const handleModelSelection = (modelKey, checked) => {
    setSelectedModels(prev => {
      if (checked) {
        return [...prev, modelKey];
      } else {
        return prev.filter(key => key !== modelKey);
      }
    });
  };

  // Save modelStatus to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('modelHub_modelStatus', JSON.stringify(modelStatus));
    } catch (error) {
      console.error('Failed to save model status to localStorage:', error);
    }
  }, [modelStatus]);

  // Save selectedModels to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('modelHub_selectedModels', JSON.stringify(selectedModels));
    } catch (error) {
      console.error('Failed to save selected models to localStorage:', error);
    }
  }, [selectedModels]);

  // Save deploymentConfig to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('modelHub_deploymentConfig', JSON.stringify(deploymentConfig));
    } catch (error) {
      console.error('Failed to save deployment config to localStorage:', error);
    }
  }, [deploymentConfig]);

  useEffect(() => {
    const initData = async () => {
      console.log('[Debug] 初始化组件数据');
      
      try {
        // 直接获取数据并处理，而不使用中间状态
        const response = await fetch('/api/model-list');
        if (response.ok) {
          const data = await response.json();
          console.log('[Debug] 获取到模型列表数据:', data);
          
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
              
            console.log('[Debug] 处理后的模型列表:', { bedrockModels, emdModels });
              
            // 更新模型分类信息
            setModelCategories({
              bedrock: {
                title: 'Bedrock 模型',
                icon: <CloudOutlined />,
                color: '#1890ff',
                models: bedrockModels
              },
              emd: {
                title: '部署模型',
                icon: <ThunderboltOutlined />,
                color: '#52c41a',
                models: emdModels
              }
            });
              
            // 立即准备模型列表并发送请求
            const allModels = [...bedrockModels.map(m => m.key), ...emdModels.map(m => m.key)];
            console.log('[Debug] 将发送到后端的模型列表:', allModels);
              
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
                console.log('[Debug] 获取到模型状态响应:', statusData);
                  
                if (statusData.model_status) {
                  setModelStatus(statusData.model_status);
                }
              } else {
                console.log('[Debug] 状态检查失败, HTTP状态码:', statusResponse.status);
                const errorText = await statusResponse.text();
                console.log('[Debug] 错误内容:', errorText);
              }
            }
          }
        }
      } catch (error) {
        console.error('[Debug] 初始化数据异常:', error);
      } finally {
        setLoading(false);
      }
    };
    
    initData();
  }, []);

  const getStatusTag = (model) => {
    if (model.alwaysAvailable) {
      return <Tag color="success" icon={<CheckCircleOutlined />}>可用</Tag>;
    }
    
    const status = modelStatus[model.key];
    if (!status) return <Tag color="default">检查中</Tag>;

    switch (status.status) {
      case 'available':
      case 'deployed':
        return <Tag color="success" icon={<CheckCircleOutlined />}>已部署</Tag>;
      case 'not_deployed':
        return <Tag color="warning">未部署</Tag>;
      case 'failed':
        return <Tag color="warning">部署失败</Tag>;
      case 'inprogress':
        return <Tag color="processing">部署中</Tag>;
      case 'init':
        return <Tag color="processing">初始化</Tag>;
      default:
        return <Tag color="default">未知</Tag>;
    }
  };

  const getModelCheckbox = (model) => {
    if (model.alwaysAvailable) return null;
    
    const status = modelStatus[model.key];
    
    // 如果已部署或正在部署中，不显示复选框
    if (status?.status === 'available' || status?.status === 'deployed' || 
        status?.status === 'inprogress' || status?.status === 'init') {
      return null;
    }
    
    return (
      <Checkbox
        checked={selectedModels.includes(model.key)}
        onChange={(e) => handleModelSelection(model.key, e.target.checked)}
      >
        选择部署
      </Checkbox>
    );
  };

  const getCleanupButton = (model) => {
    if (model.alwaysAvailable) return null;
    
    const status = modelStatus[model.key];
    
    // 只有在已部署状态下才显示清理按钮
    if (status?.status === 'available' || status?.status === 'deployed') {
      return (
        <Button 
          danger
          size="small"
          icon={<DeleteOutlined />}
          onClick={() => handleCleanup(model.key)}
          style={{ width: '100%' }}
        >
          停止
        </Button>
      );
    }
    
    return null;
  };

  const handleCleanup = (modelKey) => {
    // TODO: 实现清理资源逻辑
    console.log(`Cleanup requested for model: ${modelKey}`);
    // 这里以后会调用清理API
    // message.info(`${modelKey} 清理功能开发中...`);
  };

  const renderModelCard = (model) => (
    <Card
      key={model.key}
      size="small"
      style={{ 
        marginBottom: 16,
        borderRadius: 8
      }}
      hoverable
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <Text strong style={{ fontSize: '16px' }}>{model.name}</Text>
            {getStatusTag(model)}
          </div>
          <Paragraph 
            style={{ margin: '0 0 8px 0', color: '#666', fontSize: '14px' }}
          >
            {model.description}
          </Paragraph>
        </div>
        <div style={{ marginLeft: 2 }}>
          <Space direction="vertical" size="small">
            {getModelCheckbox(model)}
            {!model.alwaysAvailable && getCleanupButton(model)}
          </Space>
        </div>
      </div>
    </Card>
  );

  return (
    <div style={{ padding: '24px', background: '#f5f5f5', minHeight: '100vh' }}>
      <div style={{ marginBottom: 24 }}>
        <Space>
          <RobotOutlined style={{ fontSize: '24px', color: '#1890ff' }} />
          <Title level={2} style={{ margin: 0 }}>模型商店</Title>
        </Space>
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          管理和部署所有可用的推理模型
        </Text>
      </div>

      <Spin spinning={loading}>
        {Object.entries(modelCategories).map(([categoryKey, category]) => (
          <div key={categoryKey} style={{ marginBottom: 32 }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              marginBottom: 16
            }}>
              <Space>
                {category.icon}
                <Title level={3} style={{ margin: 0, color: category.color }}>
                  {category.title}
                </Title>
              </Space>
            </div>
            
            <Row gutter={[16, 16]}>
              {category.models.map(model => (
                <Col key={model.key} xs={24} sm={12} lg={8} xl={6}>
                  {renderModelCard(model)}
                </Col>
              ))}
            </Row>
            
            {categoryKey !== 'emd' && <Divider />}
          </div>
        ))}
        {/* 部署配置面板 */}
        {Object.values(modelCategories).some(category => 
          category.models.some(model => 
            !model.alwaysAvailable && 
            (!modelStatus[model.key] || 
             ['not_deployed', 'failed'].includes(modelStatus[model.key]?.status))
          )
        ) && (
          <Card 
            title={
              <Space>
                <RocketOutlined />
                <span>部署配置</span>
              </Space>
            }
            style={{ marginTop: 24 }}
          >
            <Form layout="vertical">
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="部署方式">
                    <Select
                      value={deploymentConfig.method}
                      onChange={(value) => setDeploymentConfig(prev => ({ ...prev, method: value }))}
                      options={[
                        { value: 'SageMaker Endpoint', label: 'SageMaker Endpoint' },
                        { value: 'SageMaker HyperPod', label: 'SageMaker HyperPod' },
                        { value: 'EKS', label: 'EKS' },
                        { value: 'EC2', label: 'EC2' }
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="推理框架">
                    <Select
                      value={deploymentConfig.framework}
                      onChange={(value) => setDeploymentConfig(prev => ({ ...prev, framework: value }))}
                      options={[
                        { value: 'vllm', label: 'vLLM' },
                        { value: 'sglang', label: 'SGLang' },
                        { value: 'tgi', label: 'Text Generation Inference' },
                        { value: 'transformers', label: 'Transformers' }
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="机型选择">
                    <Select
                      value={deploymentConfig.machineType}
                      onChange={(value) => setDeploymentConfig(prev => ({ ...prev, machineType: value }))}
                      options={[
                        { value: 'g5.2xlarge', label: 'g5.2xlarge (1 A10G, 24GB RAM)' },
                        { value: 'g6e.2xlarge', label: 'g6e.2xlarge (1 L40S, 48GB RAM)' },
                        { value: 'g5.12xlarge', label: 'g5.12xlarge (4 A10G, 96GB RAM)' },
                        { value: 'g6e.12xlarge', label: 'g6.48xlarge (4 L40S , 384GB RAM)' },
                        { value: 'p5.48xlarge', label: 'p5.48xlarge (8 H100, 640GB RAM)' },
                        { value: 'p5en.48xlarge', label: 'p5en.48xlarge (8 H200, 1128GB RAM)' },
                        { value: 'p4d.24xlarge', label: 'p4d.24xlarge (8 A100, 320GB RAM)' },  
                        { value: 'p4de.24xlarge', label: 'p4d.24xlarge (8 A100, 640GB RAM)' },
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="推理参数">
                    <Space.Compact style={{ width: '100%' }}>
                      <InputNumber
                        addonBefore="TP"
                        min={1}
                        max={8}
                        value={deploymentConfig.tpSize}
                        onChange={(value) => setDeploymentConfig(prev => ({ ...prev, tpSize: value }))}
                        style={{ width: '50%' }}
                      />
                      <InputNumber
                        addonBefore="DP"
                        min={1}
                        max={8}
                        value={deploymentConfig.dpSize}
                        onChange={(value) => setDeploymentConfig(prev => ({ ...prev, dpSize: value }))}
                        style={{ width: '50%' }}
                      />
                    </Space.Compact>
                  </Form.Item>
                </Col>
              </Row>
              <Row>
                <Col span={24}>
                  <Space>
                    <Button 
                      type="primary" 
                      onClick={handleBatchDeploy}
                      disabled={selectedModels.length === 0}
                      size="large"
                    >
                      部署选中模型 ({selectedModels.length})
                    </Button>
                    <Button 
                      onClick={() => setSelectedModels([])}
                      disabled={selectedModels.length === 0}
                    >
                      清空选择
                    </Button>
                  </Space>
                </Col>
              </Row>
            </Form>
          </Card>
        )}
      </Spin>
    </div>
  );
};

export default ModelHubPage;