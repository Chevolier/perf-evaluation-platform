import React, { useState, useEffect } from 'react';
import { Card, Button, Row, Col, Typography, Space, Steps, notification, Spin } from 'antd';
import { ArrowLeftOutlined, ArrowRightOutlined, CloudUploadOutlined } from '@ant-design/icons';
import ParamConfigurator from '../components/ParamConfigurator';

const { Title, Paragraph, Text } = Typography;

const ConfigurationPage = ({ params, onParamsChange, onNext, onPrev, selectedModels, dataset }) => {
  const [deploymentStatus, setDeploymentStatus] = useState({});
  const [checking, setChecking] = useState(false);
  
  const ec2Models = ['qwen2-vl-7b', 'qwen2.5-vl-7b', 'qwen2.5-vl-32b', 'qwen2.5-0.5b', 'gemma-3-4b', 'ui-tars-1.5-7b'];

  const checkModelStatus = async () => {
    const localModels = selectedModels.filter(model => ec2Models.includes(model));
    if (localModels.length === 0) return;
    
    setChecking(true);
    try {
      const response = await fetch('/api/check-model-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models: localModels }),
      });
      
      const data = await response.json();
      if (data.status === 'success') {
        setDeploymentStatus(data.model_status);
      }
    } catch (error) {
      console.error('Error checking model status:', error);
    } finally {
      setChecking(false);
    }
  };
  
  const deployUndeployedModels = async () => {
    const modelsNeedingDeployment = Object.entries(deploymentStatus)
      .filter(([model, info]) => info.type === 'emd' && info.status === 'not_deployed')
      .map(([model]) => model);
    
    if (modelsNeedingDeployment.length === 0) {
      notification.info({
        message: '所有模型已准备就绪',
        description: '无需额外部署',
        duration: 3,
      });
      return;
    }
    
    try {
      const response = await fetch('/api/deploy-selected-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models: modelsNeedingDeployment }),
      });
      
      const data = await response.json();
      if (data.status === 'success') {
        notification.success({
          message: '模型部署已开始',
          description: `开始部署 ${modelsNeedingDeployment.length} 个模型，部署将在后台进行。`,
          duration: 6,
        });
        
        // Refresh status after deployment starts
        setTimeout(() => checkModelStatus(), 2000);
      } else {
        throw new Error(data.error || '模型部署失败');
      }
    } catch (error) {
      notification.error({
        message: '模型部署失败',
        description: error.message,
        duration: 8,
      });
    }
  };
  
  useEffect(() => {
    checkModelStatus();
  }, [selectedModels]);
  
  const handleNext = async () => {
    // Check model status one more time before proceeding
    await checkModelStatus();
    onNext();
  };
  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Row gutter={[24, 24]} justify="center">
        <Col span={24}>
          <Card>
            <div style={{ textAlign: 'center', marginBottom: '32px' }}>
              <Title level={2}>步骤 3: 配置推理参数</Title>
              <Paragraph style={{ fontSize: '16px', color: '#666' }}>
                设置模型推理的参数，包括最大输出长度和温度等。
              </Paragraph>
            </div>
            
            <Steps
              current={2}
              style={{ marginBottom: '32px' }}
              items={[
                { title: '选择模型', description: `已选择 ${selectedModels.length} 个模型` },
                { title: '上传材料', description: `已上传 ${dataset.files?.length || 0} 个文件` },
                { title: '配置参数', description: '设置推理参数' },
                { title: '开始评测', description: '执行推理测试' }
              ]}
            />
            
            <Row gutter={24}>
              <Col span={12} offset={6}>
                <ParamConfigurator 
                  value={params} 
                  onChange={onParamsChange} 
                />
              </Col>
            </Row>
            
            {/* Model Deployment Status Display */}
            {Object.keys(deploymentStatus).length > 0 && (
              <>
                <div style={{ background: '#f6ffed', padding: '16px', borderRadius: '6px', border: '1px solid #b7eb8f', marginTop: '24px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <Text strong style={{ color: '#389e0d' }}>
                      <CloudUploadOutlined /> 模型部署状态:
                    </Text>
                    <Space>
                      <Button 
                        size="small" 
                        onClick={checkModelStatus}
                        loading={checking}
                        icon={checking ? <Spin size="small" /> : null}
                      >
                        刷新状态
                      </Button>
                      <Button 
                        size="small" 
                        type="primary"
                        onClick={deployUndeployedModels}
                        disabled={!Object.values(deploymentStatus).some(info => 
                          info.type === 'emd' && info.status === 'not_deployed'
                        )}
                      >
                        部署未部署模型
                      </Button>
                    </Space>
                  </div>
                  <div>
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
                >
                  下一步：开始评测
                </Button>
              </Space>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ConfigurationPage;