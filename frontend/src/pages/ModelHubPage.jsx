import React, { useState, useEffect, useMemo, useCallback } from 'react';
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
  InputNumber,
  Skeleton 
} from 'antd';
import { 
  RobotOutlined, 
  CloudOutlined, 
  ThunderboltOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  RocketOutlined,
  ReloadOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const ModelHubPage = () => {
  const [initialLoading, setInitialLoading] = useState(true);
  const [statusLoading, setStatusLoading] = useState(false);
  
  
  // Always start with empty model status to force fresh fetch
  const [modelStatus, setModelStatus] = useState(() => {
    // Clear any cached status to ensure fresh data on every load
    localStorage.removeItem('modelHub_modelStatus');
    localStorage.removeItem('modelHub_cacheTimestamp');
    return {};
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
    // Clear the old localStorage data first to ensure fresh defaults
    localStorage.removeItem('modelHub_deploymentConfig');

    // Return the default config
    return {
      method: 'EC2',
      framework: 'vllm',
      serviceType: 'vllm_realtime',
      machineType: 'g5.2xlarge',
      tpSize: 1,
      dpSize: 1
    };
  });
  // Memoized category templates to avoid recreating icons
  const categoryTemplates = useMemo(() => ({
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
  }), []);

  const [modelCategories, setModelCategories] = useState(categoryTemplates);
  

  // 批量部署模型 (memoized for performance)
  const handleBatchDeploy = useCallback(async () => {
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
          instance_type: deploymentConfig.machineType,
          engine_type: deploymentConfig.framework,
          service_type: deploymentConfig.serviceType
        })
      });
      
      if (response.ok) {
        const responseData = await response.json();
        console.log('Deployment response:', responseData);
        
        if (responseData.status === 'success') {
          // Check individual model deployment results
          const results = responseData.results || {};
          let successCount = 0;
          let failedCount = 0;
          
          const newStatus = {};
          selectedModels.forEach(modelKey => {
            const modelResult = results[modelKey];
            if (modelResult && modelResult.success) {
              newStatus[modelKey] = { 
                status: 'inprogress', 
                message: '部署中',
                tag: modelResult.tag
              };
              successCount++;
            } else {
              newStatus[modelKey] = { 
                status: 'failed', 
                message: modelResult?.error || '部署失败'
              };
              failedCount++;
            }
          });
          
          // Batch state updates to reduce re-renders
          React.startTransition(() => {
            setModelStatus(prev => ({
              ...prev,
              ...newStatus
            }));
            
            // 清空选择
            setSelectedModels([]);
          });
          
          // Show appropriate message
          if (failedCount === 0) {
            message.success(`已开始部署 ${successCount} 个模型`);
          } else if (successCount === 0) {
            message.error(`${failedCount} 个模型部署失败`);
          } else {
            message.warning(`${successCount} 个模型开始部署，${failedCount} 个模型部署失败`);
          }
        } else {
          message.error(`部署请求失败: ${responseData.message || '未知错误'}`);
        }
        
      } else {
        const errorText = await response.text();
        console.error('Deployment failed:', response.status, errorText);
        message.error(`批量部署请求失败 (${response.status}): ${errorText}`);
      }
    } catch (error) {
      console.error('批量部署模型失败:', error);
      message.error('部署请求失败');
    }
  }, [selectedModels, deploymentConfig]);

  // 处理模型选择 (memoized for performance)
  const handleModelSelection = useCallback((modelKey, checked) => {
    setSelectedModels(prev => {
      if (checked) {
        return [...prev, modelKey];
      } else {
        return prev.filter(key => key !== modelKey);
      }
    });
  }, []);

  // Save only non-status data to localStorage (keep selected models and config)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      try {
        // Only save selected models and deployment config, not status (always fetch fresh)
        const batch = {
          modelHub_selectedModels: JSON.stringify(selectedModels),
          modelHub_deploymentConfig: JSON.stringify(deploymentConfig)
        };
        
        // Use requestIdleCallback if available for non-blocking writes
        const writeBatch = () => {
          Object.entries(batch).forEach(([key, value]) => {
            try {
              localStorage.setItem(key, value);
            } catch (error) {
              console.warn(`Failed to save ${key}:`, error);
            }
          });
        };
        
        if (window.requestIdleCallback) {
          window.requestIdleCallback(writeBatch, { timeout: 1000 });
        } else {
          setTimeout(writeBatch, 0);
        }
      } catch (error) {
        console.error('Failed to batch save localStorage:', error);
      }
    }, 300); // Debounce localStorage writes
    
    return () => clearTimeout(timeoutId);
  }, [selectedModels, deploymentConfig]);

  // Always fetch fresh data - no caching to ensure correct status
  const fetchModelData = useCallback(async () => {
    try {
      console.log('🚀 Fetching fresh model data (no cache)');
      
      // Add timeout handling to prevent hanging on throttled requests
      const fetchWithTimeout = (url, options = {}, timeout = 10000) => {
        return Promise.race([
          fetch(url, options),
          new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Request timeout')), timeout)
          )
        ]);
      };
      
      // First fetch model list to get the available models
      console.log('🔍 DEBUG: Fetching model list first...');
      const modelListResponse = await fetchWithTimeout('/api/model-list', {}, 15000);
      
      let modelListData = null;
      let deployableModelKeys = [];
      
      // Process model list response
      if (modelListResponse.ok) {
        const data = await modelListResponse.json();
        
        if (data.status === 'success' && data.models) {
          modelListData = data.models;
          
          // Process models with memoized transformation
          const bedrockModels = data.models.bedrock ? 
            Object.entries(data.models.bedrock).map(([key, info]) => ({
              key,
              name: info.name,
              description: info.description,
              alwaysAvailable: true
            })) : [];
            
          const emdModels = data.models.emd ? 
            Object.entries(data.models.emd).map(([key, info]) => ({
              key,
              name: info.name,
              description: info.description,
              alwaysAvailable: false
            })) : [];
            
          // Extract deployable model keys for status check
          deployableModelKeys = emdModels.map(m => m.key);
          console.log('🔍 DEBUG: deployableModelKeys extracted:', deployableModelKeys);
            
          // Batch UI updates to reduce re-renders
          React.startTransition(() => {
            setModelCategories({
              bedrock: {
                ...categoryTemplates.bedrock,
                models: bedrockModels
              },
              emd: {
                ...categoryTemplates.emd,
                models: emdModels
              }
            });
            
            // Keep loading state until status is fetched
            // setInitialLoading(false); // Don't stop loading yet
          });
        }
      }
      
      // Now fetch status for deployable models
      console.log('🔍 DEBUG: Fetching status for deployable models:', deployableModelKeys);
      if (deployableModelKeys.length > 0) {
        try {
          const statusResponse = await fetchWithTimeout('/api/check-model-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ models: deployableModelKeys })
          }, 10000);
          
          if (statusResponse.ok) {
            const data = await statusResponse.json();
            console.log('🔍 DEBUG: Status response data:', data);
            if (data.model_status) {
              setModelStatus(prev => ({
                ...prev,
                ...data.model_status
              }));
            }
            // Status check completed successfully
            setInitialLoading(false);
          } else {
            console.warn('Status response not ok:', statusResponse.status);
            // Status check failed but completed
            setInitialLoading(false);
          }
        } catch (error) {
          console.error('Status fetch failed:', error);
          // Handle failed status check - set default not_deployed status
          const fallbackStatus = {};
          deployableModelKeys.forEach(modelKey => {
            fallbackStatus[modelKey] = {
              status: 'not_deployed',
              message: 'Status check failed - may need to refresh'
            };
          });
          setModelStatus(prev => ({
            ...prev,
            ...fallbackStatus
          }));
          // Status check failed but completed
          setInitialLoading(false);
        }
      } else {
        // No deployable models, stop loading
        setInitialLoading(false);
      }
      
      // No caching - always use fresh data
    } catch (error) {
      console.error('Failed to fetch model data:', error);
    } finally {
      setInitialLoading(false);
    }
  }, [categoryTemplates]);

  useEffect(() => {
    fetchModelData();
  }, [fetchModelData]);

  // Polling for models in deleting or deploying status
  useEffect(() => {
    const pollInterval = setInterval(() => {
      // Check if there are any models in transitional states
      const hasTransitionalModels = Object.values(modelStatus).some(status => 
        ['deleting', 'inprogress', 'init'].includes(status?.status)
      );
      
      if (hasTransitionalModels) {
        console.log('🔄 Polling for transitional model status updates...');
        // Fetch only status for models that need updates
        const transitionalModelKeys = Object.keys(modelStatus).filter(key => 
          ['deleting', 'inprogress', 'init'].includes(modelStatus[key]?.status)
        );
        
        if (transitionalModelKeys.length > 0) {
          fetch('/api/check-model-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ models: transitionalModelKeys })
          })
          .then(response => response.json())
          .then(data => {
            if (data.model_status) {
              console.log('🔄 Status update received:', data.model_status);
              setModelStatus(prev => ({
                ...prev,
                ...data.model_status
              }));
            }
          })
          .catch(error => {
            console.warn('Status polling failed:', error);
          });
        }
      }
    }, 10000); // Poll every 10 seconds
    
    return () => clearInterval(pollInterval);
  }, [modelStatus]);

  const handleCleanup = useCallback(async (modelKey) => {
    try {
      console.log(`Starting cleanup for model: ${modelKey}`);
      
      // Show loading state immediately
      setModelStatus(prev => ({
        ...prev,
        [modelKey]: {
          ...prev[modelKey],
          status: 'deleting',
          message: '正在停止模型...'
        }
      }));
      
      const response = await fetch('/api/delete-model', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          model_key: modelKey
        })
      });
      
      if (response.ok) {
        const responseData = await response.json();
        console.log('Deletion response:', responseData);
        
        if (responseData.success) {
          message.success(`${modelKey} 停止成功`);
          
          // Update status to deleting (will be updated by status polling)
          setModelStatus(prev => ({
            ...prev,
            [modelKey]: {
              status: 'deleting',
              message: '正在停止中...',
              tag: responseData.tag
            }
          }));
          
        } else {
          message.error(`停止失败: ${responseData.error || '未知错误'}`);
          
          // Revert status on failure
          setModelStatus(prev => ({
            ...prev,
            [modelKey]: {
              ...prev[modelKey],
              message: `停止失败: ${responseData.error || '未知错误'}`
            }
          }));
        }
        
      } else {
        const errorText = await response.text();
        console.error('Deletion failed:', response.status, errorText);
        message.error(`停止请求失败 (${response.status}): ${errorText}`);
        
        // Revert status on failure
        setModelStatus(prev => ({
          ...prev,
          [modelKey]: {
            ...prev[modelKey],
            message: `停止请求失败: ${errorText}`
          }
        }));
      }
    } catch (error) {
      console.error('停止模型失败:', error);
      message.error('停止请求失败');
      
      // Revert status on error
      setModelStatus(prev => ({
        ...prev,
        [modelKey]: {
          ...prev[modelKey],
          message: '停止请求失败'
        }
      }));
    }
  }, []);



  const getStatusTag = useCallback((model) => {
    if (model.alwaysAvailable) {
      return <Tag color="success" icon={<CheckCircleOutlined />}>可用</Tag>;
    }
    
    const status = modelStatus[model.key];
    
    // Add timeout for "检查中..." status - if no status after 15 seconds, show error
    if (!status) {
      if (initialLoading) {
        return <Tag color="processing">检查中...</Tag>;
      } else {
        // If not initial loading and still no status, show error state
        return <Tag color="error">检查失败</Tag>;
      }
    }

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
      case 'deleting':
        return <Tag color="processing">停止中</Tag>;
      case 'init':
        return <Tag color="processing">初始化</Tag>;
      default:
        return <Tag color="default">未知</Tag>;
    }
  }, [modelStatus, initialLoading]);

  const getModelCheckbox = useCallback((model) => {
    if (model.alwaysAvailable) return null;
    
    const status = modelStatus[model.key];
    
    // 如果已部署或正在部署中或正在删除中，不显示复选框
    if (status?.status === 'available' || status?.status === 'deployed' || 
        status?.status === 'inprogress' || status?.status === 'init' || 
        status?.status === 'deleting') {
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
  }, [modelStatus, selectedModels, handleModelSelection]);

  const getCleanupButton = useCallback((model) => {
    if (model.alwaysAvailable) return null;
    
    const status = modelStatus[model.key];
    
    // 只有在已部署状态下才显示清理按钮，删除过程中显示禁用状态
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
    } else if (status?.status === 'deleting') {
      return (
        <Button 
          danger
          size="small"
          icon={<DeleteOutlined />}
          loading
          disabled
          style={{ width: '100%' }}
        >
          停止中
        </Button>
      );
    }
    
    return null;
  }, [modelStatus, handleCleanup]);

  // Skeleton component for loading states
  const SkeletonCard = useMemo(() => (
    <Card
      size="small"
      style={{ 
        marginBottom: 16,
        borderRadius: 8
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <Skeleton.Input style={{ width: 150, height: 20 }} active />
            <Skeleton.Button style={{ width: 60, height: 24 }} active />
          </div>
          <Skeleton active paragraph={{ rows: 2, width: ['100%', '80%'] }} title={false} />
        </div>
        <div style={{ marginLeft: 16, width: 80 }}>
          <Skeleton.Button style={{ width: '100%', height: 32 }} active />
        </div>
      </div>
    </Card>
  ), []);

  const renderModelCard = useCallback((model) => (
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
  ), [getStatusTag, getModelCheckbox, getCleanupButton]);

  return (
    <div style={{ padding: '24px', background: '#f5f5f5', minHeight: '100vh' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Space>
              <RobotOutlined style={{ fontSize: '24px', color: '#1890ff' }} />
              <Title level={2} style={{ margin: 0 }}>模型商店</Title>
            </Space>
            <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
              管理和部署所有可用的推理模型
            </Text>
          </div>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              console.log('🔄 Manual refresh triggered - clearing cache');
              // Clear localStorage cache to force fresh data
              localStorage.removeItem('modelHub_modelStatus');
              localStorage.removeItem('modelHub_cacheTimestamp');
              // Set loading state to show "检查中..." instead of "检查失败"
              setInitialLoading(true);
              // Don't clear modelStatus immediately - let fetchModelData handle it
              // Trigger fresh data fetch
              fetchModelData();
            }}
            loading={initialLoading}
          >
            刷新状态
          </Button>
        </div>
      </div>

      {/* Show UI structure immediately, even during initial loading */}
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
              {statusLoading && categoryKey === 'emd' && (
                <Spin size="small" />
              )}
            </Space>
          </div>
          
          <Row gutter={[16, 16]}>
            {initialLoading ? (
              // Show skeleton cards during initial loading
              Array.from({ length: 6 }, (_, index) => (
                <Col key={`skeleton-${categoryKey}-${index}`} xs={24} sm={12} lg={8} xl={6}>
                  {SkeletonCard}
                </Col>
              ))
            ) : (
              // Show actual model cards once data is loaded
              category.models.map(model => (
                <Col key={model.key} xs={24} sm={12} lg={8} xl={6}>
                  {renderModelCard(model)}
                </Col>
              ))
            )}
          </Row>
          
          {categoryKey !== 'emd' && <Divider />}
        </div>
      ))}
      
      {/* Show skeleton structure if no categories loaded yet */}
      {initialLoading && Object.keys(modelCategories).length === 0 && (
        <>
          <div style={{ marginBottom: 32 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
              <Space>
                <CloudOutlined />
                <Title level={3} style={{ margin: 0, color: '#1890ff' }}>
                  Bedrock 模型
                </Title>
              </Space>
            </div>
            <Row gutter={[16, 16]}>
              {Array.from({ length: 4 }, (_, index) => (
                <Col key={`bedrock-skeleton-${index}`} xs={24} sm={12} lg={8} xl={6}>
                  {SkeletonCard}
                </Col>
              ))}
            </Row>
            <Divider />
          </div>
          
          <div style={{ marginBottom: 32 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
              <Space>
                <ThunderboltOutlined />
                <Title level={3} style={{ margin: 0, color: '#52c41a' }}>
                  部署模型
                </Title>
              </Space>
            </div>
            <Row gutter={[16, 16]}>
              {Array.from({ length: 6 }, (_, index) => (
                <Col key={`emd-skeleton-${index}`} xs={24} sm={12} lg={8} xl={6}>
                  {SkeletonCard}
                </Col>
              ))}
            </Row>
          </div>
        </>
      )}
      {/* 部署配置面板 - 只有在有可部署模型时显示 */}
      {useMemo(() => {
        const hasDeployableModels = Object.values(modelCategories).some(category => 
          category.models.some(model => 
            !model.alwaysAvailable && 
            (!modelStatus[model.key] || 
             ['not_deployed', 'failed'].includes(modelStatus[model.key]?.status))
          )
        );

        if (!hasDeployableModels) return null;

        return (
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
                        // { value: 'SageMaker Endpoint', label: 'SageMaker Endpoint' },
                        // { value: 'SageMaker HyperPod', label: 'SageMaker HyperPod' },
                        // { value: 'EKS', label: 'EKS' },
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
                        { value: 'g5.xlarge', label: 'g5.xlarge (1 A10G, 24GB RAM)' },
                        { value: 'g5.2xlarge', label: 'g5.2xlarge (1 A10G, 24GB RAM)' },
                        { value: 'g5.4xlarge', label: 'g5.4xlarge (1 A10G, 24GB RAM)' },
                        { value: 'g5.12xlarge', label: 'g5.12xlarge (4 A10G, 96GB RAM)' },
                        { value: 'g5.24xlarge', label: 'g5.48xlarge (4 A10G, 192GB RAM)' },
                        { value: 'g6e.xlarge', label: 'g6e.xlarge (1 L40S, 48GB RAM)' },
                        { value: 'p4d.24xlarge', label: 'p4d.24xlarge (8 A100, 320GB RAM)' },
                        { value: 'p4de.24xlarge', label: 'p4d.24xlarge (8 A100, 640GB RAM)' },
                        { value: 'p5.48xlarge', label: 'p5.48xlarge (8 A100, 640GB RAM)' },
                        { value: 'p5e.48xlarge', label: 'p5e.48xlarge (8 H100, 1128GB RAM)' },
                        { value: 'p5en.48xlarge', label: 'p5en.48xlarge (8 H100, 1128GB RAM)' },
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
        );
      }, [modelCategories, modelStatus, selectedModels, deploymentConfig, handleBatchDeploy])}
    </div>
  );
};

export default ModelHubPage;