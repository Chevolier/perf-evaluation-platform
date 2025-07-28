import React from 'react';
import { Form, InputNumber } from 'antd';

const ParamConfigurator = ({ value = {}, onChange }) => {
  const [form] = Form.useForm();
  
  const defaultValues = {
    max_tokens: 1024,
    temperature: 0.1,
    ...value
  };

  const handleValuesChange = (changed, all) => {
    onChange({ ...defaultValues, ...all });
  };

  return (
    <Form
      form={form}
      layout="vertical"
      initialValues={defaultValues}
      onValuesChange={handleValuesChange}
    >
      <Form.Item label="Max Tokens" name="max_tokens">
        <InputNumber 
          min={1} 
          max={4096} 
          placeholder="1024"
          style={{ width: '100%' }} 
        />
      </Form.Item>
      <Form.Item label="Temperature" name="temperature">
        <InputNumber 
          min={0} 
          max={1} 
          step={0.01} 
          placeholder="0.1"
          style={{ width: '100%' }} 
        />
      </Form.Item>
    </Form>
  );
};

export default ParamConfigurator; 