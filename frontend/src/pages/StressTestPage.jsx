import React, { useState, useEffect, useRef, useCallback } from 'react';
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
  Spin,
  Radio,
  Input
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
  CloudOutlined,
  LinkOutlined,
  SettingOutlined
} from '@ant-design/icons';
import { Line } from '@ant-design/plots';

const { Title, Text } = Typography;
const { Option } = Select;

const StressTestPage = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState([]);
  const [inputMode, setInputMode] = useState('dropdown'); // 'dropdown' or 'manual'
  
  // 从localStorage恢复测试会话状态
  const [testSessions, setTestSessions] = useState(() => {
    try {
      const saved = localStorage.getItem('stressTest_sessions');
      return saved ? JSON.parse(saved) : {};
    } catch (error) {
      console.error('Failed to load test sessions from localStorage:', error);
      return {};
    }
  });
  
  const [currentSessionId, setCurrentSessionId] = useState(() => {
    try {
      return localStorage.getItem('stressTest_currentSessionId') || null;
    } catch (error) {
      console.error('Failed to load current session ID from localStorage:', error);
      return null;
    }
  });
  
  const [pollingInterval, setPollingInterval] = useState(null);
  const pollingRestored = useRef(false);

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
      // Parse comma-separated values into arrays of numbers
      const parseCommaSeparatedNumbers = (str) => {
        return str.split(',').map(v => parseInt(v.trim())).filter(n => !isNaN(n) && n > 0);
      };

      const numRequestsArray = parseCommaSeparatedNumbers(values.num_requests);
      const concurrencyArray = parseCommaSeparatedNumbers(values.concurrency);

      // Validate that both arrays have the same length
      if (numRequestsArray.length !== concurrencyArray.length) {
        message.error(`请求总数和并发数的值数量必须相同。当前请求总数有 ${numRequestsArray.length} 个值，并发数有 ${concurrencyArray.length} 个值。`);
        setLoading(false);
        return;
      }

      const requestBody = {
        params: {
          num_requests: numRequestsArray,
          concurrency: concurrencyArray,
          input_tokens: values.input_tokens,
          output_tokens: values.output_tokens,
          temperature: 0.1
        }
      };

      // Handle different input modes
      if (inputMode === 'manual') {
        requestBody.api_url = values.api_url;
        requestBody.model_name = values.model_name;
        // Add deployment configuration for manual input
        requestBody.params.instance_type = values.instance_type;
        requestBody.params.inference_framework = values.framework;
        requestBody.params.tp_size = values.tp_size;
        requestBody.params.dp_size = values.dp_size;
      } else {
        requestBody.model = values.model;
      }

      const response = await fetch('/api/stress-test/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
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
              model: inputMode === 'manual' ? values.model_name : values.model,
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
        } else if (response.status === 404) {
          // Session not found on backend - clear stale session
          console.log(`Session ${sessionId} not found on backend, clearing local data`);
          clearInterval(interval);
          setTestSessions(prev => {
            const updated = { ...prev };
            delete updated[sessionId];
            return updated;
          });
          if (currentSessionId === sessionId) {
            setCurrentSessionId(null);
          }
          message.warning('测试会话已过期，已清除本地缓存');
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
        a.download = `stress_test_report_${sessionId}.pdf`;
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

  // 保存测试会话到localStorage
  useEffect(() => {
    try {
      localStorage.setItem('stressTest_sessions', JSON.stringify(testSessions));
    } catch (error) {
      console.error('Failed to save test sessions to localStorage:', error);
    }
  }, [testSessions]);

  // 保存当前会话ID到localStorage
  useEffect(() => {
    try {
      if (currentSessionId) {
        localStorage.setItem('stressTest_currentSessionId', currentSessionId);
      } else {
        localStorage.removeItem('stressTest_currentSessionId');
      }
    } catch (error) {
      console.error('Failed to save current session ID to localStorage:', error);
    }
  }, [currentSessionId]);

  // 恢复正在进行的测试的轮询 - 只在组件挂载时执行一次
  useEffect(() => {
    if (!pollingRestored.current && currentSessionId && testSessions[currentSessionId]) {
      const session = testSessions[currentSessionId];
      if (session.status === 'running') {
        startPolling(currentSessionId);
        pollingRestored.current = true;
      }
    }
  }, [currentSessionId, testSessions]);

  // 验证和清理过期会话
  const validateSessions = async () => {
    const sessionIds = Object.keys(testSessions);
    for (const sessionId of sessionIds) {
      try {
        const response = await fetch(`/api/stress-test/status/${sessionId}`);
        if (response.status === 404) {
          console.log(`Cleaning up stale session: ${sessionId}`);
          setTestSessions(prev => {
            const updated = { ...prev };
            delete updated[sessionId];
            return updated;
          });
          if (currentSessionId === sessionId) {
            setCurrentSessionId(null);
          }
        }
      } catch (error) {
        console.error(`Failed to validate session ${sessionId}:`, error);
      }
    }
  };

  // Handle page refresh (Command+R on Mac, F5 on Windows/Linux)
  const handlePageRefresh = useCallback((event) => {
    // Check for refresh key combinations
    if ((event.metaKey && event.key === 'r') || event.key === 'F5') {
      event.preventDefault();
      
      // Clear all localStorage data
      localStorage.removeItem('stressTest_sessions');
      localStorage.removeItem('stressTest_currentSessionId');
      
      // Clear polling interval
      if (pollingInterval) {
        clearInterval(pollingInterval);
        setPollingInterval(null);
      }
      
      // Reset all state to defaults
      setTestSessions({});
      setCurrentSessionId(null);
      setLoading(false);
      setInputMode('dropdown');
      
      // Reset form to default values
      form.resetFields();
      form.setFieldsValue({
        num_requests: "50, 100, 200",
        concurrency: "1, 5, 10",
        input_tokens: 32,
        output_tokens: 32,
        instance_type: "g5.2xlarge",
        framework: "vllm",
        tp_size: 1,
        dp_size: 1
      });
      
      // Refresh the page
      window.location.reload();
    }
  }, [pollingInterval, form]);

  useEffect(() => {
    fetchModels();
    // Validate existing sessions on component mount
    if (Object.keys(testSessions).length > 0) {
      validateSessions();
    }
    
    // Add keyboard event listener for refresh
    document.addEventListener('keydown', handlePageRefresh);
    
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
      document.removeEventListener('keydown', handlePageRefresh);
    };
  }, [handlePageRefresh]);

  // 渲染综合性能摘要表格
  const renderComprehensiveSummary = (results) => {
    if (!results || !results.is_comprehensive) return null;
    
    const summary = results.comprehensive_summary;
    const tableData = results.performance_table || [];
    
    // Performance table columns
    const columns = [
      {
        title: 'Conc.',
        dataIndex: 'concurrency',
        key: 'concurrency',
        width: 60,
        align: 'center'
      },
      {
        title: 'RPS',
        dataIndex: 'rps',
        key: 'rps',
        width: 80,
        align: 'center',
        render: (value) => value?.toFixed(2) || 'N/A'
      },
      {
        title: 'Avg Lat.(s)',
        dataIndex: 'avg_latency',
        key: 'avg_latency',
        width: 100,
        align: 'center',
        render: (value) => value?.toFixed(3) || 'N/A'
      },
      {
        title: 'P99 Lat.(s)',
        dataIndex: 'p99_latency',
        key: 'p99_latency',
        width: 100,
        align: 'center',
        render: (value) => value?.toFixed(3) || 'N/A'
      },
      {
        title: 'Gen. toks/s',
        dataIndex: 'gen_toks_per_sec',
        key: 'gen_toks_per_sec',
        width: 100,
        align: 'center',
        render: (value) => value?.toFixed(0) || 'N/A'
      },
      {
        title: 'Tot. toks/s',
        dataIndex: 'total_toks_per_sec',
        key: 'total_toks_per_sec',
        width: 100,
        align: 'center',
        render: (value) => value?.toFixed(0) || 'N/A'
      },
      {
        title: 'Avg TTFT(s)',
        dataIndex: 'avg_ttft',
        key: 'avg_ttft',
        width: 100,
        align: 'center',
        render: (value) => value?.toFixed(3) || 'N/A'
      },
      {
        title: 'P99 TTFT(s)',
        dataIndex: 'p99_ttft',
        key: 'p99_ttft',
        width: 100,
        align: 'center',
        render: (value) => value?.toFixed(3) || 'N/A'
      },
      {
        title: 'Avg TPOT(s)',
        dataIndex: 'avg_tpot',
        key: 'avg_tpot',
        width: 100,
        align: 'center',
        render: (value) => value?.toFixed(3) || 'N/A'
      },
      {
        title: 'P99 TPOT(s)',
        dataIndex: 'p99_tpot',
        key: 'p99_tpot',
        width: 100,
        align: 'center',
        render: (value) => value?.toFixed(3) || 'N/A'
      },
      {
        title: 'Success Rate',
        dataIndex: 'success_rate',
        key: 'success_rate',
        width: 100,
        align: 'center',
        render: (value) => `${value?.toFixed(1) || 0}%`
      }
    ];

    return (
      <div>
        {/* Summary Header */}
        <Card title="Performance Test Summary Report" size="small" style={{ marginBottom: 16 }}>
          <Row gutter={[16, 16]}>
            <Col span={8}>
              <Statistic
                title="Total Generated"
                value={summary?.total_generated_tokens || 0}
                suffix="tokens"
                valueStyle={{ color: '#3f8600' }}
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="Total Test Time"
                value={summary?.total_test_time || 0}
                precision={2}
                suffix="seconds"
                valueStyle={{ color: '#1890ff' }}
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="Avg Output Rate"
                value={summary?.avg_output_rate || 0}
                precision={2}
                suffix="tokens/sec"
                valueStyle={{ color: '#722ed1' }}
              />
            </Col>
          </Row>
        </Card>

        {/* Detailed Performance Metrics Table */}
        <Card title="Detailed Performance Metrics" size="small" style={{ marginBottom: 16 }}>
          <Table
            columns={columns}
            dataSource={tableData.map((row, index) => ({ ...row, key: index }))}
            pagination={false}
            size="small"
            bordered
            scroll={{ x: 1000 }}
            style={{ marginBottom: 16 }}
          />
        </Card>

        {/* Best Performance Configuration */}
        <Card title="Best Performance Configuration" size="small" style={{ marginBottom: 16 }}>
          <Row gutter={[16, 16]}>
            <Col span={12}>
              <div style={{ textAlign: 'center', padding: '16px', background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '6px' }}>
                <Text strong style={{ color: '#52c41a', fontSize: '16px' }}>Highest RPS</Text>
                <div style={{ fontSize: '14px', marginTop: '8px' }}>
                  {summary?.best_rps?.config || 'N/A'}
                </div>
              </div>
            </Col>
            <Col span={12}>
              <div style={{ textAlign: 'center', padding: '16px', background: '#f0f5ff', border: '1px solid #91d5ff', borderRadius: '6px' }}>
                <Text strong style={{ color: '#1890ff', fontSize: '16px' }}>Lowest Latency</Text>
                <div style={{ fontSize: '14px', marginTop: '8px' }}>
                  {summary?.best_latency?.config || 'N/A'}
                </div>
              </div>
            </Col>
          </Row>
        </Card>

        {/* Performance Charts */}
        {renderPerformanceCharts(tableData)}
      </div>
    );
  };

  // 渲染性能指标图表 (for comprehensive results)
  const renderPerformanceCharts = (tableData) => {
    if (!tableData || tableData.length === 0) return null;

    // Prepare data for charts - sort by concurrency for better visualization
    const chartData = [...tableData].sort((a, b) => a.concurrency - b.concurrency);
    console.log('Performance chart data:', chartData);

    const rpsConfig = {
      data: chartData,
      xField: 'concurrency',
      yField: 'rps',
      smooth: true,
      color: '#1890ff',
      point: { 
        size: 4,
        shape: 'circle'
      },
      xAxis: {
        title: {
          text: 'Concurrency'
        }
      },
      yAxis: {
        title: {
          text: 'RPS (req/s)'
        }
      }
    };

    const genThroughputConfig = {
      data: chartData,
      xField: 'concurrency',
      yField: 'gen_toks_per_sec',
      smooth: true,
      color: '#52c41a',
      point: { 
        size: 4,
        shape: 'circle'
      },
      xAxis: {
        title: {
          text: 'Concurrency'
        }
      },
      yAxis: {
        title: {
          text: 'Gen. Throughput (tok/s)'
        }
      }
    };

    const totalThroughputConfig = {
      data: chartData,
      xField: 'concurrency',
      yField: 'total_toks_per_sec',
      smooth: true,
      color: '#389e0d',
      point: { 
        size: 4,
        shape: 'circle'
      },
      xAxis: {
        title: {
          text: 'Concurrency'
        }
      },
      yAxis: {
        title: {
          text: 'Total Throughput (tok/s)'
        }
      }
    };

    const latencyConfig = {
      data: chartData,
      xField: 'concurrency',
      yField: 'avg_latency',
      smooth: true,
      color: '#fa541c',
      point: { 
        size: 4,
        shape: 'circle'
      },
      xAxis: {
        title: {
          text: 'Concurrency'
        }
      },
      yAxis: {
        title: {
          text: 'Average Latency (s)'
        }
      }
    };

    const ttftConfig = {
      data: chartData,
      xField: 'concurrency',
      yField: 'avg_ttft',
      smooth: true,
      color: '#722ed1',
      point: { 
        size: 4,
        shape: 'circle'
      },
      xAxis: {
        title: {
          text: 'Concurrency'
        }
      },
      yAxis: {
        title: {
          text: 'Average TTFT (s)'
        }
      }
    };

    const tpotConfig = {
      data: chartData,
      xField: 'concurrency',
      yField: 'avg_tpot',
      smooth: true,
      color: '#13c2c2',
      point: { 
        size: 4,
        shape: 'circle'
      },
      xAxis: {
        title: {
          text: 'Concurrency'
        }
      },
      yAxis: {
        title: {
          text: 'Average TPOT (s)'
        }
      }
    };

    return (
      <Card title="Performance Metrics vs Concurrency" size="small">
        <Row gutter={[16, 16]}>
          <Col span={12}>
            <div style={{ textAlign: 'center', marginBottom: '16px' }}>
              <Text strong>RPS vs Concurrency</Text>
            </div>
            <Line {...rpsConfig} height={200} />
          </Col>
          <Col span={12}>
            <div style={{ textAlign: 'center', marginBottom: '16px' }}>
              <Text strong>Gen. Throughput vs Concurrency</Text>
            </div>
            <Line {...genThroughputConfig} height={200} />
          </Col>
          <Col span={12}>
            <div style={{ textAlign: 'center', marginBottom: '16px' }}>
              <Text strong>Total Throughput vs Concurrency</Text>
            </div>
            <Line {...totalThroughputConfig} height={200} />
          </Col>
          <Col span={12}>
            <div style={{ textAlign: 'center', marginBottom: '16px' }}>
              <Text strong>Average Latency vs Concurrency</Text>
            </div>
            <Line {...latencyConfig} height={200} />
          </Col>
          <Col span={12}>
            <div style={{ textAlign: 'center', marginBottom: '16px' }}>
              <Text strong>Average TTFT vs Concurrency</Text>
            </div>
            <Line {...ttftConfig} height={200} />
          </Col>
          <Col span={12}>
            <div style={{ textAlign: 'center', marginBottom: '16px' }}>
              <Text strong>Average TPOT vs Concurrency</Text>
            </div>
            <Line {...tpotConfig} height={200} />
          </Col>
        </Row>
      </Card>
    );
  };

  // 渲染性能指标图表 (fallback for old format)
  const renderMetricsCharts = (results) => {
    if (!results || !results.percentiles) return null;

    const percentiles = results.percentiles;
    const percentileLabels = percentiles['Percentiles'] || [];
    
    // 转换百分位标签为数值 (例: "P50" -> 50, "P99" -> 99)
    const convertPercentileToNumber = (label) => {
      if (typeof label === 'string' && label.startsWith('P')) {
        return parseFloat(label.substring(1));
      }
      if (typeof label === 'number') {
        return label;
      }
      // 如果无法解析，尝试直接解析数字
      return parseFloat(label) || 0;
    };

    // TTFT分布图 - 使用百分位数据，x轴为百分位，y轴为TTFT值
    const ttftData = percentileLabels.map((label, index) => ({
      percentile: convertPercentileToNumber(label),
      ttft: percentiles['TTFT (s)']?.[index] || 0
    })); // 不需要反转数据顺序

    // 延迟分布图 - 使用百分位数据，x轴为百分位，y轴为延迟值
    const latencyData = percentileLabels.map((label, index) => ({
      percentile: convertPercentileToNumber(label),
      latency: percentiles['Latency (s)']?.[index] || 0
    })); // 不需要反转数据顺序

    const ttftConfig = {
      data: ttftData,
      xField: 'percentile', // x轴为百分位
      yField: 'ttft', // y轴为TTFT值
      smooth: true,
      color: '#1890ff',
      point: { size: 3 },
      tooltip: {
        formatter: (datum) => [
          {
            name: '百分位',
            value: `P${datum.percentile}`
          },
          {
            name: 'TTFT',
            value: `${datum.ttft?.toFixed(3)}s`
          }
        ]
      },
      xAxis: {
        title: {
          text: '百分位'
        },
        min: 0,
        max: 100,
        tickInterval: 10
      },
      yAxis: {
        title: {
          text: 'TTFT (秒)'
        }
      }
    };

    const latencyConfig = {
      data: latencyData,
      xField: 'percentile', // x轴为百分位
      yField: 'latency', // y轴为延迟值
      smooth: true,
      color: '#52c41a',
      point: { size: 3 },
      tooltip: {
        formatter: (datum) => [
          {
            name: '百分位',
            value: `P${datum.percentile}`
          },
          {
            name: '端到端延迟',
            value: `${datum.latency?.toFixed(3)}s`
          }
        ]
      },
      xAxis: {
        title: {
          text: '百分位'
        },
        min: 0,
        max: 100,
        tickInterval: 10
      },
      yAxis: {
        title: {
          text: '端到端延迟 (秒)'
        }
      }
    };

    // Token使用分布数据 - 使用百分位数据
    const tokenData = percentileLabels.map((label, index) => ({
      percentile: convertPercentileToNumber(label),
      input_tokens: percentiles['Input tokens']?.[index] || 0,
      output_tokens: percentiles['Output tokens']?.[index] || 0
    })); // 不需要反转数据顺序

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
                  data={tokenData}
                  xField="percentile"
                  yField="input_tokens"
                  color="#1890ff"
                  smooth={true}
                  point={{ size: 2 }}
                  height={160}
                  tooltip={{
                    formatter: (datum) => [
                      {
                        name: '百分位',
                        value: `P${datum.percentile}`
                      },
                      {
                        name: '输入Token',
                        value: `${datum.input_tokens}`
                      }
                    ]
                  }}
                  xAxis={{
                    title: { text: '百分位' }
                  }}
                  yAxis={{
                    title: { text: '输入Token数' }
                  }}
                />
              </div>
              <div style={{ width: '50%', paddingLeft: 8 }}>
                <h4 style={{ textAlign: 'center', margin: '0 0 16px 0' }}>输出Token</h4>
                <Line
                  data={tokenData}
                  xField="percentile"
                  yField="output_tokens"
                  color="#52c41a"
                  smooth={true}
                  point={{ size: 2 }}
                  height={160}
                  tooltip={{
                    formatter: (datum) => [
                      {
                        name: '百分位',
                        value: `P${datum.percentile}`
                      },
                      {
                        name: '输出Token',
                        value: `${datum.output_tokens}`
                      }
                    ]
                  }}
                  xAxis={{
                    title: { text: '百分位' }
                  }}
                  yAxis={{
                    title: { text: '输出Token数' }
                  }}
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
           对部署的模型进行性能评估，测量 TTFT、延迟和 QPS 等关键指标
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
                num_requests: "50, 100, 200",
                concurrency: "1, 5, 10",
                input_tokens: 32,
                output_tokens: 32,
                instance_type: "g5.2xlarge",
                framework: "vllm",
                tp_size: 1,
                dp_size: 1
              }}
            >
              <Form.Item label="模型选择方式">
                <Radio.Group 
                  value={inputMode} 
                  onChange={(e) => {
                    setInputMode(e.target.value);
                    // Clear form fields when switching modes
                    form.resetFields(['model', 'api_url', 'model_name', 'instance_type', 'framework', 'tp_size', 'dp_size']);
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
              </Form.Item>

              {inputMode === 'dropdown' ? (
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
              ) : (
                <>
                  <Form.Item
                    name="api_url"
                    label="API URL"
                    rules={[
                      { required: true, message: '请输入API URL' },
                      { type: 'url', message: '请输入有效的URL' }
                    ]}
                    extra="请输入完整的chat completions端点URL，必须包含 /v1/chat/completions 路径"
                  >
                    <Input 
                      placeholder="http://your-api-host.com/v1/chat/completions"
                      prefix={<LinkOutlined />}
                    />
                  </Form.Item>
                  <Form.Item
                    name="model_name"
                    label="模型名称"
                    rules={[{ required: true, message: '请输入模型名称' }]}
                    extra="请输入准确的模型名称，如: gpt-3.5-turbo, claude-3-sonnet-20240229"
                  >
                    <Input 
                      placeholder="gpt-3.5-turbo"
                      prefix={<RocketOutlined />}
                    />
                  </Form.Item>
                  
                  {/* Manual deployment configuration */}
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        name="instance_type"
                        label="实例类型"
                        rules={[{ required: true, message: '请选择实例类型' }]}
                      >
                        <Select placeholder="选择实例类型">
                          <Option value="ml.g5.xlarge">ml.g5.xlarge</Option>
                          <Option value="ml.g5.2xlarge">ml.g5.2xlarge</Option>
                          <Option value="ml.g5.4xlarge">ml.g5.4xlarge</Option>
                          <Option value="ml.g5.8xlarge">ml.g5.8xlarge</Option>
                          <Option value="ml.g5.12xlarge">ml.g5.12xlarge</Option>
                          <Option value="ml.g5.16xlarge">ml.g5.16xlarge</Option>
                          <Option value="ml.g5.24xlarge">ml.g5.24xlarge</Option>
                          <Option value="ml.g5.48xlarge">ml.g5.48xlarge</Option>
                          <Option value="ml.p4d.24xlarge">ml.p4d.24xlarge</Option>
                          <Option value="ml.p4de.24xlarge">ml.p4de.24xlarge</Option>
                          <Option value="ml.p5.48xlarge">ml.p5.48xlarge</Option>
                          <Option value="g5.xlarge">g5.xlarge</Option>
                          <Option value="g5.2xlarge">g5.2xlarge</Option>
                          <Option value="g5.4xlarge">g5.4xlarge</Option>
                          <Option value="g5.8xlarge">g5.8xlarge</Option>
                          <Option value="g5.12xlarge">g5.12xlarge</Option>
                          <Option value="g5.16xlarge">g5.16xlarge</Option>
                          <Option value="g5.24xlarge">g5.24xlarge</Option>
                          <Option value="g5.48xlarge">g5.48xlarge</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name="framework"
                        label="推理框架"
                        rules={[{ required: true, message: '请选择推理框架' }]}
                      >
                        <Select placeholder="选择推理框架">
                          <Option value="vllm">vLLM</Option>
                          <Option value="sglang">SGLang</Option>
                          <Option value="tgi">TGI (Text Generation Inference)</Option>
                          <Option value="transformers">Transformers</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                  </Row>
                  
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        name="tp_size"
                        label="张量并行 (TP Size)"
                        rules={[{ required: true, message: '请输入张量并行数' }]}
                        extra="通常为GPU数量，如1, 2, 4, 8"
                      >
                        <InputNumber
                          min={1}
                          max={8}
                          placeholder="1"
                          style={{ width: '100%' }}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name="dp_size"
                        label="数据并行 (DP Size)"
                        rules={[{ required: true, message: '请输入数据并行数' }]}
                        extra="通常为1，除非使用多节点部署"
                      >
                        <InputNumber
                          min={1}
                          max={16}
                          placeholder="1"
                          style={{ width: '100%' }}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                </>
              )}

              {/* <Alert
                description="提醒：请求总数和并发数需数量相同，按顺序配对测试，如 '50,100,200' 与 '1,5,10' 进行 (50,1), (100,5), (200,10) 三组测试。"
                type="info"
                showIcon={false}
                style={{ marginBottom: 8, padding: '4px 8px' }}
              /> */}

              <Form.Item
                name="num_requests"
                label="请求总数"
                rules={[
                  { required: true, message: '请输入请求总数' },
                  {
                    validator: (_, value) => {
                      if (!value) return Promise.reject(new Error('请输入请求总数'));
                      
                      // Parse comma-separated values
                      const numbers = value.split(',').map(v => v.trim()).filter(v => v);
                      const invalidNumbers = numbers.filter(n => isNaN(n) || parseInt(n) <= 0);
                      
                      if (invalidNumbers.length > 0) {
                        return Promise.reject(new Error('请输入有效的正整数，用逗号分隔'));
                      }

                      // Check if concurrency field exists and validate count match
                      const concurrencyValue = form.getFieldValue('concurrency');
                      if (concurrencyValue) {
                        const concurrencyNumbers = concurrencyValue.split(',').map(v => v.trim()).filter(v => v);
                        const validConcurrencyNumbers = concurrencyNumbers.filter(n => !isNaN(n) && parseInt(n) > 0);
                        
                        if (validConcurrencyNumbers.length > 0 && numbers.length !== validConcurrencyNumbers.length) {
                          return Promise.reject(new Error(`请求总数(${numbers.length}个值)和并发数(${validConcurrencyNumbers.length}个值)的数量必须相同`));
                        }
                      }
                      
                      return Promise.resolve();
                    }
                  }
                ]}
                extra="可以输入多个值，用英文逗号分隔，如: 10, 20, 50"
              >
                <Input
                  placeholder="10, 20, 50, 100"
                  style={{ width: '100%' }}
                />
              </Form.Item>

              <Form.Item
                name="concurrency"
                label="并发数"
                rules={[
                  { required: true, message: '请输入并发数' },
                  {
                    validator: (_, value) => {
                      if (!value) return Promise.reject(new Error('请输入并发数'));
                      
                      // Parse comma-separated values
                      const numbers = value.split(',').map(v => v.trim()).filter(v => v);
                      const invalidNumbers = numbers.filter(n => isNaN(n) || parseInt(n) <= 0);
                      
                      if (invalidNumbers.length > 0) {
                        return Promise.reject(new Error('请输入有效的正整数，用逗号分隔'));
                      }

                      // Check if num_requests field exists and validate count match
                      const numRequestsValue = form.getFieldValue('num_requests');
                      if (numRequestsValue) {
                        const requestNumbers = numRequestsValue.split(',').map(v => v.trim()).filter(v => v);
                        const validRequestNumbers = requestNumbers.filter(n => !isNaN(n) && parseInt(n) > 0);
                        
                        if (validRequestNumbers.length > 0 && numbers.length !== validRequestNumbers.length) {
                          return Promise.reject(new Error(`并发数(${numbers.length}个值)和请求总数(${validRequestNumbers.length}个值)的数量必须相同`));
                        }
                      }
                      
                      return Promise.resolve();
                    }
                  }
                ]}
                extra="可以输入多个值，用英文逗号分隔，需要与请求总数数量相同，如: 1, 5, 10"
              >
                <Input
                  placeholder="1, 5, 10, 20"
                  style={{ width: '100%' }}
                />
              </Form.Item>

              <Row gutter={8}>
                <Col span={12}>
                  <Form.Item
                    name="input_tokens"
                    label="输入Token"
                    rules={[{ required: true, message: '请输入Token数量' }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="输入Token数量"
                      min={1}
                      max={4000}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="output_tokens"
                    label="输出Token"
                    rules={[{ required: true, message: '请输入Token数量' }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="输出Token数量"
                      min={1}
                      max={4000}
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
                {/* Show comprehensive summary if available */}
                {currentSession.results.is_comprehensive ? (
                  renderComprehensiveSummary(currentSession.results)
                ) : (
                  /* Fallback to old format for backward compatibility */
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
              </>
            )}
          </Space>
        </Col>
      </Row>
    </div>
  );
};

export default StressTestPage;