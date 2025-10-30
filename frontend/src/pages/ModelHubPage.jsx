import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Card,
  Typography,
  Tag,
  Row,
  Col,
  Space,
  Divider,
  message,
  Button,
  Select,
  Form,
  Input,
  InputNumber,
  Skeleton
} from 'antd';
import {
  RobotOutlined,
  CloudOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  RocketOutlined,
  ReloadOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const ModelHubPage = () => {
  const [initialLoading, setInitialLoading] = useState(true);
  const [deploymentLoading, setDeploymentLoading] = useState(false);
  
  
  // Always start with empty model status to force fresh fetch
  const [modelStatus, setModelStatus] = useState(() => {
    // Clear any cached status to ensure fresh data on every load
    localStorage.removeItem('modelHub_modelStatus');
    localStorage.removeItem('modelHub_cacheTimestamp');
    return {};
  });
  
  const [selectedModel, setSelectedModel] = useState(() => {
    try {
      const saved = localStorage.getItem('modelHub_selectedModel');
      return saved ? JSON.parse(saved) : null;
    } catch (error) {
      console.error('Failed to load selected model from localStorage:', error);
      return null;
    }
  });

  const [customModelName, setCustomModelName] = useState(() => {
    try {
      const saved = localStorage.getItem('modelHub_customModelName');
      return saved ? JSON.parse(saved) : '';
    } catch (error) {
      console.error('Failed to load custom model name from localStorage:', error);
      return '';
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
      dpSize: 1,
      gpuMemoryUtilization: 0.9,
      maxModelLen: 2048
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
    ec2: {
      title: 'EC2 部署模型',
      icon: <ThunderboltOutlined />,
      color: '#52c41a',
      models: []
    }
  }), []);

  const [modelCategories, setModelCategories] = useState(categoryTemplates);
  

  // 部署单个模型 (memoized for performance)
  const handleModelDeploy = useCallback(async () => {
    const modelTodeploy = customModelName.trim() || selectedModel;

    if (!modelTodeploy) {
      message.warning('请选择要部署的模型或输入自定义模型名称');
      return;
    }

    // Set deployment loading state
    setDeploymentLoading(true);

    // Immediately update status to show deployment in progress
    const immediateStatus = {
      [modelTodeploy]: {
        status: 'inprogress',
        message: '开始部署...',
        tag: null
      }
    };

    // Update UI immediately to show deployment started
    React.startTransition(() => {
      setModelStatus(prev => ({
        ...prev,
        ...immediateStatus
      }));
    });

    try {
      const response = await fetch('/api/deploy-models', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          models: [modelTodeploy],
          instance_type: deploymentConfig.machineType,
          engine_type: deploymentConfig.framework,
          service_type: deploymentConfig.serviceType,
          tp_size: deploymentConfig.tpSize,
          dp_size: deploymentConfig.dpSize,
          gpu_memory_utilization: deploymentConfig.gpuMemoryUtilization,
          max_model_len: deploymentConfig.maxModelLen
        })
      });
      
      if (response.ok) {
        const responseData = await response.json();
        console.log('Deployment response:', responseData);
        
        if (responseData.status === 'success') {
          // Check model deployment result
          const results = responseData.results || {};
          const modelResult = results[modelTodeploy];

          if (modelResult && modelResult.success) {
            const newStatus = {
              [modelTodeploy]: {
                status: 'inprogress',
                message: '部署中',
                tag: modelResult.tag
              }
            };

            // Batch state updates to reduce re-renders
            React.startTransition(() => {
              setModelStatus(prev => ({
                ...prev,
                ...newStatus
              }));

              // 清空选择
              setSelectedModel(null);
              setCustomModelName('');
            });

            message.success(`模型 ${modelTodeploy} 已开始部署`);
          } else {
            const failureStatus = {
              [modelTodeploy]: {
                status: 'failed',
                message: modelResult?.error || '部署失败'
              }
            };

            React.startTransition(() => {
              setModelStatus(prev => ({
                ...prev,
                ...failureStatus
              }));
            });

            message.error(`模型 ${modelTodeploy} 部署失败: ${modelResult?.error || '未知错误'}`);
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
    } finally {
      // Always clear deployment loading state
      setDeploymentLoading(false);
    }
  }, [selectedModel, customModelName, deploymentConfig]);


  // 处理自定义模型名称输入
  const handleCustomModelNameChange = useCallback((e) => {
    const value = e.target.value;
    setCustomModelName(value);
    // Clear selected model when typing custom name to ensure mutual exclusivity
    if (value.trim()) {
      setSelectedModel(null);
    }
  }, []);

  // Handle clearing stale deployment statuses
  const handleClearStaleStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/clear-stale-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          message.success(`已清理 ${data.cleared_count} 个过期的部署状态`);

          // Refresh model status after clearing
          if (data.cleared_count > 0) {
            // Force refresh by reloading the page
            setTimeout(() => {
              window.location.reload();
            }, 1000);
          }
        } else {
          message.error(`清理失败: ${data.error}`);
        }
      } else {
        message.error('清理请求失败');
      }
    } catch (error) {
      console.error('清理过期状态失败:', error);
      message.error('清理过期状态失败');
    }
  }, []);

  // Save only non-status data to localStorage (keep selected models and config)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      try {
        // Only save selected model, custom model name and deployment config, not status (always fetch fresh)
        const batch = {
          modelHub_selectedModel: JSON.stringify(selectedModel),
          modelHub_customModelName: JSON.stringify(customModelName),
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
  }, [selectedModel, customModelName, deploymentConfig]);

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

      let deployableModelKeys = [];
      
      // Process model list response
      if (modelListResponse.ok) {
        const data = await modelListResponse.json();
        
        if (data.status === 'success' && data.models) {
          
          // Process models with memoized transformation
          const bedrockModels = data.models.bedrock ? 
            Object.entries(data.models.bedrock).map(([key, info]) => ({
              key,
              name: info.name,
              description: info.description,
              alwaysAvailable: true
            })) : [];
            
          const ec2Models = data.models.ec2 ?
            Object.entries(data.models.ec2).map(([key, info]) => ({
              key,
              name: info.name,
              description: info.description,
              alwaysAvailable: false
            })) : [];
            
          // Extract deployable model keys for status check
          deployableModelKeys = ec2Models.map(m => m.key);
          console.log('🔍 DEBUG: deployableModelKeys extracted:', deployableModelKeys);
            
          // Batch UI updates to reduce re-renders
          React.startTransition(() => {
            setModelCategories({
              bedrock: {
                ...categoryTemplates.bedrock,
                models: bedrockModels
              },
              ec2: {
                ...categoryTemplates.ec2,
                models: ec2Models
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

  // Status tag for Bedrock models (always available)
  const getStatusTag = useCallback((model) => {
    if (model.alwaysAvailable) {
      return <Tag color="success" icon={<CheckCircleOutlined />}>可用</Tag>;
    }
    return <Tag color="default">未知</Tag>;
  }, []);

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
      </div>
    </Card>
  ), []);

  // Render model card (for Bedrock models only)
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
      </div>
    </Card>
  ), [getStatusTag]);


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

      {/* Bedrock 模型卡片 */}
      <div style={{ marginBottom: 32 }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          marginBottom: 16
        }}>
          <Space>
            <CloudOutlined />
            <Title level={3} style={{ margin: 0, color: '#1890ff' }}>
              Bedrock 模型
            </Title>
          </Space>
        </div>

        <Row gutter={[16, 16]}>
          {initialLoading ? (
            // Show skeleton cards during initial loading
            Array.from({ length: 4 }, (_, index) => (
              <Col key={`skeleton-bedrock-${index}`} xs={24} sm={12} lg={8} xl={6}>
                {SkeletonCard}
              </Col>
            ))
          ) : (
            // Show actual Bedrock model cards once data is loaded
            modelCategories.bedrock?.models?.map(model => (
              <Col key={model.key} xs={24} sm={12} lg={8} xl={6}>
                {renderModelCard(model)}
              </Col>
            ))
          )}
        </Row>
        <Divider />
      </div>

      {/* EC2 部署模型标题 */}
      <div style={{ marginBottom: 32 }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          marginBottom: 16
        }}>
          <Space>
            <ThunderboltOutlined />
            <Title level={3} style={{ margin: 0, color: '#52c41a' }}>
              EC2 部署模型
            </Title>
          </Space>
        </div>
        <Text type="secondary">
          EC2 模型可以在下方部署配置中选择并部署
        </Text>
      </div>

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
                <Col span={12}>
                  <Form.Item label="EC2 预设模型选择">
                    <Select
                      placeholder="选择 EC2 预设模型"
                      value={selectedModel}
                      onChange={(value) => {
                        setSelectedModel(value);
                        setCustomModelName('');
                      }}
                      disabled={!!customModelName.trim()}
                      allowClear
                      onClear={() => setSelectedModel(null)}
                      style={{ width: '100%' }}
                      options={
                        // Only EC2 models in dropdown
                        Object.values(modelCategories).find(cat => cat.title === 'EC2 部署模型')?.models.map(model => ({
                          label: `${model.name} (${model.key})`,
                          value: model.key,
                        })) || []
                      }
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="自定义模型名称 (Hugging Face Hub)">
                    <Input
                      placeholder="输入 Hugging Face 模型名称，例如: Qwen/Qwen3-8B"
                      value={customModelName}
                      onChange={handleCustomModelNameChange}
                      disabled={!!selectedModel}
                      style={{ width: '100%' }}
                    />
                    <div style={{ marginTop: 4, fontSize: '12px', color: '#666' }}>
                      {selectedModel ?
                        `已选择预设模型: ${selectedModel}` :
                        (customModelName.trim() ?
                          `将部署自定义模型: ${customModelName.trim()}` :
                          '请选择预设模型或输入自定义模型名称'
                        )
                      }
                    </div>
                  </Form.Item>
                </Col>
              </Row>
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
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="GPU内存利用率">
                    <InputNumber
                      min={0.1}
                      max={1.0}
                      step={0.1}
                      value={deploymentConfig.gpuMemoryUtilization}
                      onChange={(value) => setDeploymentConfig(prev => ({ ...prev, gpuMemoryUtilization: value }))}
                      formatter={value => `${(value * 100).toFixed(0)}%`}
                      parser={value => value.replace('%', '') / 100}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="最大模型长度">
                    <InputNumber
                      min={512}
                      max={32768}
                      step={512}
                      value={deploymentConfig.maxModelLen}
                      onChange={(value) => setDeploymentConfig(prev => ({ ...prev, maxModelLen: value }))}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Row>
                <Col span={24}>
                  <Space>
                    <Button
                      type="primary"
                      onClick={handleModelDeploy}
                      disabled={!selectedModel && !customModelName.trim()}
                      loading={deploymentLoading}
                      size="large"
                    >
                      部署模型 {(customModelName.trim() || selectedModel) && `(${customModelName.trim() || selectedModel})`}
                    </Button>
                    <Button
                      onClick={() => {
                        setSelectedModel(null);
                        setCustomModelName('');
                      }}
                      disabled={!selectedModel && !customModelName.trim()}
                    >
                      清空选择
                    </Button>
                    <Button
                      onClick={handleClearStaleStatus}
                      type="default"
                      icon={<ReloadOutlined />}
                    >
                      清理过期状态
                    </Button>
                  </Space>
                </Col>
              </Row>
            </Form>
          </Card>
        );
      }, [modelCategories, modelStatus, selectedModel, customModelName, deploymentConfig, handleModelDeploy])}
    </div>
  );
};

export default ModelHubPage;