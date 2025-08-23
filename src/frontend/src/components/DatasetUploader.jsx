import React, { useState } from 'react';
import { Upload, Button, message, Radio, Input, Space } from 'antd';
import { UploadOutlined, FileImageOutlined, VideoCameraOutlined, FileZipOutlined } from '@ant-design/icons';

const { TextArea } = Input;

const DatasetUploader = ({ onChange, value }) => {
  const [type, setType] = useState(value?.type || 'image');
  const [prompt, setPrompt] = useState(value?.prompt || '');
  const [files, setFiles] = useState(value?.files || []);

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

  const handleChange = (info) => {
    const newFiles = info.fileList.map(f => f.originFileObj);
    setFiles(newFiles);
    onChange && onChange({
      type,
      files: newFiles,
      prompt
    });
  };

  const handlePromptChange = (e) => {
    const newPrompt = e.target.value;
    setPrompt(newPrompt);
    onChange && onChange({
      type,
      files,
      prompt: newPrompt
    });
  };

  const handleTypeChange = (e) => {
    const newType = e.target.value;
    setType(newType);
    setFiles([]);
    onChange && onChange({
      type: newType,
      files: [],
      prompt
    });
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
      <Upload
        beforeUpload={beforeUpload}
        multiple={type === 'image'}
        accept={type === 'image' ? 'image/*' : type === 'video' ? 'video/*' : '.zip'}
        showUploadList={true}
        onChange={handleChange}
        listType={type === 'image' ? 'picture-card' : 'text'}
        maxCount={type === 'image' ? 10 : 1}
      >
        <Button icon={<UploadOutlined />}>
          {type === 'image' ? '上传图片（可多选）' : 
           type === 'video' ? '上传视频' : 
           '上传ZIP包'}
        </Button>
      </Upload>
      <TextArea
        rows={3}
        placeholder="请输入Prompt（如：请描述图片/视频内容...）"
        value={prompt}
        onChange={handlePromptChange}
        style={{ marginTop: 8 }}
      />
    </Space>
  );
};

export default DatasetUploader; 