import React, { useState } from 'react';
import { Card, Button, Row, Col, Typography, Space, Steps, notification, Spin } from 'antd';
import { ArrowLeftOutlined, ArrowRightOutlined, CloudUploadOutlined } from '@ant-design/icons';
import DatasetUploader from '../components/DatasetUploader';

const { Title, Paragraph, Text } = Typography;

const MaterialUploadPage = ({ dataset, onDatasetChange, onNext, onPrev, selectedModels }) => {
  const [deploying, setDeploying] = useState(false);
  const [deploymentStatus, setDeploymentStatus] = useState({});
  
  const emdModels = ['qwen2-vl-7b', 'qwen2.5-vl-32b', 'qwen2.5-0.5b', 'gemma-3-4b', 'ui-tars-1.5-7b'];
  
  const checkAndDeployModels = async () => {
    const localModels = selectedModels.filter(model => emdModels.includes(model));
    
    if (localModels.length === 0) {
      return true; // No EMD models to deploy
    }
    
    setDeploying(true);
    
    try {
      // First check current model status
      const statusResponse = await fetch('/api/check-model-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models: localModels }),
      });
      
      const statusData = await statusResponse.json();
      if (statusData.status !== 'success') {
        throw new Error(statusData.error || '检查模型状态失败');
      }
      
      // Check which models need deployment
      const modelsNeedingDeployment = [];
      const modelStatusInfo = {};
      
      Object.entries(statusData.model_status).forEach(([model, info]) => {
        modelStatusInfo[model] = info;
        if (info.type === 'emd' && info.status === 'not_deployed') {
          modelsNeedingDeployment.push(model);
        }
      });
      
      setDeploymentStatus(modelStatusInfo);
      
      if (modelsNeedingDeployment.length === 0) {
        notification.success({
          message: '模型状态检查完成',
          description: '所有所需模型都已部署，可以继续下一步',
          duration: 3,
        });
        return true;
      }
      
      // Deploy models that need deployment
      const deployResponse = await fetch('/api/deploy-selected-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models: modelsNeedingDeployment }),
      });
      
      const deployData = await deployResponse.json();
      if (deployData.status !== 'success') {
        throw new Error(deployData.error || '模型部署失败');
      }
      
      notification.success({
        message: '模型部署已开始',
        description: `开始部署 ${modelsNeedingDeployment.length} 个模型，您可以继续配置参数，部署将在后台进行。`,
        duration: 6,
      });
      
      return true;
      
    } catch (error) {
      notification.warning({
        message: '模型部署检查失败',
        description: `${error.message}。您可以继续配置参数，稍后可在推理页面重新检查模型状态。`,
        duration: 8,
      });
      return true; // Still allow progression
    } finally {
      setDeploying(false);
    }
  };
  
  const handleNext = async () => {
    if (!dataset.files || dataset.files.length === 0) {
      alert('请上传图片或视频文件');
      return;
    }
    if (!dataset.prompt) {
      alert('请输入提示词');
      return;
    }
    
    // Check and deploy models if needed, but proceed to next step regardless
    await checkAndDeployModels();
    onNext();
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Row gutter={[24, 24]} justify="center">
        <Col span={24}>
          <Card>
            <div style={{ textAlign: 'center', marginBottom: '32px' }}>
              <Title level={2}>步骤 2: 上传评测材料</Title>
              <Paragraph style={{ fontSize: '16px', color: '#666' }}>
                上传图片或视频文件，并输入您希望模型处理的提示词。
              </Paragraph>
            </div>
            
            <Steps
              current={1}
              style={{ marginBottom: '32px' }}
              items={[
                { title: '选择模型', description: `已选择 ${selectedModels.length} 个模型` },
                { title: '上传材料', description: '上传文件和提示词' },
                { title: '配置参数', description: '设置推理参数' },
                { title: '开始评测', description: '执行推理测试' }
              ]}
            />
            
            <Row gutter={24}>
              <Col span={16} offset={4}>
                <DatasetUploader 
                  onChange={onDatasetChange}
                  value={dataset}
                />
              </Col>
            </Row>
            
            {/* Deployment Status Display */}
            {Object.keys(deploymentStatus).length > 0 && (
              <>
                <div style={{ background: '#f6ffed', padding: '16px', borderRadius: '6px', border: '1px solid #b7eb8f', marginBottom: '24px' }}>
                  <Text strong style={{ color: '#389e0d' }}>
                    <CloudUploadOutlined /> 模型部署状态:
                  </Text>
                  <div style={{ marginTop: '8px' }}>
                    {Object.entries(deploymentStatus).map(([modelName, info]) => {
                      let statusDisplay = '';
                      let color = '#666';
                      
                      if (info.type === 'bedrock') {
                        statusDisplay = '✅ 已准备好';
                        color = '#52c41a';
                      } else if (info.type === 'emd') {
                        if (info.status === 'deployed') {
                          statusDisplay = '✅ 已部署';
                          color = '#52c41a';
                        } else if (info.status === 'not_deployed') {
                          statusDisplay = '⏳ 需要部署';
                          color = '#faad14';
                        }
                      }
                      
                      return (
                        <div key={modelName} style={{ marginBottom: '4px' }}>
                          <Text>
                            <strong>{modelName}</strong>: <span style={{ color }}>{statusDisplay}</span>
                            {info.tag && <Text type="secondary" style={{ fontSize: '12px', marginLeft: '8px' }}>({info.tag})</Text>}
                          </Text>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            )}
            
            <div style={{ textAlign: 'center', marginTop: '32px' }}>
              <Space size="large">
                <Button 
                  size="large" 
                  onClick={onPrev}
                  icon={<ArrowLeftOutlined />}
                >
                  上一步
                </Button>
                <Button 
                  type="primary" 
                  size="large" 
                  onClick={handleNext}
                  icon={<ArrowRightOutlined />}
                  loading={deploying}
                  disabled={!dataset.files?.length || !dataset.prompt || deploying}
                >
                  {deploying ? (
                    <><Spin size="small" style={{ marginRight: '8px' }} />检查并部署模型...</>
                  ) : (
                    "下一步：配置参数"
                  )}
                </Button>
              </Space>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default MaterialUploadPage;