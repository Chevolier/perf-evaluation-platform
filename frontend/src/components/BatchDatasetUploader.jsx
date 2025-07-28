import React, { useState } from 'react';
import { Upload, Button, message, Radio, Input, Space, Card, Switch, List, Typography, Divider } from 'antd';
import { UploadOutlined, FileImageOutlined, VideoCameraOutlined, FileZipOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Text } = Typography;

const BatchDatasetUploader = ({ onChange }) => {
  const [type, setType] = useState('image');
  const [batchMode, setBatchMode] = useState(false); // false: 统一prompt, true: 独立prompt
  const [globalPrompt, setGlobalPrompt] = useState('');
  const [samples, setSamples] = useState([]); // [{ file, prompt, id }]

  const beforeUpload = (file) => {
    if (type === 'image') {
      const isImage = file.type.startsWith('image/');
      if (!isImage) {
        message.error('请选择图片文件');
        return Upload.LIST_IGNORE;
      }
    } else if (type === 'video') {
      const isVideo = file.type.startsWith('video/');
      if (!isVideo) {
        message.error('请选择视频文件');
        return Upload.LIST_IGNORE;
      }
    } else if (type === 'zip') {
      const isZip = file.type === 'application/zip' || file.name.endsWith('.zip');
      if (!isZip) {
        message.error('请选择ZIP文件');
        return Upload.LIST_IGNORE;
      }
    }
    return false;
  };

  const handleFileUpload = (info) => {
    const newFiles = info.fileList.map(f => f.originFileObj).filter(Boolean);
    
    if (batchMode) {
      // 独立prompt模式：为每个文件创建独立样本
      const newSamples = newFiles.map(file => ({
        id: Date.now() + Math.random(),
        file,
        prompt: '',
        name: file.name
      }));
      setSamples(newSamples);
      
      onChange && onChange({
        type,
        mode: 'batch',
        samples: newSamples
      });
    } else {
      // 统一prompt模式：所有文件使用相同prompt
      const newSamples = newFiles.map(file => ({
        id: Date.now() + Math.random(),
        file,
        prompt: globalPrompt,
        name: file.name
      }));
      setSamples(newSamples);
      
      onChange && onChange({
        type,
        mode: 'unified',
        samples: newSamples,
        globalPrompt
      });
    }
  };

  const handleGlobalPromptChange = (e) => {
    const newPrompt = e.target.value;
    setGlobalPrompt(newPrompt);
    
    if (!batchMode) {
      // 统一prompt模式：更新所有样本的prompt
      const updatedSamples = samples.map(sample => ({
        ...sample,
        prompt: newPrompt
      }));
      setSamples(updatedSamples);
      
      onChange && onChange({
        type,
        mode: 'unified',
        samples: updatedSamples,
        globalPrompt: newPrompt
      });
    }
  };

  const handleSamplePromptChange = (sampleId, newPrompt) => {
    const updatedSamples = samples.map(sample => 
      sample.id === sampleId 
        ? { ...sample, prompt: newPrompt }
        : sample
    );
    setSamples(updatedSamples);
    
    onChange && onChange({
      type,
      mode: 'batch',
      samples: updatedSamples
    });
  };

  const handleRemoveSample = (sampleId) => {
    const updatedSamples = samples.filter(sample => sample.id !== sampleId);
    setSamples(updatedSamples);
    
    onChange && onChange({
      type,
      mode: batchMode ? 'batch' : 'unified',
      samples: updatedSamples,
      globalPrompt
    });
  };

  const handleTypeChange = (e) => {
    const newType = e.target.value;
    setType(newType);
    setSamples([]);
    onChange && onChange({
      type: newType,
      mode: batchMode ? 'batch' : 'unified',
      samples: [],
      globalPrompt
    });
  };

  const handleBatchModeChange = (checked) => {
    setBatchMode(checked);
    
    if (checked) {
      // 切换到独立prompt模式
      const updatedSamples = samples.map(sample => ({
        ...sample,
        prompt: sample.prompt || globalPrompt
      }));
      setSamples(updatedSamples);
      
      onChange && onChange({
        type,
        mode: 'batch',
        samples: updatedSamples
      });
    } else {
      // 切换到统一prompt模式
      const updatedSamples = samples.map(sample => ({
        ...sample,
        prompt: globalPrompt
      }));
      setSamples(updatedSamples);
      
      onChange && onChange({
        type,
        mode: 'unified',
        samples: updatedSamples,
        globalPrompt
      });
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Radio.Group
        value={type}
        onChange={handleTypeChange}
        buttonStyle="solid"
        style={{ marginBottom: 8 }}
      >
        <Radio.Button value="image"><FileImageOutlined /> 图片</Radio.Button>
        <Radio.Button value="video"><VideoCameraOutlined /> 视频</Radio.Button>
        <Radio.Button value="zip"><FileZipOutlined /> ZIP包</Radio.Button>
      </Radio.Group>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space align="center">
          <Text strong>处理模式：</Text>
          <Switch
            checked={batchMode}
            onChange={handleBatchModeChange}
            checkedChildren="独立Prompt"
            unCheckedChildren="统一Prompt"
          />
          <Text type="secondary">
            {batchMode ? '每个文件可以设置不同的Prompt' : '所有文件使用相同的Prompt'}
          </Text>
        </Space>
      </Card>

      <Upload
        beforeUpload={beforeUpload}
        multiple={type === 'image'}
        accept={type === 'image' ? 'image/*' : type === 'video' ? 'video/*' : '.zip'}
        showUploadList={false}
        onChange={handleFileUpload}
        maxCount={type === 'image' ? 20 : type === 'video' ? 5 : 1}
      >
        <Button icon={<UploadOutlined />} type="dashed" style={{ width: '100%' }}>
          <PlusOutlined />
          {type === 'image' ? '添加图片文件' : 
           type === 'video' ? '添加视频文件' : 
           '添加ZIP文件'}
        </Button>
      </Upload>

      {!batchMode && (
        <>
          <Divider orientation="left">统一Prompt设置</Divider>
          <TextArea
            rows={3}
            placeholder="请输入Prompt（将应用于所有上传的文件）"
            value={globalPrompt}
            onChange={handleGlobalPromptChange}
          />
        </>
      )}

      {samples.length > 0 && (
        <>
          <Divider orientation="left">样本列表 ({samples.length}个)</Divider>
          <List
            dataSource={samples}
            renderItem={(sample) => (
              <List.Item
                actions={[
                  <Button
                    key="remove"
                    type="link"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleRemoveSample(sample.id)}
                  >
                    删除
                  </Button>
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Text strong>{sample.name}</Text>
                      <Text type="secondary">({(sample.file.size / 1024 / 1024).toFixed(2)}MB)</Text>
                    </Space>
                  }
                  description={
                    batchMode ? (
                      <TextArea
                        rows={2}
                        placeholder="请输入该样本的Prompt"
                        value={sample.prompt}
                        onChange={(e) => handleSamplePromptChange(sample.id, e.target.value)}
                        style={{ marginTop: 8 }}
                      />
                    ) : (
                      <Text type="secondary">
                        使用统一Prompt: {sample.prompt ? `"${sample.prompt.substring(0, 50)}..."` : '(未设置)'}
                      </Text>
                    )
                  }
                />
              </List.Item>
            )}
          />
        </>
      )}
    </Space>
  );
};

export default BatchDatasetUploader;