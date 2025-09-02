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
import PlaygroundModelSelector from '../components/PlaygroundModelSelector';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Dragger } = Upload;

const PlaygroundPage = ({
  selectedModels,
  dataset,
  onDatasetChange,
  params,
  onParamsChange,
  onModelChange
}) => {
  // Load inference results from localStorage
  const [inferenceResults, setInferenceResults] = useState(() => {
    try {
      const saved = localStorage.getItem('playground_inferenceResults');
      return saved ? JSON.parse(saved) : {};
    } catch (error) {
      console.error('Failed to load inference results from localStorage:', error);
      return {};
    }
  });
  
  const [isInferring, setIsInferring] = useState(false);
  const [modelSelectorVisible, setModelSelectorVisible] = useState(false);
  
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
        model_name: ''
      };
    } catch (error) {
      console.error('Failed to load manual config from localStorage:', error);
      return {
        api_url: '',
        model_name: ''
      };
    }
  });

  // Load history for API URLs and model names
  const [apiUrlHistory, setApiUrlHistory] = useState(() => {
    try {
      const saved = localStorage.getItem('playground_apiUrlHistory');
      return saved ? JSON.parse(saved) : [];
    } catch (error) {
      console.error('Failed to load API URL history from localStorage:', error);
      return [];
    }
  });

  const [modelNameHistory, setModelNameHistory] = useState(() => {
    try {
      const saved = localStorage.getItem('playground_modelNameHistory');
      return saved ? JSON.parse(saved) : [];
    } catch (error) {
      console.error('Failed to load model name history from localStorage:', error);
      return [];
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
      localStorage.setItem('playground_apiUrlHistory', JSON.stringify(apiUrlHistory));
    } catch (error) {
      console.error('Failed to save API URL history to localStorage:', error);
    }
  }, [apiUrlHistory]);

  useEffect(() => {
    try {
      localStorage.setItem('playground_modelNameHistory', JSON.stringify(modelNameHistory));
    } catch (error) {
      console.error('Failed to save model name history to localStorage:', error);
    }
  }, [modelNameHistory]);

  useEffect(() => {
    try {
      localStorage.setItem('playground_originalFiles', JSON.stringify(originalFiles));
    } catch (error) {
      console.error('Failed to save original files to localStorage:', error);
    }
  }, [originalFiles]);

  // Helper functions to manage history
  const addToApiUrlHistory = (url) => {
    if (!url.trim()) return;
    
    setApiUrlHistory(prev => {
      const newHistory = prev.filter(item => item !== url.trim());
      newHistory.unshift(url.trim());
      return newHistory.slice(0, 10); // Keep only the latest 10 entries
    });
  };

  const addToModelNameHistory = (modelName) => {
    if (!modelName.trim()) return;
    
    setModelNameHistory(prev => {
      const newHistory = prev.filter(item => item !== modelName.trim());
      newHistory.unshift(modelName.trim());
      return newHistory.slice(0, 10); // Keep only the latest 10 entries
    });
  };

  const removeFromApiUrlHistory = (url) => {
    setApiUrlHistory(prev => prev.filter(item => item !== url));
  };

  const removeFromModelNameHistory = (modelName) => {
    setModelNameHistory(prev => prev.filter(item => item !== modelName));
  };

  // Handle page refresh (Command+R on Mac, F5 on Windows/Linux)
  const handlePageRefresh = useCallback((event) => {
    // Check for refresh key combinations
    if ((event.metaKey && event.key === 'r') || event.key === 'F5') {
      event.preventDefault();
      
      // Clear all localStorage data
      localStorage.removeItem('playground_inferenceResults');
      localStorage.removeItem('playground_inputMode');
      localStorage.removeItem('playground_manualConfig');
      localStorage.removeItem('playground_apiUrlHistory');
      localStorage.removeItem('playground_modelNameHistory');
      localStorage.removeItem('playground_originalFiles');
      
      // Reset all state to defaults
      setInferenceResults({});
      setIsInferring(false);
      setInputMode('dropdown');
      setManualConfig({
        api_url: '',
        model_name: ''
      });
      setApiUrlHistory([]);
      setModelNameHistory([]);
      setOriginalFiles([]);
      
      // Reset dataset and params via props if they have default reset functions
      if (onDatasetChange) {
        onDatasetChange({
          prompt: '',
          files: [],
          type: 'image'
        });
      }
      if (onParamsChange) {
        onParamsChange({
          max_tokens: 150,
          temperature: 0.7
        });
      }
      if (onModelChange) {
        onModelChange([]);
      }
      
      // Clear file input
      if (fileInputRef.current) {
        try {
          const input = fileInputRef.current.input || 
                       fileInputRef.current.querySelector('input[type="file"]') ||
                       fileInputRef.current;
          if (input && input.value !== undefined) {
            input.value = '';
          }
        } catch (error) {
          console.log('Unable to clear file input:', error);
        }
      }
      
      // Refresh the page
      window.location.reload();
    }
  }, [onDatasetChange, onParamsChange, onModelChange, fileInputRef]);

  // Add keyboard event listener for refresh
  useEffect(() => {
    document.addEventListener('keydown', handlePageRefresh);
    
    return () => {
      document.removeEventListener('keydown', handlePageRefresh);
    };
  }, [handlePageRefresh]);

  // 处理文件上传
  const handleFileUpload = async (file, fileList) => {
    console.log('handleFileUpload called with:', { 
      fileListLength: fileList.length, 
      files: fileList.map(f => ({ name: f.name, type: f.type, size: f.size }))
    });
    
    if (fileList.length === 0) {
      onDatasetChange({ ...dataset, files: [] });
      return false;
    }

    // 处理所有文件
    const processFiles = async () => {
      // 检查是否包含视频文件
      const hasVideo = fileList.some(file => file.type.startsWith('video/'));
      const maxFiles = hasVideo ? 3 : 10; // 视频文件最多3个，图片最多10个
      
      // 限制文件数量
      if (fileList.length > maxFiles) {
        message.error(`最多只能上传${maxFiles}个文件（${hasVideo ? '包含视频时' : '图片'}），以避免内存不足`);
        return;
      }

      // Reset original files before processing new ones
      setOriginalFiles([]);
      
      const base64Files = [];
      const newOriginalFiles = [];
      let fileType = 'image'; // 默认类型
      let totalSize = 0;
      const maxImageSize = 5 * 1024 * 1024; // 5MB for images
      const maxVideoSize = 50 * 1024 * 1024; // 50MB for videos
      const maxTotalSize = 100 * 1024 * 1024; // 100MB total

      for (const uploadFile of fileList) {
        const isImage = uploadFile.type.startsWith('image/');
        const isVideo = uploadFile.type.startsWith('video/');
        
        if (!isImage && !isVideo) {
          message.error(`文件 ${uploadFile.name} 不支持！只支持图片和视频文件`);
          continue;
        }

        // 检查文件大小
        const maxSize = isVideo ? maxVideoSize : maxImageSize;
        const fileTypeText = isVideo ? '视频' : '图片';
        const maxSizeMB = isVideo ? 50 : 5;
        
        if (uploadFile.size > maxSize) {
          Modal.warning({
            title: `${fileTypeText}文件过大`,
            content: (
              <div>
                <p><strong>文件：</strong>{uploadFile.name}</p>
                <p><strong>当前大小：</strong>{(uploadFile.size/1024/1024).toFixed(1)}MB</p>
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
          continue;
        }

        totalSize += uploadFile.size;
        if (totalSize > maxTotalSize) {
          message.error(`文件总大小过大（${(totalSize/1024/1024).toFixed(1)}MB），总计不能超过100MB`);
          break;
        }

        // 设置文件类型（如果有视频，则优先设为video）
        if (isVideo) {
          fileType = 'video';
        }

        try {
          console.log(`Processing file: ${uploadFile.name}, type: ${uploadFile.type}, size: ${(uploadFile.size/1024/1024).toFixed(2)}MB`);
          
          // 显示处理进度
          message.loading(`正在处理${fileTypeText}文件: ${uploadFile.name}...`, 0);
          
          // 转换为base64
          const base64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              console.log(`Successfully processed: ${uploadFile.name}`);
              resolve(reader.result.split(',')[1]);
            };
            reader.onerror = (error) => {
              console.error(`Failed to read file: ${uploadFile.name}`, error);
              reject(error);
            };
            reader.readAsDataURL(uploadFile);
          });

          // 创建预览URL
          const previewUrl = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              console.log(`Created preview URL for: ${uploadFile.name}`);
              resolve(reader.result);
            };
            reader.onerror = (error) => {
              console.error(`Failed to create preview URL: ${uploadFile.name}`, error);
              reject(error);
            };
            reader.readAsDataURL(uploadFile);
          });

          base64Files.push(base64);
          
          // Store file info for preview
          newOriginalFiles.push({
            name: uploadFile.name,
            type: uploadFile.type,
            size: uploadFile.size,
            previewUrl: previewUrl,
            isImage: isImage,
            isVideo: isVideo
          });
          
          message.destroy(); // 清除loading消息
        } catch (error) {
          message.destroy(); // 清除loading消息
          message.error(`文件 ${uploadFile.name} 处理失败: ${error.message || '未知错误'}`);
          console.error('File processing error:', error);
        }
      }

      if (base64Files.length === 0) {
        message.warning('没有成功处理任何文件');
        setOriginalFiles([]);
        return;
      }

      message.success(`成功处理 ${base64Files.length} 个文件`);
      setOriginalFiles(newOriginalFiles);
      onDatasetChange({
        ...dataset,
        files: base64Files,
        type: fileType
      });
    };

    processFiles();
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
    } else {
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
    }

    if (!dataset.prompt.trim()) {
      message.warning('请输入提示词');
      return;
    }

    setIsInferring(true);
    setInferenceResults({});

    // Add to history if using manual input
    if (inputMode === 'manual') {
      addToApiUrlHistory(manualConfig.api_url);
      addToModelNameHistory(manualConfig.model_name);
    }

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
    } else {
      requestData.manual_config = {
        api_url: manualConfig.api_url,
        model_name: manualConfig.model_name
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
                        setManualConfig({ api_url: '', model_name: '' });
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
                        手动输入
                      </Space>
                    </Radio>
                  </Radio.Group>
                </div>

                {/* 条件渲染不同的输入方式 */}
                {inputMode === 'dropdown' ? (
                  <>
                    {selectedModels.length === 0 ? (
                      <div style={{ textAlign: 'center', padding: '20px' }}>
                        <Text type="secondary">尚未选择任何模型</Text>
                        <div style={{ marginTop: 12 }}>
                          <Button 
                            type="primary" 
                            icon={<RobotOutlined />}
                            onClick={() => setModelSelectorVisible(true)}
                          >
                            选择模型
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div>
                        <div style={{ marginBottom: 12 }}>
                          <Text strong>已选择 {selectedModels.length} 个模型：</Text>
                        </div>
                        <div style={{ marginBottom: 12 }}>
                          {selectedModels.map(model => (
                            <Tag key={model} color="blue" style={{ margin: '2px' }}>
                              {model}
                            </Tag>
                          ))}
                        </div>
                        <Button 
                          size="small" 
                          onClick={() => setModelSelectorVisible(true)}
                        >
                          重新选择
                        </Button>
                      </div>
                    )}
                  </>
                ) : (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div>
                      <Text strong>API URL：</Text>
                      <Select
                        mode="tags"
                        value={manualConfig.api_url ? [manualConfig.api_url] : []}
                        onChange={(values) => {
                          const newValue = values.length > 0 ? values[values.length - 1] : '';
                          setManualConfig({ ...manualConfig, api_url: newValue });
                        }}
                        placeholder="http://your-api-host.com/v1/chat/completions"
                        style={{ marginTop: 4, width: '100%' }}
                        maxTagCount={1}
                        dropdownRender={(menu) => (
                          <div>
                            {apiUrlHistory.length > 0 && (
                              <div style={{ padding: '8px 0' }}>
                                <div style={{ padding: '0 12px 8px', fontSize: '12px', color: '#999' }}>
                                  历史记录：
                                </div>
                                {apiUrlHistory.map((url, index) => (
                                  <div
                                    key={index}
                                    style={{
                                      padding: '6px 12px',
                                      cursor: 'pointer',
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center',
                                      borderRadius: '4px',
                                      margin: '2px 8px'
                                    }}
                                    className="history-item"
                                    onMouseEnter={(e) => e.target.style.backgroundColor = '#f5f5f5'}
                                    onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
                                  >
                                    <span
                                      onClick={() => setManualConfig({ ...manualConfig, api_url: url })}
                                      style={{ flex: 1, fontSize: '13px' }}
                                    >
                                      {url}
                                    </span>
                                    <CloseOutlined
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        removeFromApiUrlHistory(url);
                                      }}
                                      style={{ 
                                        fontSize: '10px', 
                                        color: '#999', 
                                        marginLeft: '8px',
                                        padding: '2px'
                                      }}
                                    />
                                  </div>
                                ))}
                              </div>
                            )}
                            {menu}
                          </div>
                        )}
                      />
                      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                        请输入完整的chat completions端点URL，或从历史记录中选择
                      </Text>
                    </div>
                    <div>
                      <Text strong>模型名称：</Text>
                      <Select
                        mode="tags"
                        value={manualConfig.model_name ? [manualConfig.model_name] : []}
                        onChange={(values) => {
                          const newValue = values.length > 0 ? values[values.length - 1] : '';
                          setManualConfig({ ...manualConfig, model_name: newValue });
                        }}
                        placeholder="gpt-3.5-turbo"
                        style={{ marginTop: 4, width: '100%' }}
                        maxTagCount={1}
                        dropdownRender={(menu) => (
                          <div>
                            {modelNameHistory.length > 0 && (
                              <div style={{ padding: '8px 0' }}>
                                <div style={{ padding: '0 12px 8px', fontSize: '12px', color: '#999' }}>
                                  历史记录：
                                </div>
                                {modelNameHistory.map((modelName, index) => (
                                  <div
                                    key={index}
                                    style={{
                                      padding: '6px 12px',
                                      cursor: 'pointer',
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center',
                                      borderRadius: '4px',
                                      margin: '2px 8px'
                                    }}
                                    className="history-item"
                                    onMouseEnter={(e) => e.target.style.backgroundColor = '#f5f5f5'}
                                    onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
                                  >
                                    <span
                                      onClick={() => setManualConfig({ ...manualConfig, model_name: modelName })}
                                      style={{ flex: 1, fontSize: '13px' }}
                                    >
                                      {modelName}
                                    </span>
                                    <CloseOutlined
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        removeFromModelNameHistory(modelName);
                                      }}
                                      style={{ 
                                        fontSize: '10px', 
                                        color: '#999', 
                                        marginLeft: '8px',
                                        padding: '2px'
                                      }}
                                    />
                                  </div>
                                ))}
                              </div>
                            )}
                            {menu}
                          </div>
                        )}
                      />
                      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                        请输入准确的模型名称，或从历史记录中选择
                      </Text>
                    </div>
                  </Space>
                )}
              </Space>
            </Card>

            {/* 文件上传 */}
            <Card title="上传素材" size="small">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Dragger
                  ref={fileInputRef}
                  name="file"
                  multiple={true}
                  beforeUpload={handleFileUpload}
                  showUploadList={false}
                  accept="image/*,video/*"
                  style={{ padding: '20px' }}
                >
                  <p className="ant-upload-drag-icon">
                    {getFileIcon()}
                  </p>
                  <p className="ant-upload-text">
                    点击或拖拽文件到此区域上传
                  </p>
                  <p className="ant-upload-hint">
                    支持图片（JPG、PNG、GIF等，最大5MB）和视频（MP4、MOV、AVI等，最大50MB）
                  </p>
                  <p className="ant-upload-hint" style={{ fontSize: '11px', color: '#999' }}>
                    视频文件最多3个，图片文件最多10个，总大小不超过100MB
                  </p>
                </Dragger>

                {dataset.files.length > 0 && (
                  <div style={{ marginTop: '16px' }}>
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      padding: '8px',
                      background: '#f6f6f6',
                      borderRadius: '4px',
                      marginBottom: '12px'
                    }}>
                      <Space>
                        {getFileIcon()}
                        <Text>已上传 {dataset.files.length} 个{getFileTypeText()}文件</Text>
                      </Space>
                      <Button 
                        type="text" 
                        size="small" 
                        icon={<ClearOutlined />}
                        onClick={handleClearFiles}
                      >
                        清除全部
                      </Button>
                    </div>
                    
                    {/* 图片预览网格 */}
                    {originalFiles.length > 0 && (
                      <div style={{ 
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
                        gap: '12px',
                        maxHeight: '300px',
                        overflowY: 'auto',
                        padding: '8px',
                        border: '1px solid #f0f0f0',
                        borderRadius: '6px',
                        background: '#fafafa'
                      }}>
                        {originalFiles.map((fileInfo, index) => (
                          <div 
                            key={index} 
                            style={{ 
                              position: 'relative',
                              border: '1px solid #d9d9d9',
                              borderRadius: '6px',
                              overflow: 'hidden',
                              background: '#fff'
                            }}
                          >
                            {fileInfo.isImage ? (
                              <Image
                                src={fileInfo.previewUrl}
                                alt={fileInfo.name}
                                style={{
                                  width: '100%',
                                  height: '80px',
                                  objectFit: 'cover'
                                }}
                                fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMIAAADDCAYAAADQvc6UAAABRWlDQ1BJQ0MgUHJvZmlsZQAAKJFjYGASSSwoyGFhYGDIzSspCnJ3UoiIjFJgf8LAwSDCIMogwMCcmFxc4BgQ4ANUwgCjUcG3awyMIPqyLsis7PPOq3QdDFcvjV3jOD1boQVTPQrgSkktTgbSf4A4LbmgqISBgTEFyFYuLykAsTuAbJEioKOA7DkgdjqEvQHEToKwj4DVhAQ5A9k3gGyB5IxEoBmML4BsnSQk8XQkNtReEOBxcfXxUQg1Mjc0dyHgXNJBSWpFCYh2zi+oLMpMzyhRcASGUqqCZ16yno6CkYGRAQMDKMwhqj/fAIcloxgHQqxAjIHBEugw5sUIsSQpBobtQPdLciLEVJYzMPBHMDBsayhILEqEO4DxG0txmrERhM29nYGBddr//5/DGRjYNRkY/l7////39v///y4Dmn+LgeHANwDrkl1AuO+pmgAAADhlWElmTU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAAqACAAQAAAABAAAAwqADAAQAAAABAAAAwwAAAAD9b/HnAAAHlklEQVR4Ae3dP3Ik1RnG4W+FgYxN"
                              />
                            ) : fileInfo.isVideo ? (
                              <div style={{
                                width: '100%',
                                height: '80px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: '#f0f0f0'
                              }}>
                                <VideoCameraOutlined style={{ fontSize: '32px', color: '#999' }} />
                              </div>
                            ) : (
                              <div style={{
                                width: '100%',
                                height: '80px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: '#f0f0f0'
                              }}>
                                <FileImageOutlined style={{ fontSize: '32px', color: '#999' }} />
                              </div>
                            )}
                            
                            {/* 文件信息 */}
                            <div style={{ 
                              padding: '6px',
                              fontSize: '11px',
                              color: '#666',
                              borderTop: '1px solid #f0f0f0'
                            }}>
                              <div style={{ 
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis'
                              }}>
                                {fileInfo.name}
                              </div>
                              <div style={{ fontSize: '10px', color: '#999' }}>
                                {(fileInfo.size / 1024 / 1024).toFixed(1)}MB
                              </div>
                            </div>
                            
                            {/* 删除按钮 */}
                            <Button
                              type="text"
                              size="small"
                              icon={<DeleteOutlined />}
                              onClick={() => handleRemoveFile(index)}
                              style={{
                                position: 'absolute',
                                top: '4px',
                                right: '4px',
                                width: '24px',
                                height: '24px',
                                background: 'rgba(0,0,0,0.5)',
                                color: '#fff',
                                border: 'none',
                                borderRadius: '50%',
                                fontSize: '12px'
                              }}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </Space>
            </Card>

            {/* 提示词输入 */}
            <Card title="提示词" size="small">
              <TextArea
                value={dataset.prompt}
                onChange={(e) => onDatasetChange({ ...dataset, prompt: e.target.value })}
                placeholder="请输入提示词，描述你希望模型完成的任务..."
                rows={6}
                maxLength={2000}
                showCount
              />
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
              disabled={inputMode === 'dropdown' ? selectedModels.length === 0 : (!manualConfig.api_url.trim() || !manualConfig.model_name.trim())}
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

      {/* 模型选择弹窗 */}
      <PlaygroundModelSelector
        visible={modelSelectorVisible}
        onCancel={() => setModelSelectorVisible(false)}
        onOk={() => setModelSelectorVisible(false)}
        selectedModels={selectedModels}
        onModelChange={(newSelectedModels) => {
          // 更新父组件的selectedModels状态
          if (typeof onModelChange === 'function') {
            onModelChange(newSelectedModels);
          }
        }}
      />
    </div>
  );
};

export default PlaygroundPage;