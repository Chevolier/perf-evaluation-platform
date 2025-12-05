import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Row, 
  Col, 
  Card, 
  Typography, 
  Button, 
  Space, 
  Input, 
  Radio, 
  Upload, 
  Slider, 
  InputNumber,
  Divider,
  message,
  Empty,
  Alert,
  Tag,
  Modal,
  Select,
  Image
} from 'antd';
import { 
  UploadOutlined, 
  PlayCircleOutlined, 
  ClearOutlined,
  FileImageOutlined,
  VideoCameraOutlined,
  RobotOutlined,
  SettingOutlined,
  LinkOutlined,
  RocketOutlined,
  CloseOutlined,
  EyeOutlined,
  DeleteOutlined
} from '@ant-design/icons';
import PlaygroundResultsDisplay from '../components/PlaygroundResultsDisplay';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const PlaygroundPage = ({
  selectedModels,
  dataset,
  onDatasetChange,
  params,
  onParamsChange,
  onModelChange
}) => {
  // State for available models (fetched from backend)
  const [availableModels, setAvailableModels] = useState([]);
  const [modelStatus, setModelStatus] = useState({});
  const [modelsLoading, setModelsLoading] = useState(false);

  // Load inference results from localStorage and clean up incomplete results
  const [inferenceResults, setInferenceResults] = useState(() => {
    try {
      const saved = localStorage.getItem('playground_inferenceResults');
      if (saved) {
        const parsedResults = JSON.parse(saved);
        // Clean up incomplete results (those without proper status)
        const cleanResults = {};
        Object.entries(parsedResults).forEach(([modelName, result]) => {
          // Only keep results with complete status
          if (result && ['success', 'error', 'not_deployed'].includes(result.status)) {
            cleanResults[modelName] = result;
          }
        });
        return cleanResults;
      }
      return {};
    } catch (error) {
      console.error('Failed to load inference results from localStorage:', error);
      return {};
    }
  });
  
  const [isInferring, setIsInferring] = useState(false);

  // Fetch available models on component mount
  useEffect(() => {
    const fetchModels = async () => {
      setModelsLoading(true);
      try {
        // Fetch model list
        const response = await fetch('/api/model-list');
        if (response.ok) {
          const data = await response.json();
          if (data.status === 'success' && data.models) {
            const models = [];

            // Add Bedrock models
            if (data.models.bedrock) {
              Object.entries(data.models.bedrock).forEach(([key, info]) => {
                models.push({
                  key,
                  name: info.name,
                  description: info.description,
                  category: 'bedrock',
                  alwaysAvailable: true
                });
              });
            }

            // Add EC2 models
            if (data.models.ec2) {
              Object.entries(data.models.ec2).forEach(([key, info]) => {
                models.push({
                  key,
                  name: info.name,
                  description: info.description,
                  category: 'ec2',
                  alwaysAvailable: false
                });
              });
            }

            setAvailableModels(models);

            // Fetch model status
            const allModelKeys = models.map(m => m.key);
            if (allModelKeys.length > 0) {
              const statusResponse = await fetch('/api/check-model-status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ models: allModelKeys })
              });

              if (statusResponse.ok) {
                const statusData = await statusResponse.json();
                if (statusData.model_status) {
                  setModelStatus(statusData.model_status);
                }
              }
            }
          }
        }
      } catch (error) {
        console.error('Failed to fetch models:', error);
      } finally {
        setModelsLoading(false);
      }
    };

    fetchModels();
  }, []);
  
  // Store original file objects for preview
  const [originalFiles, setOriginalFiles] = useState(() => {
    try {
      const saved = localStorage.getItem('playground_originalFiles');
      return saved ? JSON.parse(saved) : [];
    } catch (error) {
      console.error('Failed to load original files from localStorage:', error);
      return [];
    }
  });

  // Controlled state for image preview
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewImage, setPreviewImage] = useState('');
  
  // Load playground internal state from localStorage
  const [inputMode, setInputMode] = useState(() => {
    try {
      const saved = localStorage.getItem('playground_inputMode');
      return saved ? JSON.parse(saved) : 'dropdown';
    } catch (error) {
      console.error('Failed to load input mode from localStorage:', error);
      return 'dropdown';
    }
  });
  
  const [manualConfig, setManualConfig] = useState(() => {
    try {
      const saved = localStorage.getItem('playground_manualConfig');
      return saved ? JSON.parse(saved) : {
        api_url: '',
        model_name: '',
        endpoint_name: ''
      };
    } catch (error) {
      console.error('Failed to load manual config from localStorage:', error);
      return {
        api_url: '',
        model_name: '',
        endpoint_name: ''
      };
    }
  });


  const fileInputRef = useRef(null);

  // Save playground internal state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('playground_inferenceResults', JSON.stringify(inferenceResults));
    } catch (error) {
      console.error('Failed to save inference results to localStorage:', error);
    }
  }, [inferenceResults]);

  useEffect(() => {
    try {
      localStorage.setItem('playground_inputMode', JSON.stringify(inputMode));
    } catch (error) {
      console.error('Failed to save input mode to localStorage:', error);
    }
  }, [inputMode]);

  useEffect(() => {
    try {
      localStorage.setItem('playground_manualConfig', JSON.stringify(manualConfig));
    } catch (error) {
      console.error('Failed to save manual config to localStorage:', error);
    }
  }, [manualConfig]);


  useEffect(() => {
    try {
      localStorage.setItem('playground_originalFiles', JSON.stringify(originalFiles));
    } catch (error) {
      console.error('Failed to save original files to localStorage:', error);
    }
  }, [originalFiles]);


  // Clear inference results cache
  const clearInferenceCache = useCallback(() => {
    console.log('🧹 Clearing inference results cache');
    setInferenceResults({});
    setIsInferring(false);
    try {
      localStorage.removeItem('playground_inferenceResults');
    } catch (error) {
      console.error('Failed to clear inference results cache:', error);
    }
  }, []);

  // Handle page refresh (Command+R on Mac, F5 on Windows/Linux)
  const handlePageRefresh = useCallback((event) => {
    // Check for refresh key combinations
    if ((event.metaKey && event.key === 'r') || event.key === 'F5') {
      event.preventDefault();

      // Clear inference cache on refresh to prevent stuck "处理中" states
      clearInferenceCache();

      // Allow normal page refresh
      window.location.reload();
    }
  }, [clearInferenceCache]);

  // Add keyboard event listener for refresh
  useEffect(() => {
    document.addEventListener('keydown', handlePageRefresh);
    
    return () => {
      document.removeEventListener('keydown', handlePageRefresh);
    };
  }, [handlePageRefresh]);

  // 处理文件上传 - 使用第一个参数 file (原生 File 对象)
  const handleFileUpload = (file) => {
    console.log('=== handleFileUpload START ===');
    console.log('handleFileUpload called with file:', {
      name: file.name,
      type: file.type,
      size: file.size
    });

    // Process file asynchronously
    processFile(file);

    // Return false synchronously to prevent default upload
    return false;
  };

  // Async file processing function
  const processFile = async (file) => {
    console.log('=== processFile START ===');

    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');

    if (!isImage && !isVideo) {
      message.error(`文件 ${file.name} 不支持！只支持图片和视频文件`);
      return false;
    }

    // 检查文件大小
    const maxImageSize = 20 * 1024 * 1024; // 20MB for images
    const maxVideoSize = 50 * 1024 * 1024; // 50MB for videos
    const maxSize = isVideo ? maxVideoSize : maxImageSize;
    const fileTypeText = isVideo ? '视频' : '图片';
    const maxSizeMB = isVideo ? 50 : 20;

    if (file.size > maxSize) {
      Modal.warning({
        title: `${fileTypeText}文件过大`,
        content: (
          <div>
            <p><strong>文件：</strong>{file.name}</p>
            <p><strong>当前大小：</strong>{(file.size/1024/1024).toFixed(1)}MB</p>
            <p><strong>大小限制：</strong>{fileTypeText}文件不能超过 <span style={{color: '#f50'}}>{maxSizeMB}MB</span></p>
            <div style={{marginTop: 16, padding: 12, backgroundColor: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6}}>
              <p style={{margin: 0, fontSize: '13px'}}><strong>建议：</strong></p>
              <ul style={{margin: '8px 0', paddingLeft: 20, fontSize: '13px'}}>
                {isVideo ? (
                  <>
                    <li>使用视频压缩工具减小文件大小</li>
                    <li>降低视频分辨率（如1080p→720p）</li>
                    <li>缩短视频时长</li>
                    <li>使用更高效的编码格式（如H.264）</li>
                  </>
                ) : (
                  <>
                    <li>使用图片压缩工具减小文件大小</li>
                    <li>降低图片分辨率</li>
                    <li>选择更高效的图片格式（如WebP、JPEG）</li>
                    <li>调整图片质量设置</li>
                  </>
                )}
              </ul>
            </div>
          </div>
        ),
        okText: '知道了',
        width: 480
      });
      return false;
    }

    try {
      console.log(`Processing file: ${file.name}, type: ${file.type}, size: ${(file.size/1024/1024).toFixed(2)}MB`);

      // 显示处理进度
      message.loading(`正在处理${fileTypeText}文件: ${file.name}...`, 0);

      // 转换为base64
      const base64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          console.log(`Successfully processed: ${file.name}`);
          resolve(reader.result.split(',')[1]);
        };
        reader.onerror = (error) => {
          console.error(`Failed to read file: ${file.name}`, error);
          reject(error);
        };
        reader.readAsDataURL(file);
      });

      // 创建预览URL
      const previewUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          console.log(`Created preview URL for: ${file.name}`);
          resolve(reader.result);
        };
        reader.onerror = (error) => {
          console.error(`Failed to create preview URL: ${file.name}`, error);
          reject(error);
        };
        reader.readAsDataURL(file);
      });

      message.destroy(); // 清除loading消息
      message.success(`成功处理文件: ${file.name}`);

      console.log('Setting originalFiles with previewUrl:', previewUrl.substring(0, 100) + '...');
      console.log('Setting dataset.files with base64 length:', base64.length);

      // Update state with single file (replace previous)
      const newOriginalFile = {
        name: file.name,
        type: file.type,
        size: file.size,
        previewUrl: previewUrl,
        isImage: isImage,
        isVideo: isVideo
      };
      setOriginalFiles([newOriginalFile]);

      // Update dataset with new file
      const newDataset = {
        prompt: dataset.prompt,  // Keep existing prompt
        files: [base64],
        type: isVideo ? 'video' : 'image'
      };
      console.log('Calling onDatasetChange with:', { ...newDataset, files: [`base64 string of length ${base64.length}`] });
      onDatasetChange(newDataset);

    } catch (error) {
      message.destroy(); // 清除loading消息
      message.error(`文件 ${file.name} 处理失败: ${error.message || '未知错误'}`);
      console.error('File processing error:', error);
    }

    return false; // 阻止自动上传
  };

  // 清除上传的文件
  const handleClearFiles = () => {
    onDatasetChange({ ...dataset, files: [], type: 'image' });
    setOriginalFiles([]);
    
    // 安全地清空文件输入
    if (fileInputRef.current) {
      try {
        // Ant Design Upload组件的内部input可能在不同位置
        const input = fileInputRef.current.input || 
                     fileInputRef.current.querySelector('input[type="file"]') ||
                     fileInputRef.current;
        if (input && input.value !== undefined) {
          input.value = '';
        }
      } catch (error) {
        console.log('Unable to clear file input:', error);
        // 即使清空失败也不影响功能，因为状态已经清空
      }
    }
  };

  // 删除单个文件
  const handleRemoveFile = (index) => {
    const newFiles = [...dataset.files];
    const newOriginalFiles = [...originalFiles];
    
    newFiles.splice(index, 1);
    newOriginalFiles.splice(index, 1);
    
    onDatasetChange({ ...dataset, files: newFiles });
    setOriginalFiles(newOriginalFiles);
    
    if (newFiles.length === 0) {
      onDatasetChange({ ...dataset, files: [], type: 'image' });
    }
  };

  // 开始推理
  const handleStartInference = async () => {
    // Validation based on input mode
    if (inputMode === 'dropdown') {
      if (selectedModels.length === 0) {
        message.warning('请先选择至少一个模型');
        return;
      }
    } else if (inputMode === 'manual') {
      if (!manualConfig.api_url.trim() || !manualConfig.model_name.trim()) {
        message.warning('请填写API URL和模型名称');
        return;
      }
      // Validate URL format
      try {
        new URL(manualConfig.api_url);
      } catch (e) {
        message.warning('请输入有效的API URL');
        return;
      }
    } else if (inputMode === 'sagemaker') {
      if (!manualConfig.endpoint_name.trim()) {
        message.warning('请填写SageMaker端点名称');
        return;
      }
      if (!manualConfig.model_name.trim()) {
        message.warning('请填写模型显示名称（Huggingface模型名称）');
        return;
      }
    }

    if (!dataset.prompt.trim()) {
      message.warning('请输入提示词');
      return;
    }

    setIsInferring(true);
    setInferenceResults({});


    const requestData = {
      text: dataset.prompt,
      frames: dataset.files,
      mediaType: dataset.type,
      max_tokens: params.max_tokens,
      temperature: params.temperature
    };

    // Handle different input modes
    if (inputMode === 'dropdown') {
      requestData.models = selectedModels;
    } else if (inputMode === 'manual') {
      requestData.manual_config = {
        api_url: manualConfig.api_url,
        model_name: manualConfig.model_name
      };
    } else if (inputMode === 'sagemaker') {
      requestData.sagemaker_config = {
        endpoint_name: manualConfig.endpoint_name,
        model_name: manualConfig.model_name || manualConfig.endpoint_name
      };
    }

    try {
      console.log('🚀 Starting inference request:', requestData);
      
      // 使用流式接口
      const response = await fetch('/api/multi-inference', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
      });

      console.log('📡 Response status:', response.status, response.statusText);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        console.log('📦 Received chunk:', JSON.stringify(chunk));
        
        buffer += chunk;
        const lines = buffer.split('\n');
        
        // Keep the last potentially incomplete line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          console.log('📄 Processing line:', JSON.stringify(line));
          
          if (line.startsWith('data: ')) {
            try {
              const jsonStr = line.slice(6).trim();
              console.log('🔍 Parsing JSON:', jsonStr);
              
              if (jsonStr) {
                const data = JSON.parse(jsonStr);
                console.log('✅ Parsed data:', data);
                
                if (data.type === 'complete') {
                  console.log('🏁 Stream complete');
                  setIsInferring(false);
                  break;
                } else if (data.model) {
                  console.log('📊 Updating results for model:', data.model);
                  setInferenceResults(prev => ({
                    ...prev,
                    [data.model]: data
                  }));
                } else if (data.type === 'heartbeat') {
                  console.log('💓 Heartbeat received');
                }
              }
            } catch (e) {
              console.error('❌ 解析SSE数据失败:', e, 'Line:', line);
            }
          } else if (line.trim()) {
            console.log('⚠️ Non-SSE line received:', line);
          }
        }
      }
      
      console.log('🎯 Stream processing finished');
      setIsInferring(false);
    } catch (error) {
      console.error('推理请求失败:', error);
      message.error('推理请求失败，请检查网络连接');
      setIsInferring(false);
    }
  };

  const getFileIcon = () => {
    return dataset.type === 'video' ? <VideoCameraOutlined /> : <FileImageOutlined />;
  };

  const getFileTypeText = () => {
    return dataset.type === 'video' ? '视频' : '图片';
  };

  return (
    <div style={{ padding: '24px', height: '100%' }}>
      <Row gutter={[24, 24]} style={{ height: '100%' }}>
        {/* 左侧：输入区域 */}
        <Col xs={24} lg={10} style={{ height: '100%' }}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {/* 模型选择区域 */}
            <Card title="选择模型" size="small">
              <Space direction="vertical" style={{ width: '100%' }}>
                {/* 模型输入方式选择 */}
                <div>
                  <Text strong style={{ marginBottom: 8, display: 'block' }}>模型输入方式：</Text>
                  <Radio.Group
                    value={inputMode}
                    onChange={(e) => {
                      setInputMode(e.target.value);
                      // Clear configurations when switching modes
                      if (e.target.value === 'manual') {
                        setManualConfig({ api_url: '', model_name: '', endpoint_name: '' });
                      } else if (e.target.value === 'sagemaker') {
                        setManualConfig({ api_url: '', model_name: '', endpoint_name: '' });
                      }
                    }}
                  >
                    <Radio value="dropdown">
                      <Space>
                        <SettingOutlined />
                        从列表选择
                      </Space>
                    </Radio>
                    <Radio value="manual">
                      <Space>
                        <LinkOutlined />
                        手动输入API
                      </Space>
                    </Radio>
                    <Radio value="sagemaker">
                      <Space>
                        <RobotOutlined />
                        SageMaker端点
                      </Space>
                    </Radio>
                  </Radio.Group>
                </div>

                {/* 条件渲染不同的输入方式 */}
                {inputMode === 'dropdown' ? (
                  <div>
                    <Text strong>选择模型：</Text>
                    <Select
                      style={{ width: '100%', marginTop: 8 }}
                      placeholder="请选择一个模型"
                      value={selectedModels.length > 0 ? selectedModels[0] : undefined}
                      onChange={(value) => {
                        // Only allow single selection
                        onModelChange(value ? [value] : []);
                      }}
                      loading={modelsLoading}
                      allowClear
                      showSearch
                      optionFilterProp="label"
                      options={(() => {
                        // Helper function to check if model is available
                        const isModelAvailable = (model) => {
                          if (model.alwaysAvailable) return true;
                          const status = modelStatus[model.key];
                          return status?.status === 'available' || status?.status === 'deployed';
                        };

                        // Group models by category
                        const bedrockModels = availableModels
                          .filter(m => m.category === 'bedrock' && isModelAvailable(m))
                          .map(m => ({
                            label: m.name,
                            value: m.key,
                            desc: m.description
                          }));

                        const ec2Models = availableModels
                          .filter(m => m.category === 'ec2' && isModelAvailable(m))
                          .map(m => ({
                            label: `${m.name} (已部署)`,
                            value: m.key,
                            desc: m.description
                          }));

                        const options = [];

                        if (bedrockModels.length > 0) {
                          options.push({
                            label: 'Bedrock 模型',
                            options: bedrockModels
                          });
                        }

                        if (ec2Models.length > 0) {
                          options.push({
                            label: 'EC2 部署模型',
                            options: ec2Models
                          });
                        }

                        return options;
                      })()}
                      optionRender={(option) => (
                        <div>
                          <div>{option.label}</div>
                          {option.data.desc && (
                            <div style={{ fontSize: '12px', color: '#999' }}>{option.data.desc}</div>
                          )}
                        </div>
                      )}
                    />
                  </div>
                ) : inputMode === 'manual' ? (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div>
                      <Text strong>API URL：</Text>
                      <Input
                        name="api_url"
                        autoComplete="url"
                        value={manualConfig.api_url}
                        onChange={(e) => setManualConfig({ ...manualConfig, api_url: e.target.value })}
                        placeholder="http://your-api-host.com/v1/chat/completions"
                        style={{ marginTop: 4, width: '100%' }}
                        prefix={<LinkOutlined />}
                      />
                      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                        请输入完整的chat completions端点URL，必须包含 /v1/chat/completions 路径
                      </Text>
                    </div>
                    <div>
                      <Text strong>模型名称：</Text>
                      <Input
                        name="model_name"
                        autoComplete="model-name"
                        value={manualConfig.model_name}
                        onChange={(e) => setManualConfig({ ...manualConfig, model_name: e.target.value })}
                        placeholder="gpt-3.5-turbo"
                        style={{ marginTop: 4, width: '100%' }}
                        prefix={<RocketOutlined />}
                      />
                      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                        请输入准确的模型名称，如: gpt-3.5-turbo, claude-3-sonnet-20240229
                      </Text>
                    </div>
                  </Space>
                ) : (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div>
                      <Text strong>SageMaker端点名称：</Text>
                      <Input
                        name="endpoint_name"
                        autoComplete="endpoint-name"
                        value={manualConfig.endpoint_name}
                        onChange={(e) => setManualConfig({ ...manualConfig, endpoint_name: e.target.value })}
                        placeholder="Qwen3-Coder-30B-A3B-Instruct-2025-10-13-05-30-15-995"
                        style={{ marginTop: 4, width: '100%' }}
                        prefix={<RobotOutlined />}
                      />
                      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                        请输入SageMaker端点名称，支持vLLM、TGI等推理框架部署的端点
                      </Text>
                    </div>
                    <div>
                      <Text strong>模型显示名称：</Text>
                      <Input
                        name="model_name"
                        autoComplete="model-display-name"
                        value={manualConfig.model_name}
                        onChange={(e) => setManualConfig({ ...manualConfig, model_name: e.target.value })}
                        placeholder="例如：Qwen/Qwen2.5-Coder-32B-Instruct （必填）"
                        style={{ marginTop: 4, width: '100%' }}
                        prefix={<RocketOutlined />}
                        required
                      />
                      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                        原始模型在Huggingface上的完整名称，例如 Qwen/Qwen2.5-Coder-32B-Instruct
                      </Text>
                    </div>
                  </Space>
                )}
              </Space>
            </Card>

            {/* 提示词输入 - 集成上传功能 */}
            <Card title="输入" size="small">
              <div>
                {/* 文本输入区域 */}
                <TextArea
                  value={dataset.prompt}
                  onChange={(e) => onDatasetChange({ ...dataset, prompt: e.target.value })}
                  placeholder="请输入提示词，描述你希望模型完成的任务..."
                  rows={6}
                  maxLength={2000}
                  showCount
                  style={{
                    resize: 'none'
                  }}
                />

                {/* 上传按钮 - 放在TextArea下方 */}
                <div style={{ marginTop: '8px' }}>
                  <Upload
                    ref={fileInputRef}
                    name="file"
                    multiple={false}
                    showUploadList={false}
                    accept="image/*,video/*"
                    customRequest={({ file, onSuccess }) => {
                      console.log('=== customRequest called ===');
                      console.log('File:', file);
                      processFile(file);
                      onSuccess('ok');
                    }}
                  >
                    <Button
                      icon={<UploadOutlined />}
                      size="small"
                    >
                      上传素材
                    </Button>
                  </Upload>
                </div>
                
                {/* 图片预览区域 - 显示在输入框下方 */}
                {dataset.files.length > 0 && (
                  <div style={{ marginTop: '16px' }}>
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      padding: '8px 0',
                      marginBottom: '12px'
                    }}>
                      <Space>
                        {getFileIcon()}
                        <Text style={{ fontSize: '14px', color: '#666' }}>
                          已上传 {dataset.files.length} 个{getFileTypeText()}文件
                        </Text>
                      </Space>
                      <Button 
                        type="text" 
                        size="small" 
                        icon={<ClearOutlined />}
                        onClick={handleClearFiles}
                        style={{ color: '#999' }}
                      >
                        清除全部
                      </Button>
                    </div>
                    
                    {/* 小图片预览行 */}
                    {originalFiles.length > 0 && (
                      <div style={{ 
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '8px',
                        padding: '12px',
                        border: '1px solid #f0f0f0',
                        borderRadius: '8px',
                        background: '#fafafa'
                      }}>
                        {originalFiles.map((fileInfo, index) => (
                          <div
                            key={index}
                            style={{
                              position: 'relative',
                              border: '1px solid #d9d9d9',
                              borderRadius: '6px',
                              background: '#fff',
                              cursor: fileInfo.isImage ? 'pointer' : 'default',
                              margin: '4px'
                            }}
                            onClick={() => {
                              if (fileInfo.isImage) {
                                // 使用 Ant Design 的 Image 预览功能
                                const img = document.createElement('img');
                                img.src = fileInfo.previewUrl;
                                img.style.display = 'none';
                                document.body.appendChild(img);
                                
                                // 触发 Ant Design Image 预览
                                const event = new MouseEvent('click', { bubbles: true });
                                const imageElement = document.querySelector(`[data-preview-id="preview-${index}"]`);
                                if (imageElement) {
                                  imageElement.click();
                                }
                              }
                            }}
                          >
                            {fileInfo.isImage ? (
                              <Image
                                src={fileInfo.previewUrl}
                                alt={fileInfo.name}
                                width={60}
                                height={60}
                                style={{
                                  objectFit: 'cover',
                                  borderRadius: '4px'
                                }}
                                preview={{
                                  visible: previewVisible && previewImage === fileInfo.previewUrl,
                                  src: fileInfo.previewUrl,
                                  onVisibleChange: (visible) => {
                                    setPreviewVisible(visible);
                                    if (!visible) {
                                      setPreviewImage('');
                                    }
                                  },
                                  destroyOnClose: true
                                }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setPreviewImage(fileInfo.previewUrl);
                                  setPreviewVisible(true);
                                }}
                              />
                            ) : fileInfo.isVideo ? (
                              <div style={{
                                width: '60px',
                                height: '60px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: '#f0f0f0',
                                borderRadius: '4px'
                              }}>
                                <VideoCameraOutlined style={{ fontSize: '20px', color: '#999' }} />
                              </div>
                            ) : (
                              <div style={{
                                width: '60px',
                                height: '60px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: '#f0f0f0',
                                borderRadius: '4px'
                              }}>
                                <FileImageOutlined style={{ fontSize: '20px', color: '#999' }} />
                              </div>
                            )}
                            
                            {/* 删除按钮 */}
                            <div
                              onClick={(e) => {
                                e.stopPropagation();
                                e.preventDefault();
                                console.log('Delete button clicked for index:', index);
                                handleRemoveFile(index);
                              }}
                              style={{
                                position: 'absolute',
                                top: '-4px',
                                right: '-4px',
                                width: '20px',
                                height: '20px',
                                background: '#ff4d4f',
                                color: '#fff',
                                border: '2px solid #fff',
                                borderRadius: '50%',
                                fontSize: '12px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                cursor: 'pointer',
                                zIndex: 10,
                                boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                              }}
                            >
                              <CloseOutlined style={{ fontSize: '10px' }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Card>

            {/* 参数配置 */}
            <Card title="参数设置" size="small">
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Text strong>最大Token数: </Text>
                  <Row gutter={16} align="middle">
                    <Col span={16}>
                      <Slider
                        min={1}
                        max={4096}
                        value={params.max_tokens}
                        onChange={(value) => onParamsChange({ ...params, max_tokens: value })}
                      />
                    </Col>
                    <Col span={8}>
                      <InputNumber
                        min={1}
                        max={4096}
                        value={params.max_tokens}
                        onChange={(value) => onParamsChange({ ...params, max_tokens: value })}
                      />
                    </Col>
                  </Row>
                </div>

                <div>
                  <Text strong>温度: </Text>
                  <Row gutter={16} align="middle">
                    <Col span={16}>
                      <Slider
                        min={0}
                        max={1}
                        step={0.1}
                        value={params.temperature}
                        onChange={(value) => onParamsChange({ ...params, temperature: value })}
                      />
                    </Col>
                    <Col span={8}>
                      <InputNumber
                        min={0}
                        max={1}
                        step={0.1}
                        value={params.temperature}
                        onChange={(value) => onParamsChange({ ...params, temperature: value })}
                      />
                    </Col>
                  </Row>
                </div>
              </Space>
            </Card>

            {/* 执行按钮 */}
            <Button
              type="primary"
              size="large"
              icon={<PlayCircleOutlined />}
              onClick={handleStartInference}
              loading={isInferring}
              disabled={
                inputMode === 'dropdown' ? selectedModels.length === 0 :
                inputMode === 'manual' ? (!manualConfig.api_url.trim() || !manualConfig.model_name.trim()) :
                inputMode === 'sagemaker' ? (!manualConfig.endpoint_name.trim() || !manualConfig.model_name.trim()) : false
              }
              style={{ width: '100%' }}
            >
              {isInferring ? '推理中...' : '开始推理'}
            </Button>
          </Space>
        </Col>

        {/* 右侧：结果展示 */}
        <Col xs={24} lg={14} style={{ height: '100%' }}>
          <Card
            title="推理结果"
            size="small"
            style={{ height: '100%' }}
            bodyStyle={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto', padding: '16px' }}
            extra={
              Object.keys(inferenceResults).length > 0 && (
                <Button
                  type="text"
                  size="small"
                  icon={<ClearOutlined />}
                  onClick={clearInferenceCache}
                  style={{ color: '#999' }}
                >
                  清除结果
                </Button>
              )
            }
          >
            {Object.keys(inferenceResults).length === 0 && !isInferring ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="开始推理后，结果将显示在这里"
              />
            ) : (
              <PlaygroundResultsDisplay
                results={inferenceResults}
                loading={isInferring}
              />
            )}
          </Card>
        </Col>
      </Row>

    </div>
  );
};

export default PlaygroundPage;