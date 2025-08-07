import React, { useState, useRef } from 'react';
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
  Modal
} from 'antd';
import { 
  UploadOutlined, 
  PlayCircleOutlined, 
  ClearOutlined,
  FileImageOutlined,
  VideoCameraOutlined,
  RobotOutlined
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
  const [inferenceResults, setInferenceResults] = useState({});
  const [isInferring, setIsInferring] = useState(false);
  const [modelSelectorVisible, setModelSelectorVisible] = useState(false);
  const fileInputRef = useRef(null);

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

      const base64Files = [];
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

          base64Files.push(base64);
          message.destroy(); // 清除loading消息
        } catch (error) {
          message.destroy(); // 清除loading消息
          message.error(`文件 ${uploadFile.name} 处理失败: ${error.message || '未知错误'}`);
          console.error('File processing error:', error);
        }
      }

      if (base64Files.length === 0) {
        message.warning('没有成功处理任何文件');
        return;
      }

      message.success(`成功处理 ${base64Files.length} 个文件`);
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

  // 开始推理
  const handleStartInference = async () => {
    if (selectedModels.length === 0) {
      message.warning('请先选择至少一个模型');
      return;
    }

    if (!dataset.prompt.trim()) {
      message.warning('请输入提示词');
      return;
    }

    setIsInferring(true);
    setInferenceResults({});

    const requestData = {
      models: selectedModels,
      text: dataset.prompt,
      frames: dataset.files,
      mediaType: dataset.type,
      max_tokens: params.max_tokens,
      temperature: params.temperature
    };

    try {
      // 使用流式接口
      const response = await fetch('/api/multi-inference', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'complete') {
                setIsInferring(false);
                break;
              } else if (data.model) {
                setInferenceResults(prev => ({
                  ...prev,
                  [data.model]: data
                }));
              }
            } catch (e) {
              console.error('解析SSE数据失败:', e);
            }
          }
        }
      }
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
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    padding: '8px',
                    background: '#f6f6f6',
                    borderRadius: '4px'
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
                      清除
                    </Button>
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
              disabled={selectedModels.length === 0}
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