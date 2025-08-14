import React, { useState, useEffect } from 'react';
import {
  Card,
  Typography,
  Form,
  Select,
  InputNumber,
  Button,
  Space,
  Row,
  Col,
  Alert,
  Progress,
  Table,
  message,
  Divider,
  Statistic,
  Spin
} from 'antd';
import { 
  ThunderboltOutlined,
  PlayCircleOutlined,
  DownloadOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  FireOutlined,
  RocketOutlined,
  DashboardOutlined,
  CloudOutlined
} from '@ant-design/icons';
import { Line } from '@ant-design/plots';

const { Title, Text } = Typography;
const { Option } = Select;

const StressTestPage = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState([]);
  const [testSessions, setTestSessions] = useState({});
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [pollingInterval, setPollingInterval] = useState(null);

  // 获取可用模型列表
  const fetchModels = async () => {
    try {
      const response = await fetch('/api/model-list');
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success' && data.models) {
          const availableModels = [];
          
          // 添加Bedrock模型
          if (data.models.bedrock) {
            Object.entries(data.models.bedrock).forEach(([key, info]) => {
              availableModels.push({
                key,
                name: info.name,
                type: 'bedrock',
                description: info.description
              });
            });
          }
          
          // 检查EMD模型状态
          if (data.models.emd) {
            const emdModelKeys = Object.keys(data.models.emd);
            const statusResponse = await fetch('/api/check-model-status', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ models: emdModelKeys })
            });
            
            if (statusResponse.ok) {
              const statusData = await statusResponse.json();
              Object.entries(data.models.emd).forEach(([key, info]) => {
                const status = statusData.model_status?.[key];
                if (status && (status.status === 'deployed' || status.status === 'available')) {
                  availableModels.push({
                    key,
                    name: info.name,
                    type: 'emd',
                    description: info.description,
                    tag: status.tag
                  });
                }
              });
            }
          }
          
          setModels(availableModels);
        }
      }
    } catch (error) {
      console.error('获取模型列表失败:', error);
      message.error('获取模型列表失败');
    }
  };

  // 启动压力测试
  const startStressTest = async (values) => {
    setLoading(true);
    try {
      const response = await fetch('/api/stress-test/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: values.model,
          params: {
            num_requests: values.num_requests,
            concurrency: values.concurrency,
            input_tokens_range: values.input_tokens_range,
            output_tokens_range: values.output_tokens_range,
            temperature: 0.1
          }
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success') {
          const sessionId = data.session_id;
          setCurrentSessionId(sessionId);
          setTestSessions(prev => ({
            ...prev,
            [sessionId]: {
              status: 'running',
              model: values.model,
              params: values,
              startTime: new Date().toISOString()
            }
          }));
          
          message.success('压力测试已开始');
          startPolling(sessionId);
        } else {
          message.error(data.message || '启动测试失败');
        }
      } else {
        const errorText = await response.text();
        console.error('HTTP Error:', response.status, errorText);
        message.error(`启动测试失败 (${response.status}): ${errorText}`);
      }
    } catch (error) {
      console.error('启动测试失败:', error);
      message.error('启动测试失败: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // 轮询测试状态
  const startPolling = (sessionId) => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`/api/stress-test/status/${sessionId}`);
        if (response.ok) {
          const data = await response.json();
          console.log('Polling response:', data); // Debug log
          
          // 后端返回 {status: "success", test_session: {...}} 格式
          const sessionData = data.test_session || data;
          
          setTestSessions(prev => ({
            ...prev,
            [sessionId]: {
              ...prev[sessionId],
              ...sessionData
            }
          }));

          if (sessionData.status === 'completed') {
            clearInterval(interval);
            message.success('压力测试完成！');
          } else if (sessionData.status === 'failed') {
            clearInterval(interval);
            message.error('压力测试失败：' + (sessionData.error || '未知错误'));
          }
        }
      } catch (error) {
        console.error('获取测试状态失败:', error);
      }
    }, 2000);

    setPollingInterval(interval);
  };

  // 下载报告
  const downloadReport = async (sessionId) => {
    try {
      const response = await fetch(`/api/stress-test/download/${sessionId}`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `stress_test_report_${sessionId}.html`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        message.success('报告下载成功');
      } else {
        message.error('下载报告失败');
      }
    } catch (error) {
      console.error('下载报告失败:', error);
      message.error('下载报告失败');
    }
  };

  useEffect(() => {
    fetchModels();
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, []);

  // 渲染性能指标图表
  const renderMetricsCharts = (results) => {
    if (!results || !results.detailed_metrics) return null;

    const metrics = results.detailed_metrics;
    
    // TTFT分布图
    const ttftData = metrics.ttft_distribution?.map((value, index) => ({
      request: index + 1,
      ttft: value
    })) || [];

    // 延迟分布图
    const latencyData = metrics.latency_distribution?.map((value, index) => ({
      request: index + 1,
      latency: value
    })) || [];

    const ttftConfig = {
      data: ttftData,
      xField: 'request',
      yField: 'ttft',
      smooth: true,
      color: '#1890ff',
      point: { size: 3 },
      tooltip: {
        formatter: (datum) => ({
          name: 'TTFT',
          value: `${datum.ttft?.toFixed(3)}s`
        })
      }
    };

    const latencyConfig = {
      data: latencyData,
      xField: 'request',
      yField: 'latency',
      smooth: true,
      color: '#52c41a',
      point: { size: 3 },
      tooltip: {
        formatter: (datum) => ({
          name: '延迟',
          value: `${datum.latency?.toFixed(3)}s`
        })
      }
    };

    // 吞吐量数据
    const throughputData = metrics.input_tokens?.map((input, index) => ({
      request: index + 1,
      input_tokens: input,
      output_tokens: metrics.output_tokens?.[index] || 0
    })) || [];

    const throughputConfig = {
      data: throughputData,
      xField: 'request',
      yField: 'input_tokens',
      seriesField: 'type',
      smooth: true,
      color: ['#1890ff', '#52c41a'],
      point: { size: 2 },
      tooltip: {
        formatter: (datum) => ({
          name: 'Token数量',
          value: `输入: ${datum.input_tokens}, 输出: ${datum.output_tokens}`
        })
      }
    };

    return (
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card title="首字延迟分布 (TTFT)" size="small">
            <Line {...ttftConfig} height={200} />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="端到端延迟分布" size="small">
            <Line {...latencyConfig} height={200} />
          </Card>
        </Col>
        <Col span={24}>
          <Card title="Token使用分布" size="small">
            <div style={{ display: 'flex', height: 200 }}>
              <div style={{ width: '50%', paddingRight: 8 }}>
                <h4 style={{ textAlign: 'center', margin: '0 0 16px 0' }}>输入Token</h4>
                <Line
                  data={throughputData}
                  xField="request"
                  yField="input_tokens"
                  color="#1890ff"
                  smooth={true}
                  point={{ size: 2 }}
                  height={160}
                />
              </div>
              <div style={{ width: '50%', paddingLeft: 8 }}>
                <h4 style={{ textAlign: 'center', margin: '0 0 16px 0' }}>输出Token</h4>
                <Line
                  data={throughputData}
                  xField="request"
                  yField="output_tokens"
                  color="#52c41a"
                  smooth={true}
                  point={{ size: 2 }}
                  height={160}
                />
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    );
  };

  // 渲染测试结果表格
  const renderResultsTable = (results) => {
    if (!results) return null;

    const columns = [
      {
        title: '指标',
        dataIndex: 'metric',
        key: 'metric',
        width: 200
      },
      {
        title: '数值',
        dataIndex: 'value',
        key: 'value'
      },
      {
        title: '单位',
        dataIndex: 'unit',
        key: 'unit'
      }
    ];

    const data = [
      {
        key: 'qps',
        metric: 'QPS (每秒查询数)',
        value: results.qps?.toFixed(2) || 'N/A',
        unit: 'queries/sec'
      },
      {
        key: 'avg_ttft',
        metric: '平均首字延迟',
        value: results.avg_ttft?.toFixed(3) || 'N/A',
        unit: 'seconds'
      },
      {
        key: 'avg_latency',
        metric: '平均端到端延迟',
        value: results.avg_latency?.toFixed(3) || 'N/A',
        unit: 'seconds'
      },
      {
        key: 'p50_ttft',
        metric: 'P50 首字延迟',
        value: results.p50_ttft?.toFixed(3) || 'N/A',
        unit: 'seconds'
      },
      {
        key: 'p99_ttft',
        metric: 'P99 首字延迟',
        value: results.p99_ttft?.toFixed(3) || 'N/A',
        unit: 'seconds'
      },
      {
        key: 'p50_latency',
        metric: 'P50 端到端延迟',
        value: results.p50_latency?.toFixed(3) || 'N/A',
        unit: 'seconds'
      },
      {
        key: 'p99_latency',
        metric: 'P99 端到端延迟',
        value: results.p99_latency?.toFixed(3) || 'N/A',
        unit: 'seconds'
      },
      {
        key: 'tokens_per_second',
        metric: '吞吐量',
        value: results.tokens_per_second?.toFixed(2) || 'N/A',
        unit: 'tokens/sec'
      }
    ];

    return (
      <Table
        columns={columns}
        dataSource={data}
        pagination={false}
        size="small"
        bordered
      />
    );
  };

  // 渲染百分位数据表格
  const renderPercentilesTable = (results) => {
    if (!results || !results.percentiles) return null;

    const percentiles = results.percentiles;
    const percentileLabels = percentiles['Percentiles'] || [];
    
    const columns = [
      { title: '百分位', dataIndex: 'percentile', key: 'percentile', width: 80 },
      { 
        title: 'TTFT (秒)', 
        dataIndex: 'ttft', 
        key: 'ttft',
        render: (value) => value?.toFixed(4) || 'N/A'
      },
      { 
        title: '延迟 (秒)', 
        dataIndex: 'latency', 
        key: 'latency',
        render: (value) => value?.toFixed(4) || 'N/A'
      },
      { 
        title: 'ITL (秒)', 
        dataIndex: 'itl', 
        key: 'itl',
        render: (value) => value?.toFixed(4) || 'N/A'
      },
      { 
        title: 'TPOT (秒)', 
        dataIndex: 'tpot', 
        key: 'tpot',
        render: (value) => value?.toFixed(4) || 'N/A'
      },
      { 
        title: '输入Token', 
        dataIndex: 'inputTokens', 
        key: 'inputTokens' 
      },
      { 
        title: '输出Token', 
        dataIndex: 'outputTokens', 
        key: 'outputTokens' 
      },
      { 
        title: '输出吞吐量 (tok/s)', 
        dataIndex: 'outputThroughput', 
        key: 'outputThroughput',
        render: (value) => value?.toFixed(2) || 'N/A'
      }
    ];

    const data = percentileLabels.map((label, index) => ({
      key: index,
      percentile: label,
      ttft: percentiles['TTFT (s)']?.[index],
      latency: percentiles['Latency (s)']?.[index],
      itl: percentiles['ITL (s)']?.[index],
      tpot: percentiles['TPOT (s)']?.[index],
      inputTokens: percentiles['Input tokens']?.[index],
      outputTokens: percentiles['Output tokens']?.[index],
      outputThroughput: percentiles['Output (tok/s)']?.[index]
    }));

    return (
      <Table
        columns={columns}
        dataSource={data}
        pagination={false}
        size="small"
        bordered
        scroll={{ x: 800 }}
      />
    );
  };

  const currentSession = currentSessionId ? testSessions[currentSessionId] : null;

  return (
    <div style={{ padding: '24px', background: '#f5f5f5', minHeight: '100vh' }}>
      <div style={{ marginBottom: 24 }}>
        <Space>
          <ThunderboltOutlined style={{ fontSize: '24px', color: '#fa541c' }} />
          <Title level={2} style={{ margin: 0 }}>压力测试</Title>
        </Space>
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          使用 Evalscope 对部署的模型进行性能评估，测量 TTFT、延迟和 QPS 等关键指标
        </Text>
      </div>

      <Row gutter={[24, 24]}>
        {/* 测试配置 */}
        <Col span={8}>
          <Card title="测试配置" size="small">
            <Form
              form={form}
              layout="vertical"
              onFinish={startStressTest}
              initialValues={{
                num_requests: 50,
                concurrency: 5,
                input_tokens_range: [50, 200],
                output_tokens_range: [100, 500]
              }}
            >
              <Form.Item
                name="model"
                label="选择模型"
                rules={[{ required: true, message: '请选择要测试的模型' }]}
              >
                <Select placeholder="选择模型">
                  {models.map(model => (
                    <Option key={model.key} value={model.key}>
                      <Space>
                        {model.type === 'bedrock' ? <CloudOutlined /> : <RocketOutlined />}
                        {model.name}
                        {model.tag && <Text type="secondary">({model.tag})</Text>}
                      </Space>
                    </Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item
                name="num_requests"
                label="请求总数"
                rules={[{ required: true, message: '请输入请求总数' }]}
              >
                <InputNumber
                  min={1}
                  max={1000}
                  style={{ width: '100%' }}
                  placeholder="请求总数"
                />
              </Form.Item>

              <Form.Item
                name="concurrency"
                label="并发数"
                rules={[{ required: true, message: '请输入并发数' }]}
              >
                <InputNumber
                  min={1}
                  max={50}
                  style={{ width: '100%' }}
                  placeholder="并发请求数"
                />
              </Form.Item>

              <Row gutter={8}>
                <Col span={12}>
                  <Form.Item
                    name={['input_tokens_range', 0]}
                    label="输入Token最小值"
                    rules={[{ required: true, message: '请输入最小值' }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="最小值"
                      min={1}
                      max={2000}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name={['input_tokens_range', 1]}
                    label="输入Token最大值"
                    rules={[{ required: true, message: '请输入最大值' }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="最大值"
                      min={1}
                      max={2000}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={8}>
                <Col span={12}>
                  <Form.Item
                    name={['output_tokens_range', 0]}
                    label="输出Token最小值"
                    rules={[{ required: true, message: '请输入最小值' }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="最小值"
                      min={1}
                      max={2000}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name={['output_tokens_range', 1]}
                    label="输出Token最大值"
                    rules={[{ required: true, message: '请输入最大值' }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="最大值"
                      min={1}
                      max={2000}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  icon={<PlayCircleOutlined />}
                  block
                  disabled={currentSession?.status === 'running'}
                >
                  {currentSession?.status === 'running' ? '测试进行中...' : '开始压力测试'}
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        {/* 测试状态和进度 */}
        <Col span={16}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            {/* 当前测试状态 */}
            {currentSession && (
              <Card title="测试状态" size="small">
                <Row gutter={[16, 16]}>
                  <Col span={6}>
                    <Statistic
                      title="测试模型"
                      value={currentSession.model}
                      prefix={<DashboardOutlined />}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="状态"
                      value={currentSession.status === 'running' ? '进行中' : 
                             currentSession.status === 'completed' ? '已完成' :
                             currentSession.status === 'failed' ? '失败' : '未知'}
                      valueStyle={{
                        color: currentSession.status === 'running' ? '#1890ff' :
                               currentSession.status === 'completed' ? '#52c41a' :
                               currentSession.status === 'failed' ? '#ff4d4f' : '#666'
                      }}
                      prefix={<ClockCircleOutlined />}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="进度"
                      value={currentSession.progress || 0}
                      suffix="%"
                      prefix={<FireOutlined />}
                    />
                  </Col>
                  <Col span={6}>
                    {currentSession.status === 'completed' && (
                      <Button
                        type="primary"
                        icon={<DownloadOutlined />}
                        onClick={() => downloadReport(currentSessionId)}
                      >
                        下载报告
                      </Button>
                    )}
                  </Col>
                </Row>
                
                {currentSession.status === 'running' && (
                  <div style={{ marginTop: 16 }}>
                    <Progress
                      percent={currentSession.progress || 0}
                      status="active"
                      strokeColor={{
                        from: '#108ee9',
                        to: '#87d068',
                      }}
                    />
                    <Text type="secondary" style={{ marginTop: 8, display: 'block' }}>
                      {currentSession.message || currentSession.current_message || '正在执行压力测试...'}
                    </Text>
                  </div>
                )}

                {currentSession.status === 'failed' && currentSession.error && (
                  <Alert
                    message="测试失败"
                    description={currentSession.error}
                    type="error"
                    style={{ marginTop: 16 }}
                  />
                )}
              </Card>
            )}

            {/* 测试结果 */}
            {currentSession && currentSession.status === 'completed' && currentSession.results && (
              <>
                <Card title="性能指标概览" size="small">
                  <Row gutter={[16, 16]}>
                    <Col span={6}>
                      <Statistic
                        title="QPS"
                        value={currentSession.results.qps || 0}
                        precision={2}
                        suffix="req/s"
                        valueStyle={{ color: '#3f8600' }}
                      />
                    </Col>
                    <Col span={6}>
                      <Statistic
                        title="平均TTFT"
                        value={currentSession.results.avg_ttft || 0}
                        precision={3}
                        suffix="s"
                        valueStyle={{ color: '#cf1322' }}
                      />
                    </Col>
                    <Col span={6}>
                      <Statistic
                        title="平均延迟"
                        value={currentSession.results.avg_latency || 0}
                        precision={3}
                        suffix="s"
                        valueStyle={{ color: '#1890ff' }}
                      />
                    </Col>
                    <Col span={6}>
                      <Statistic
                        title="吞吐量"
                        value={currentSession.results.tokens_per_second || 0}
                        precision={2}
                        suffix="tok/s"
                        valueStyle={{ color: '#722ed1' }}
                      />
                    </Col>
                  </Row>
                </Card>

                <Card title="详细指标" size="small">
                  {renderResultsTable(currentSession.results)}
                </Card>

                {renderMetricsCharts(currentSession.results)}
                
                <Card title="百分位数据" size="small">
                  {renderPercentilesTable(currentSession.results)}
                </Card>
              </>
            )}
          </Space>
        </Col>
      </Row>
    </div>
  );
};

export default StressTestPage;