import React, { useState } from 'react';
import { Card, Button, Row, Col, Typography, Space, Divider, notification, Spin } from 'antd';
import { ArrowRightOutlined, CloudUploadOutlined } from '@ant-design/icons';
import ModelSelector from '../components/ModelSelector';

const { Title, Paragraph, Text } = Typography;

const ModelSelectionPage = ({ selectedModels, onModelChange, onNext }) => {
  const [deploymentStatus, setDeploymentStatus] = useState({});

  // EMD local models that need deployment
  const emdModels = ['qwen2-vl-7b', 'qwen2.5-vl-32b', 'qwen2.5-0.5b', 'gemma-3-4b', 'ui-tars-1.5-7b'];

  // Removed unused triggerEMDDeployment function

  const startDeploymentStatusStream = (models) => {
    const eventSource = new EventSource(`/api/emd/deployment-stream?models=${models.join(',')}`);
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'update') {
        setDeploymentStatus(data.deployments);
        
        // Check for completed deployments
        Object.entries(data.deployments).forEach(([modelName, status]) => {
          if (status.status === 'deployed') {
            notification.success({
              message: '模型部署完成',
              description: `${modelName} 已成功部署，现在可以使用了`,
              duration: 4,
            });
          } else if (status.status === 'failed') {
            notification.error({
              message: '模型部署失败',
              description: `${modelName} 部署失败: ${status.message}`,
              duration: 8,
            });
          }
        });
      } else if (data.type === 'complete' || data.type === 'stream_ended') {
        eventSource.close();
      }
    };
    
    eventSource.onerror = () => {
      eventSource.close();
    };
  };

  const checkModelStatus = async (models) => {
    try {
      const response = await fetch('/api/check-model-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models }),
      });
      
      const data = await response.json();
      if (data.status === 'success') {
        // Update deployment status based on model status
        const statusUpdate = {};
        Object.entries(data.model_status).forEach(([model, info]) => {
          if (info.type === 'emd') {
            if (info.status === 'deployed') {
              statusUpdate[model] = {
                status: 'already_deployed',
                tag: info.tag,
                message: info.message
              };
            } else if (info.status === 'not_deployed') {
              statusUpdate[model] = {
                status: 'needs_deployment',
                message: info.message
              };
            }
          }
        });
        setDeploymentStatus(statusUpdate);
      }
    } catch (error) {
      console.error('Error checking model status:', error);
    }
  };

  const handleModelChange = (newModels) => {
    onModelChange(newModels);
    
    // Check status for all selected models
    if (newModels.length > 0) {
      checkModelStatus(newModels);
    }
  };

  const handleNext = async () => {
    if (selectedModels.length === 0) {
      alert('请至少选择一个模型');
      return;
    }
    
    // Check deployment status before proceeding
    await checkModelStatus(selectedModels);
    
    // Proceed to next step
    onNext();
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Row gutter={[24, 24]} justify="center">
        <Col span={24}>
          <Card>
            <div style={{ textAlign: 'center', marginBottom: '32px' }}>
              <Title level={2}>步骤 1: 选择评测模型</Title>
              <Paragraph style={{ fontSize: '16px', color: '#666' }}>
                选择您要评测的大语言模型。您可以选择多个模型进行对比评测。
              </Paragraph>
            </div>
            
            <Row gutter={24}>
              <Col span={12} offset={6}>
                <ModelSelector 
                  value={selectedModels} 
                  onChange={handleModelChange} 
                />
              </Col>
            </Row>
            
            {/* Deployment Status Display */}
            {Object.keys(deploymentStatus).length > 0 && (
              <>
                <Divider />
                <div style={{ background: '#f6ffed', padding: '16px', borderRadius: '6px', border: '1px solid #b7eb8f' }}>
                  <Text strong style={{ color: '#389e0d' }}>
                    <CloudUploadOutlined /> 本地模型部署状态:
                  </Text>
                  <div style={{ marginTop: '8px' }}>
                    {Object.entries(deploymentStatus).map(([modelName, status]) => {
                      let statusDisplay = '';
                      let color = '#666';
                      
                      switch (status.status) {
                        case 'checking_bootstrap':
                          statusDisplay = '🔍 检查环境...';
                          color = '#1890ff';
                          break;
                        case 'bootstrapping':
                          statusDisplay = '⚡ 初始化环境...';
                          color = '#722ed1';
                          break;
                        case 'deploying':
                          statusDisplay = '🚀 部署中...';
                          color = '#1890ff';
                          break;
                        case 'deployed':
                          statusDisplay = '✅ 已部署';
                          color = '#52c41a';
                          break;
                        case 'already_deployed':
                          statusDisplay = '✅ 已就绪';
                          color = '#52c41a';
                          break;
                        case 'failed':
                          statusDisplay = '❌ 部署失败';
                          color = '#ff4d4f';
                          break;
                        default:
                          statusDisplay = `⏳ ${status.message || status.status}`;
                          color = '#faad14';
                      }
                      
                      return (
                        <div key={modelName} style={{ marginBottom: '4px' }}>
                          <Text>
                            <strong>{modelName}</strong>: <span style={{ color }}>{statusDisplay}</span>
                            {status.tag && <Text type="secondary" style={{ fontSize: '12px', marginLeft: '8px' }}>({status.tag})</Text>}
                          </Text>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            )}
            
            <Divider />
            
            <div style={{ textAlign: 'center', marginTop: '32px' }}>
              <Space direction="vertical" size="small">
                <Space>
                  <span style={{ marginRight: '16px' }}>
                    已选择 {selectedModels.length} 个模型
                  </span>
                  {/* Show deployment status indicator */}
                  {Object.values(deploymentStatus).some(status => 
                    ['checking_bootstrap', 'bootstrapping', 'deploying'].includes(status.status)
                  ) && (
                    <span style={{ color: '#1890ff', fontSize: '12px' }}>
                      <Spin size="small" style={{ marginRight: '4px' }} />
                      本地模型部署中...
                    </span>
                  )}
                </Space>
                <Button 
                  type="primary" 
                  size="large" 
                  onClick={handleNext}
                  icon={<ArrowRightOutlined />}
                  disabled={selectedModels.length === 0}
                >
                  下一步：上传材料
                </Button>
              </Space>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ModelSelectionPage;