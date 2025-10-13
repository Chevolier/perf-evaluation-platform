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
  Skeleton
} from 'antd';
import {
  RobotOutlined,
  CloudOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  ReloadOutlined,
  HistoryOutlined
} from '@ant-design/icons';
import HyperPodPanel from '../components/HyperPodPanel';
import LaunchPanel from '../components/LaunchPanel';
import LaunchHistoryDrawer from '../components/LaunchHistoryDrawer';

const { Title, Text, Paragraph } = Typography;

const ModelHubPage = () => {
  const [initialLoading, setInitialLoading] = useState(true);
  const [launchHistoryVisible, setLaunchHistoryVisible] = useState(false);
  
  
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
  
  // Memoized category templates to avoid recreating icons
  const categoryTemplates = useMemo(() => ({
    bedrock: {
      title: 'Bedrock 模型',
      icon: <CloudOutlined />,
      color: '#1890ff',
      alwaysAvailable: true
    },
    emd: {
      title: '部署模型',
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

  const [modelCategories, setModelCategories] = useState({});

  const buildCategories = useCallback((modelsData = {}) => {
    const categories = {};
    const deployableKeys = [];

    Object.entries(modelsData).forEach(([categoryKey, categoryModels]) => {
      const preset = categoryTemplates[categoryKey] || {
        title: categoryKey,
        icon: <RobotOutlined />,
        color: '#722ed1',
        alwaysAvailable: true
      };

      const models = Object.entries(categoryModels || {}).map(([key, info]) => {
        const alwaysAvailable = Object.prototype.hasOwnProperty.call(info, 'always_available')
          ? Boolean(info.always_available)
          : (preset.alwaysAvailable ?? true);

        if (!alwaysAvailable) {
          deployableKeys.push(key);
        }

        return {
          key,
          name: info.name || key,
          description: info.description || '',
          alwaysAvailable,
          deployment_method: info.deployment_method,
          status: info.deployment_status || {},
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

    return { categories, deployableKeys };
  }, [categoryTemplates]);
  


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
          modelHub_selectedModels: JSON.stringify(selectedModels)
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
  }, [selectedModels]);

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
          const { categories, deployableKeys } = buildCategories(data.models);
          deployableModelKeys = deployableKeys;

          React.startTransition(() => {
            setModelCategories(categories);
            setModelStatus({});
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

      <HyperPodPanel />

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
          <div>
            <LaunchPanel
              selectedModels={selectedModels}
              onLaunchStart={(jobId) => {
                message.success(`Launch started! Job ID: ${jobId}`);
                // Refresh model status to show launch status
                fetchModelData();
              }}
            />
            
            <div style={{ marginTop: 16, textAlign: 'center' }}>
              <Space>
                <Button 
                  onClick={() => setSelectedModels([])}
                  disabled={selectedModels.length === 0}
                >
                  清空选择
                </Button>
                <Button 
                  icon={<HistoryOutlined />}
                  onClick={() => setLaunchHistoryVisible(true)}
                >
                  查看启动历史
                </Button>
              </Space>
            </div>
          </div>
        );
      }, [modelCategories, modelStatus, selectedModels])}
      
      {/* Launch History Drawer */}
      <LaunchHistoryDrawer
        visible={launchHistoryVisible}
        onClose={() => setLaunchHistoryVisible(false)}
      />
    </div>
  );
};

export default ModelHubPage;
