import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Select,
  Input,
  InputNumber,
  Button,
  Space,
  Typography,
  Alert,
  message,
  Divider,
  Tag,
  Tooltip
} from 'antd';
import {
  RocketOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';

const { Text } = Typography;
const { Option } = Select;

const LaunchPanel = ({ selectedModels, onLaunchStart }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [launchMethods, setLaunchMethods] = useState({});
  const [selectedMethod, setSelectedMethod] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);
  const [modelInfo, setModelInfo] = useState(null);
  const [availableEngines, setAvailableEngines] = useState([]);

  // Fetch launch methods on component mount
  useEffect(() => {
    fetchLaunchMethods();
  }, []);

  // Update available engines when method or model changes
  useEffect(() => {
    updateAvailableEngines();
  }, [selectedMethod, selectedModel, launchMethods]);

  const fetchLaunchMethods = async () => {
    try {
      const response = await fetch('/api/launch-methods');
      const data = await response.json();
      
      if (data.success) {
        setLaunchMethods(data.methods);
      } else {
        message.error('Failed to load launch methods');
      }
    } catch (error) {
      console.error('Error fetching launch methods:', error);
      message.error('Failed to load launch methods');
    }
  };

  const updateAvailableEngines = () => {
    if (!selectedMethod || !selectedModel || !launchMethods[selectedMethod]) {
      setAvailableEngines([]);
      return;
    }

    const method = launchMethods[selectedMethod];
    const modelEngines = modelInfo?.supported_engines || [];
    const methodEngines = method.supported_engines || [];
    
    // Find intersection of model and method supported engines
    const engines = modelEngines.filter(engine => methodEngines.includes(engine));
    setAvailableEngines(engines);

    // Reset engine selection if current selection is not available
    const currentEngine = form.getFieldValue('engine');
    if (currentEngine && !engines.includes(currentEngine)) {
      form.setFieldsValue({ engine: engines[0] || null });
    }
  };

  const handleModelChange = async (modelKey) => {
    setSelectedModel(modelKey);
    
    if (modelKey) {
      try {
        const response = await fetch(`/api/models/${modelKey}/launch-info`);
        const data = await response.json();
        
        if (data.success) {
          setModelInfo(data);
          
          // Reset method selection if current method is not supported
          const currentMethod = form.getFieldValue('method');
          const supportedMethods = data.supported_methods || [];
          
          if (currentMethod && !supportedMethods.includes(currentMethod)) {
            form.setFieldsValue({ method: supportedMethods[0] || null });
            setSelectedMethod(supportedMethods[0] || null);
          }
        } else {
          message.error('Failed to load model information');
        }
      } catch (error) {
        console.error('Error fetching model info:', error);
        message.error('Failed to load model information');
      }
    } else {
      setModelInfo(null);
    }
  };

  const handleMethodChange = (method) => {
    setSelectedMethod(method);
    
    // Reset form values for method-specific fields
    const methodSchema = launchMethods[method];
    if (methodSchema) {
      const defaultValues = {};
      Object.entries(methodSchema.parameters || {}).forEach(([key, param]) => {
        if (param.default !== undefined) {
          defaultValues[key] = param.default;
        }
      });
      form.setFieldsValue(defaultValues);
    }
  };

  const renderFormField = (fieldName, fieldConfig) => {
    const { type, label, required, placeholder, options, min, max } = fieldConfig;
    
    const rules = [];
    if (required) {
      rules.push({ required: true, message: `${label} is required` });
    }

    switch (type) {
      case 'select':
        return (
          <Form.Item
            key={fieldName}
            name={fieldName}
            label={label}
            rules={rules}
          >
            <Select placeholder={placeholder}>
              {options?.map(option => (
                <Option key={option} value={option}>
                  {option}
                </Option>
              ))}
            </Select>
          </Form.Item>
        );
      
      case 'number':
        return (
          <Form.Item
            key={fieldName}
            name={fieldName}
            label={label}
            rules={rules}
          >
            <InputNumber
              placeholder={placeholder}
              min={min}
              max={max}
              style={{ width: '100%' }}
            />
          </Form.Item>
        );
      
      case 'text':
      default:
        return (
          <Form.Item
            key={fieldName}
            name={fieldName}
            label={label}
            rules={rules}
          >
            <Input placeholder={placeholder} />
          </Form.Item>
        );
    }
  };

  const handleLaunch = async (values) => {
    if (!selectedModel) {
      message.error('Please select a model');
      return;
    }

    setLoading(true);
    
    try {
      const launchData = {
        method: values.method,
        model_key: selectedModel,
        engine: values.engine,
        params: { ...values },
        user_id: 'current_user' // TODO: Get from auth context
      };

      // Remove method and engine from params (they're top-level fields)
      delete launchData.params.method;
      delete launchData.params.engine;

      const response = await fetch('/api/launches', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(launchData),
      });

      const result = await response.json();

      if (result.success) {
        message.success(`Launch started successfully! Job ID: ${result.job_id}`);
        onLaunchStart?.(result.job_id);
        
        // Reset form
        form.resetFields();
        setSelectedModel(null);
        setSelectedMethod(null);
        setModelInfo(null);
      } else {
        message.error(result.error || 'Launch failed');
      }
    } catch (error) {
      console.error('Error starting launch:', error);
      message.error('Failed to start launch');
    } finally {
      setLoading(false);
    }
  };

  const getMethodDescription = (method) => {
    const descriptions = {
      'SAGEMAKER_ENDPOINT': 'Deploy via AWS SageMaker Elastic Model Deployment (EMD)',
      'HYPERPOD': 'Deploy via AWS SageMaker HyperPod cluster',
      'EKS': 'Deploy to existing Amazon EKS cluster',
      'EC2': 'Launch on EC2 instance with IAM role-based access'
    };
    return descriptions[method] || 'Deploy using this method';
  };

  return (
    <Card
      title={
        <Space>
          <RocketOutlined />
          <span>Launch Model</span>
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleLaunch}
        initialValues={{
          method: null,
          engine: null
        }}
      >
        {/* Model Selection */}
        <Form.Item
          name="model"
          label="Model"
          rules={[{ required: true, message: 'Please select a model' }]}
        >
          <Select
            placeholder="Select a model to launch"
            onChange={handleModelChange}
            showSearch
            filterOption={(input, option) =>
              option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
            }
          >
            {selectedModels.map(modelKey => (
              <Option key={modelKey} value={modelKey}>
                {modelKey}
              </Option>
            ))}
          </Select>
        </Form.Item>

        {/* Model Information */}
        {modelInfo && (
          <Alert
            message="Model Information"
            description={
              <Space direction="vertical" size="small">
                <div>
                  <Text strong>Supported Methods: </Text>
                  {modelInfo.supported_methods?.map(method => (
                    <Tag key={method} color="blue">{method}</Tag>
                  ))}
                </div>
                <div>
                  <Text strong>Supported Engines: </Text>
                  {modelInfo.supported_engines?.map(engine => (
                    <Tag key={engine} color="green">{engine}</Tag>
                  ))}
                </div>
                {modelInfo.constraints && (
                  <div>
                    <Text strong>Constraints: </Text>
                    <Text>Min GPUs: {modelInfo.constraints.min_gpus || 'N/A'}</Text>
                  </div>
                )}
              </Space>
            }
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        {/* Launch Method Selection */}
        <Form.Item
          name="method"
          label="Launch Method"
          rules={[{ required: true, message: 'Please select a launch method' }]}
        >
          <Select
            placeholder="Select launch method"
            onChange={handleMethodChange}
            disabled={!selectedModel}
          >
            {Object.entries(launchMethods).map(([methodKey, methodConfig]) => {
              const isSupported = modelInfo?.supported_methods?.includes(methodKey);
              return (
                <Option
                  key={methodKey}
                  value={methodKey}
                  disabled={!isSupported}
                >
                  <Space>
                    <span>{methodConfig.name}</span>
                    {!isSupported && (
                      <Tooltip title="This method is not supported by the selected model">
                        <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />
                      </Tooltip>
                    )}
                  </Space>
                </Option>
              );
            })}
          </Select>
        </Form.Item>

        {/* Method Description */}
        {selectedMethod && (
          <Alert
            message={launchMethods[selectedMethod]?.name}
            description={getMethodDescription(selectedMethod)}
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        {/* Engine Selection */}
        <Form.Item
          name="engine"
          label="Inference Engine"
          rules={[{ required: true, message: 'Please select an engine' }]}
        >
          <Select
            placeholder="Select inference engine"
            disabled={!selectedMethod || availableEngines.length === 0}
          >
            {availableEngines.map(engine => (
              <Option key={engine} value={engine}>
                {engine.toUpperCase()}
              </Option>
            ))}
          </Select>
        </Form.Item>

        {/* Method-specific Parameters */}
        {selectedMethod && launchMethods[selectedMethod] && (
          <>
            <Divider orientation="left">Configuration</Divider>
            {Object.entries(launchMethods[selectedMethod].parameters || {}).map(([fieldName, fieldConfig]) =>
              renderFormField(fieldName, fieldConfig)
            )}
          </>
        )}

        {/* Launch Button */}
        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            loading={loading}
            disabled={!selectedModel || !selectedMethod || availableEngines.length === 0}
            icon={<RocketOutlined />}
            size="large"
            block
          >
            {loading ? 'Launching...' : 'Launch Model'}
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default LaunchPanel;
