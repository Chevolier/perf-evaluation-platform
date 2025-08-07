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
  Button 
} from 'antd';
import { 
  RobotOutlined, 
  CloudOutlined, 
  ThunderboltOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  DeleteOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const ModelHubPage = () => {
  const [loading, setLoading] = useState(false);
  const [modelStatus, setModelStatus] = useState({});
  const [deployingModels, setDeployingModels] = useState(new Set());
  const deployingModelsRef = useRef(new Set());

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
        setModelStatus(prev => {
          const newStatus = { ...prev };
          
          // 更新状态，但保留正在部署的模型状态
          Object.entries(data.model_status || {}).forEach(([modelKey, status]) => {
            // 如果模型不在deployingModels中，或者已经完成/失败，则更新状态
            if (!deployingModelsRef.current.has(modelKey) || 
                status.status === 'deployed' || 
                status.status === 'available' || 
                status.status === 'error' || 
                status.status === 'failed') {
              newStatus[modelKey] = status;
            }
          });
          
          return newStatus;
        });
      }
    } catch (error) {
      console.error('检查模型状态失败:', error);
      message.error('获取模型状态失败');
    } finally {
      setLoading(false);
    }
  };

  // 部署模型
  const handleDeploy = async (modelKey) => {
    const newDeployingSet = new Set([...deployingModels, modelKey]);
    setDeployingModels(newDeployingSet);
    deployingModelsRef.current = newDeployingSet;
    
    try {
      const response = await fetch('/api/deploy-model', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ model: modelKey })
      });
      
      if (response.ok) {
        message.success(`${modelKey} 部署已开始，正在初始化...`);
        
        // 立即更新状态为部署中
        setModelStatus(prev => ({
          ...prev,
          [modelKey]: { status: 'deploying', message: '正在部署中...' }
        }));
        
        // 开始轮询部署状态
        startPollingDeploymentStatus(modelKey);
      } else {
        message.error(`${modelKey} 部署请求失败`);
        const newSet = new Set(deployingModelsRef.current);
        newSet.delete(modelKey);
        setDeployingModels(newSet);
        deployingModelsRef.current = newSet;
      }
    } catch (error) {
      console.error('部署模型失败:', error);
      message.error('部署请求失败');
      const newSet = new Set(deployingModelsRef.current);
      newSet.delete(modelKey);
      setDeployingModels(newSet);
      deployingModelsRef.current = newSet;
    }
  };

  // 轮询部署状态
  const startPollingDeploymentStatus = (modelKey) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch('/api/check-model-status', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ models: [modelKey] })
        });
        
        if (response.ok) {
          const data = await response.json();
          const status = data.model_status?.[modelKey];
          
          // 如果部署完成或失败，停止轮询
          if (status && (status.status === 'deployed' || status.status === 'available' || status.status === 'error' || status.status === 'failed')) {
            clearInterval(pollInterval);
            
            // 更新模型状态
            setModelStatus(prev => ({
              ...prev,
              [modelKey]: status
            }));
            
            // 从部署中状态移除
            const newSet = new Set(deployingModelsRef.current);
            newSet.delete(modelKey);
            setDeployingModels(newSet);
            deployingModelsRef.current = newSet;
            
            if (status.status === 'deployed' || status.status === 'available') {
              message.success(`${modelKey} 部署成功！`);
            } else if (status.status === 'error' || status.status === 'failed') {
              message.error(`${modelKey} 部署失败: ${status.message || '未知错误'}`);
            }
          } else {
            // 部署仍在进行中，更新状态但保持在deployingModels中
            setModelStatus(prev => ({
              ...prev,
              [modelKey]: status || { status: 'deploying', message: '部署中...' }
            }));
          }
        }
      } catch (error) {
        console.error('轮询部署状态失败:', error);
      }
    }, 3000); // 每3秒轮询一次

    // 30分钟后停止轮询（防止无限轮询）
    setTimeout(() => {
      clearInterval(pollInterval);
      const newSet = new Set(deployingModelsRef.current);
      newSet.delete(modelKey);
      setDeployingModels(newSet);
      deployingModelsRef.current = newSet;
      message.warning(`${modelKey} 部署超时，请手动刷新状态`);
    }, 30 * 60 * 1000);
  };

  useEffect(() => {
    checkModelStatus();
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
      case 'deploying':
        return <Tag color="processing">部署中</Tag>;
      default:
        return <Tag color="default">未知</Tag>;
    }
  };

  const getDeployButton = (model) => {
    if (model.alwaysAvailable) return null;
    
    const status = modelStatus[model.key];
    const isDeploying = deployingModels.has(model.key);
    
    if (status?.status === 'available' || status?.status === 'deployed') {
      return null;
    }
    
    if (status?.status === 'deploying' || isDeploying) {
      return (
        <Button 
          type="primary" 
          size="small" 
          loading
          disabled
        >
          部署中
        </Button>
      );
    }
    
    return (
      <Button 
        type="primary" 
        size="small"
        icon={<PlayCircleOutlined />}
        onClick={() => handleDeploy(model.key)}
        loading={isDeploying}
      >
        部署
      </Button>
    );
  };

  const getCleanupButton = (model) => {
    if (model.alwaysAvailable) return null;
    
    const status = modelStatus[model.key];
    const isDeploying = deployingModels.has(model.key);
    
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
          清理资源
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

  const renderModelCard = (model, category) => (
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
        <div style={{ marginLeft: 16 }}>
          <Space direction="vertical" size="small">
            {getDeployButton(model)}
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
          <Title level={2} style={{ margin: 0 }}>Model Hub</Title>
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
                  {renderModelCard(model, category)}
                </Col>
              ))}
            </Row>
            
            {categoryKey !== 'emd' && <Divider />}
          </div>
        ))}
      </Spin>
    </div>
  );
};

export default ModelHubPage;