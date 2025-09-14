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
  const [datasetType, setDatasetType] = useState('random');
  const [isMultimodal, setIsMultimodal] = useState(false);
  
  // Model type mapping - maps model names to LLM or VLM
  const MODEL_TYPE_MAP = {
    // Common LLM models
    "Qwen3-8B": "LLM",
    "Qwen2.5-8B": "LLM", 
    "Qwen2.5-14B": "LLM",
    "Qwen2.5-32B": "LLM",
    "Qwen2.5-72B": "LLM",
    "Qwen2-7B": "LLM",
    "Qwen2-1.5B": "LLM",
    "Qwen2-0.5B": "LLM",
    "Llama-3.2-1B": "LLM",
    "Llama-3.2-3B": "LLM", 
    "Llama-3.1-8B": "LLM",
    "Llama-3.1-70B": "LLM",
    "Llama-3.1-405B": "LLM",
    "Gemma-2-2B": "LLM",
    "Gemma-2-9B": "LLM",
    "Gemma-2-27B": "LLM",
    // Common VLM models
    "Qwen2.5-VL-7B-Instruct": "VLM",
    "Qwen2.5-VL-32B-Instruct": "VLM",
    "Qwen2-VL-7B-Instruct": "VLM",
    "Qwen2-VL-2B-Instruct": "VLM",
    "Llava-1.5-7B": "VLM",
    "Llava-1.5-13B": "VLM", 
    "Llava-Next-7B": "VLM",
    "Llava-Next-13B": "VLM",
    "InternVL2-8B": "VLM",
    "InternVL2-26B": "VLM",
    "MiniCPM-V-2.6": "VLM",
    "CogVLM2-19B": "VLM"
  };
  
  // Extract model name from path using regex (looks for model size pattern like 7B, 32B, etc.)
  const extractModelNameFromPath = (modelPath) => {
    if (!modelPath || typeof modelPath !== 'string') return modelPath;
    
    // If it's already a simple model name, return as is
    if (!modelPath.includes('/')) return modelPath;
    
    // Extract model name from path - look for directory names that contain size patterns
    const pathParts = modelPath.split('/').filter(part => part.length > 0);
    
    // Find the part that looks like a model name (contains size like 7B, 32B, etc.)
    for (const part of pathParts) {
      if (/\d+[Bb]/.test(part)) {
        return part;
      }
    }
    
    // Fallback: return the last directory name
    return pathParts[pathParts.length - 1] || modelPath;
  };
  
  // Determine if a model is multimodal based on model name
  const getModelType = (modelName) => {
    if (!modelName) return 'LLM';
    
    const extractedName = extractModelNameFromPath(modelName);
    
    // Direct lookup first
    if (MODEL_TYPE_MAP[extractedName]) {
      return MODEL_TYPE_MAP[extractedName];
    }
    
    // Fallback: check for VLM keywords in the name
    const vlmKeywords = ['VL', 'Vision', 'Llava', 'InternVL', 'CogVLM', 'MiniCPM-V'];
    const nameUpper = extractedName.toUpperCase();
    
    for (const keyword of vlmKeywords) {
      if (nameUpper.includes(keyword.toUpperCase())) {
        return 'VLM';
      }
    }
    
    return 'LLM';
  };
  
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

  // Handle model selection change to detect multimodal models
  const handleModelChange = (modelKey) => {
    const selectedModel = models.find(model => model.key === modelKey);
    const modelType = getModelType(selectedModel?.name || modelKey);
    setIsMultimodal(modelType === 'VLM');
    
    // Force form to re-render to update conditional validation
    setTimeout(() => {
      form.validateFields(['input_tokens', 'output_tokens', 'image_width', 'image_height', 'image_num']);
    }, 0);
  };
  
  // Handle manual model name change to detect multimodal models
  const handleManualModelNameChange = (modelName) => {
    const modelType = getModelType(modelName);
    setIsMultimodal(modelType === 'VLM');
    
    // Force form to re-render to update conditional validation
    setTimeout(() => {
      form.validateFields(['input_tokens', 'output_tokens', 'image_width', 'image_height', 'image_num']);
    }, 0);
  };
  
  // Determine if parameters should be enabled based on model type and dataset
  const shouldEnableTokenParams = () => {
    const currentModelType = inputMode === 'dropdown' 
      ? (() => {
          const modelKey = form.getFieldValue('model');
          const selectedModel = models.find(model => model.key === modelKey);
          return getModelType(selectedModel?.name || modelKey);
        })()
      : getModelType(form.getFieldValue('model_name'));
    
    const currentDataset = form.getFieldValue('dataset') || datasetType;
    
    // Enable token params if:
    // - LLM model with random dataset
    // - VLM model with random_vl dataset
    return (currentModelType === 'LLM' && currentDataset === 'random') ||
           (currentModelType === 'VLM' && currentDataset === 'random_vl');
  };
  
  const shouldEnableImageParams = () => {
    const currentModelType = inputMode === 'dropdown' 
      ? (() => {
          const modelKey = form.getFieldValue('model');
          const selectedModel = models.find(model => model.key === modelKey);
          return getModelType(selectedModel?.name || modelKey);
        })()
      : getModelType(form.getFieldValue('model_name'));
    
    const currentDataset = form.getFieldValue('dataset') || datasetType;
    
    // Enable image params if VLM model with random_vl dataset
    return currentModelType === 'VLM' && currentDataset === 'random_vl';
  };

  // 获取可用模型列表
  // Cross-field validation helper
  const validateFieldCount = () => {
    const concurrencyValue = form.getFieldValue('concurrency');
    const numRequestsValue = form.getFieldValue('num_requests');
    
    if (!concurrencyValue || !numRequestsValue) return null;
    
    const parseCommaSeparatedNumbers = (str) => {
      return str.split(',').map(v => v.trim()).filter(v => v && !isNaN(v) && parseInt(v) > 0);
    };
    
    const concurrencyNumbers = parseCommaSeparatedNumbers(concurrencyValue);
    const requestNumbers = parseCommaSeparatedNumbers(numRequestsValue);
    
    if (concurrencyNumbers.length > 0 && requestNumbers.length > 0 && concurrencyNumbers.length !== requestNumbers.length) {
      return `并发数(${concurrencyNumbers.length}个值)和请求总数(${requestNumbers.length}个值)的数量必须相同`;
    }
    
    return null;
  };

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
                description: info.description,
                supports_multimodal: info.supports_multimodal || false
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
                    tag: status.tag,
                    supports_multimodal: info.supports_multimodal || false
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
          temperature: 0.1,
          dataset: values.dataset,
          dataset_path: values.dataset_path,
          deployment_method: values.deployment_method
        }
      };

      // Add VLM parameters if multimodal model is selected
      if (isMultimodal) {
        requestBody.params.image_width = values.image_width;
        requestBody.params.image_height = values.image_height;
        requestBody.params.image_num = values.image_num;
        requestBody.params.image_format = 'RGB'; // Fixed value as per test file
      }

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

  // 下载报告 - Generate HTML report in session folder and zip download
  const downloadReport = async (sessionId) => {
    const session = testSessions[sessionId];
    if (!session || !session.results) {
      message.error('No test results available for download');
      return;
    }

    try {
      // Import JSZip dynamically
      const JSZip = (await import('jszip')).default;

      message.loading('正在生成HTML报告...', 0);

      const timestamp = new Date().toLocaleString();
      const results = session.results;

      // Generate performance tables HTML for comprehensive results
      let tablesHtml = '';
      if (results.is_comprehensive && results.performance_table) {
        tablesHtml = `
          <h3>📊 Comprehensive Performance Metrics</h3>
          <table class="performance-table">
            <thead>
              <tr>
                <th>Concurrency</th>
                <th>RPS</th>
                <th>Avg Latency (s)</th>
                <th>Gen Throughput (tok/s)</th>
                <th>Total Throughput (tok/s)</th>
                <th>Avg TTFT (s)</th>
                <th>Avg TPOT (s)</th>
                <th>Avg ITL (s)</th>
                <th>Success Rate (%)</th>
              </tr>
            </thead>
            <tbody>
              ${results.performance_table.map(row => `
                <tr>
                  <td>${row.concurrency || 0}</td>
                  <td>${(row.rps || 0).toFixed(2)}</td>
                  <td>${(row.avg_latency || 0).toFixed(3)}</td>
                  <td>${(row.gen_toks_per_sec || 0).toFixed(0)}</td>
                  <td>${(row.total_toks_per_sec || 0).toFixed(0)}</td>
                  <td>${(row.avg_ttft || 0).toFixed(3)}</td>
                  <td>${(row.avg_tpot || 0).toFixed(3)}</td>
                  <td>${(row.avg_itl || 0).toFixed(3)}</td>
                  <td>${(row.success_rate || 0).toFixed(1)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }

      // Prepare chart data for interactive charts
      let chartsHtml = '';
      if (results.is_comprehensive && results.performance_table) {
        const chartData = results.performance_table.sort((a, b) => a.concurrency - b.concurrency);

        const metrics = [
          { key: 'rps', title: 'RPS vs Concurrency', yLabel: 'Requests per Second' },
          { key: 'gen_toks_per_sec', title: 'Generation Throughput vs Concurrency', yLabel: 'Tokens per Second' },
          { key: 'total_toks_per_sec', title: 'Total Throughput vs Concurrency', yLabel: 'Tokens per Second' },
          { key: 'avg_latency', title: 'Average Latency vs Concurrency', yLabel: 'Latency (seconds)' },
          { key: 'avg_ttft', title: 'Average TTFT vs Concurrency', yLabel: 'TTFT (seconds)' },
          { key: 'avg_tpot', title: 'Average TPOT vs Concurrency', yLabel: 'TPOT (seconds)' }
        ];

        chartsHtml = metrics.map((metric, index) => {
          const traces = [{
            x: chartData.map(d => d.concurrency),
            y: chartData.map(d => d[metric.key] || 0),
            type: 'scatter',
            mode: 'lines+markers',
            name: metric.title,
            line: {
              color: ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2'][index % 6],
              width: 3
            },
            marker: {
              size: 8,
              color: ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2'][index % 6]
            },
            hovertemplate: '<b>' + metric.title + '</b><br>' +
                          '%{y}<br>' +
                          '<extra></extra>'
          }];

          return `
            <div class="chart-container">
              <div class="chart-title">${metric.title}</div>
              <div id="chart-${metric.key}" style="width: 100%; height: 400px;"></div>
              <script>
                (function() {
                    var chartDiv = document.getElementById('chart-${metric.key}');
                    Plotly.newPlot(chartDiv, ${JSON.stringify(traces)}, {
                      title: false,
                      xaxis: { title: 'Concurrency' },
                      yaxis: { title: '${metric.yLabel}' },
                      hovermode: 'x unified',
                      showlegend: false,
                      margin: { t: 10, r: 40, b: 80, l: 60 },
                      autosize: true
                    }, {
                      responsive: true,
                      displayModeBar: false
                    });

                    // Ensure proper resize
                    window.addEventListener('resize', function() {
                        Plotly.Plots.resize(chartDiv);
                    });
                })();
              </script>
            </div>
          `;
        }).join('');
      }

      // Generate complete HTML content
      const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stress Test Results Report</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            color: #1890ff;
            text-align: center;
            margin-bottom: 30px;
            font-size: 28px;
        }
        h2 {
            color: #333;
            border-bottom: 2px solid #1890ff;
            padding-bottom: 10px;
            margin-top: 40px;
        }
        h3 {
            color: #555;
            margin-top: 30px;
        }
        .timestamp {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 30px;
        }
        .session-summary {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .summary-item {
            margin: 10px 0;
            font-size: 16px;
        }
        .summary-label {
            font-weight: bold;
            color: #1890ff;
        }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 30px;
            margin: 30px 0;
        }
        .chart-container {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            min-height: 500px;
            display: flex;
            flex-direction: column;
        }
        .chart-container > div:last-child {
            flex: 1;
            min-height: 400px;
        }
        .chart-title {
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin-bottom: 15px;
            text-align: center;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .performance-table {
            font-size: 12px;
        }
        .performance-table th {
            background-color: #f0f0f0;
            font-size: 11px;
        }
        @media (max-width: 1200px) {
            .charts-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Stress Test Results Report</h1>
        <div class="timestamp">Generated on: ${timestamp}</div>

        <h2>📊 Test Session Summary</h2>
        <div class="session-summary">
            <div class="summary-item"><span class="summary-label">Model:</span> ${session.model}</div>
            <div class="summary-item"><span class="summary-label">Session ID:</span> ${sessionId}</div>
            <div class="summary-item"><span class="summary-label">Status:</span> ${session.status}</div>
            <div class="summary-item"><span class="summary-label">Start Time:</span> ${session.startTime || 'N/A'}</div>
            ${results.comprehensive_summary ? `
            <div class="summary-item"><span class="summary-label">Total Generated Tokens:</span> ${results.comprehensive_summary.total_generated_tokens || 0}</div>
            <div class="summary-item"><span class="summary-label">Total Test Time:</span> ${(results.comprehensive_summary.total_test_time || 0).toFixed(2)} seconds</div>
            <div class="summary-item"><span class="summary-label">Average Output Rate:</span> ${(results.comprehensive_summary.avg_output_rate || 0).toFixed(2)} tokens/sec</div>
            ` : ''}
        </div>

        ${results.is_comprehensive && chartsHtml ? `
        <h2>📈 Interactive Performance Charts</h2>
        <div class="charts-grid">
            ${chartsHtml}
        </div>
        ` : ''}

        <h2>📋 Performance Metrics Tables</h2>
        ${tablesHtml}
    </div>
</body>
</html>`;

      // Send HTML content to backend to save in session folder
      const saveResponse = await fetch('/api/stress-test/save-report', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          html_content: htmlContent,
          filename: 'stress-test-report.html'
        }),
      });

      if (!saveResponse.ok) {
        throw new Error(`Failed to save HTML report: ${saveResponse.status}`);
      }

      // Request backend to zip the session folder and return it
      message.loading('正在压缩会话文件夹...', 0);

      const zipResponse = await fetch(`/api/stress-test/download-zip/${sessionId}`, {
        method: 'GET'
      });

      if (!zipResponse.ok) {
        throw new Error(`Failed to create zip: ${zipResponse.status}`);
      }

      // Download the zip file
      const zipBlob = await zipResponse.blob();
      const url = window.URL.createObjectURL(zipBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `stress-test-session-${sessionId}-${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      message.destroy();
      message.success('会话文件夹已压缩并下载');

    } catch (error) {
      message.destroy();
      console.error('Error generating HTML report:', error);
      message.error('生成HTML报告时出现错误');
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
      
      // Allow normal page refresh without clearing state
      // State will be preserved through localStorage and restored on page load
      window.location.reload();
    }
  }, []);

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
        title: 'Avg TPOT(s)',
        dataIndex: 'avg_tpot',
        key: 'avg_tpot',
        width: 100,
        align: 'center',
        render: (value) => value?.toFixed(3) || 'N/A'
      },
      {
        title: 'Avg ITL(s)',
        dataIndex: 'avg_itl',
        key: 'avg_itl',
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
        <Col span={24}>
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
                deployment_method: inputMode === 'dropdown' ? "SageMaker Endpoint" : "EC2",
                dataset: "random",
                image_width: 512,
                image_height: 512,
                image_num: 1,
                instance_type: "g5.2xlarge",
                framework: "vllm",
                tp_size: 1,
                dp_size: 1
              }}
            >
              <Row gutter={8} justify="space-between" align="middle" style={{ marginBottom: 16, padding: '8px 0' }}>
                <Col flex="none">
                  <Text strong style={{ fontSize: '14px' }}>模型选择方式:</Text>
                </Col>
                <Col flex="1" style={{ textAlign: 'left', paddingLeft: '16px' }}>
                  <Radio.Group 
                    value={inputMode} 
                    onChange={(e) => {
                      const newMode = e.target.value;
                      setInputMode(newMode);
                      // Clear form fields when switching modes
                      form.resetFields(['model', 'deployment_method', 'dataset', 'dataset_path', 'api_url', 'model_name', 'instance_type', 'framework', 'tp_size', 'dp_size', 'image_width', 'image_height', 'image_num']);
                      // Set default deployment method based on input mode
                      if (newMode === 'dropdown') {
                        form.setFieldsValue({ deployment_method: 'SageMaker Endpoint' });
                      } else if (newMode === 'manual') {
                        form.setFieldsValue({ deployment_method: 'EC2' });
                      }
                    }}
                  >
                    <Radio value="dropdown" style={{ marginRight: '24px' }}>
                      <Space>
                        <SettingOutlined />
                        <span>从列表选择</span>
                      </Space>
                    </Radio>
                    <Radio value="manual">
                      <Space>
                        <LinkOutlined />
                        <span>手动输入</span>
                      </Space>
                    </Radio>
                  </Radio.Group>
                </Col>
              </Row>

              {inputMode === 'dropdown' ? (
                <>
                  {/* Main configuration row */}
                  <Row gutter={8} justify="space-between">
                    <Col flex="1">
                      <Form.Item
                        name="model"
                        label="选择模型"
                        rules={[{ required: true, message: '请选择要测试的模型' }]}
                        style={{ marginBottom: 16 }}
                      >
                        <Select 
                          placeholder="选择模型"
                          onChange={handleModelChange}
                        >
                          {models.map(model => (
                            <Option key={model.key} value={model.key}>
                              <Space>
                                {model.type === 'bedrock' ? <CloudOutlined /> : <RocketOutlined />}
                                {model.name}
                                {model.tag && <Text type="secondary">({model.tag})</Text>}
                                {model.supports_multimodal && <Text type="success" style={{ fontSize: '12px' }}>[VLM]</Text>}
                              </Space>
                            </Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col flex="1">
                      <Form.Item
                        name="deployment_method"
                        label="部署方式"
                        rules={[{ required: true, message: '请选择部署方式' }]}
                        initialValue="SageMaker Endpoint"
                        style={{ marginBottom: 16 }}
                      >
                        <Select placeholder="选择部署方式">
                          <Option value="SageMaker Endpoint">Endpoint</Option>
                          <Option value="SageMaker HyperPod">HyperPod</Option>
                          <Option value="EKS">EKS</Option>
                          <Option value="EC2">EC2</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col flex="1">
                      <Form.Item
                        name="dataset"
                        label="数据集"
                        rules={[{ required: true, message: '请选择数据集' }]}
                        initialValue="random"
                        style={{ marginBottom: 16 }}
                      >
                        <Select 
                          placeholder="选择数据集"
                          onChange={(value) => {
                            setDatasetType(value);
                            // Force form to re-render to update conditional validation
                            setTimeout(() => {
                              form.validateFields(['input_tokens', 'output_tokens', 'image_width', 'image_height', 'image_num']);
                            }, 0);
                          }}
                        >
                          <Option value="random">random</Option>
                          <Option value="random_vl">random_vl</Option>
                          <Option value="openqa">openqa</Option>
                          <Option value="longalpaca">longalpaca</Option>
                          <Option value="flickr8k">flickr8k</Option>
                          <Option value="custom">custom</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col flex="1">
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
                              
                              // Cross-field validation
                              const crossFieldError = validateFieldCount();
                              if (crossFieldError) {
                                return Promise.reject(new Error(crossFieldError));
                              }
                              
                              return Promise.resolve();
                            }
                          }
                        ]}
                        style={{ marginBottom: 16 }}
                      >
                        <Input
                          placeholder="1, 5, 10"
                          style={{ width: '100%' }}
                          onChange={() => {
                            // Trigger validation for both fields when either changes
                            setTimeout(() => {
                              form.validateFields(['concurrency', 'num_requests']);
                            }, 0);
                          }}
                        />
                      </Form.Item>
                    </Col>
                    <Col flex="1">
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
                              
                              // Cross-field validation
                              const crossFieldError = validateFieldCount();
                              if (crossFieldError) {
                                return Promise.reject(new Error(crossFieldError));
                              }
                              
                              return Promise.resolve();
                            }
                          }
                        ]}
                        style={{ marginBottom: 16 }}
                      >
                        <Input
                          placeholder="20, 100, 200"
                          style={{ width: '100%' }}
                          onChange={() => {
                            // Trigger validation for both fields when either changes
                            setTimeout(() => {
                              form.validateFields(['concurrency', 'num_requests']);
                            }, 0);
                          }}
                        />
                      </Form.Item>
                    </Col>
                  </Row>

                  {datasetType === 'custom' && (
                    <Row gutter={16}>
                      <Col span={24}>
                        <Form.Item
                          name="dataset_path"
                          label="数据集路径"
                          rules={[{ required: true, message: '请输入数据集路径' }]}
                          extra="请输入自定义数据集的完整路径"
                          style={{ marginBottom: 16 }}
                        >
                          <Input 
                            placeholder="/path/to/your/dataset"
                            prefix={<LinkOutlined />}
                          />
                        </Form.Item>
                      </Col>
                    </Row>
                  )}
                </>
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
                    extra="请输入准确的模型名称，如: gpt-3.5-turbo, claude-3-sonnet-20240229, Qwen2.5-VL-7B-Instruct"
                  >
                    <Input 
                      placeholder="gpt-3.5-turbo"
                      prefix={<RocketOutlined />}
                      onChange={(e) => handleManualModelNameChange(e.target.value)}
                    />
                  </Form.Item>
                  
                  {/* Main configuration row for manual mode */}
                  <Row gutter={8}>
                    <Col span={6}>
                      <Form.Item
                        name="deployment_method"
                        label="部署方式"
                        rules={[{ required: true, message: '请选择部署方式' }]}
                        initialValue="EC2"
                        style={{ marginBottom: 16 }}
                      >
                        <Select placeholder="选择部署方式">
                          <Option value="SageMaker Endpoint">Endpoint</Option>
                          <Option value="SageMaker HyperPod">HyperPod</Option>
                          <Option value="EKS">EKS</Option>
                          <Option value="EC2">EC2</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item
                        name="dataset"
                        label="数据集"
                        rules={[{ required: true, message: '请选择数据集' }]}
                        initialValue="random"
                        style={{ marginBottom: 16 }}
                      >
                        <Select 
                          placeholder="选择数据集"
                          onChange={(value) => {
                            setDatasetType(value);
                            // Force form to re-render to update conditional validation
                            setTimeout(() => {
                              form.validateFields(['input_tokens', 'output_tokens', 'image_width', 'image_height', 'image_num']);
                            }, 0);
                          }}
                        >
                          <Option value="random">random</Option>
                          <Option value="random_vl">random_vl</Option>
                          <Option value="openqa">openqa</Option>
                          <Option value="longalpaca">longalpaca</Option>
                          <Option value="flickr8k">flickr8k</Option>
                          <Option value="custom">custom</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={6}>
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
                              
                              // Cross-field validation
                              const crossFieldError = validateFieldCount();
                              if (crossFieldError) {
                                return Promise.reject(new Error(crossFieldError));
                              }
                              
                              return Promise.resolve();
                            }
                          }
                        ]}
                        style={{ marginBottom: 16 }}
                      >
                        <Input
                          placeholder="1, 5, 10"
                          style={{ width: '100%' }}
                          onChange={() => {
                            // Trigger validation for both fields when either changes
                            setTimeout(() => {
                              form.validateFields(['concurrency', 'num_requests']);
                            }, 0);
                          }}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item
                        name="num_requests"
                        label="请求总数"
                        rules={[
                          { required: true, message: '请输入请求总数' },
                          {
                            validator: (_, value) => {
                              if (!value) return Promise.reject(new Error('请求总数'));
                              
                              // Parse comma-separated values
                              const numbers = value.split(',').map(v => v.trim()).filter(v => v);
                              const invalidNumbers = numbers.filter(n => isNaN(n) || parseInt(n) <= 0);
                              
                              if (invalidNumbers.length > 0) {
                                return Promise.reject(new Error('请输入有效的正整数，用逗号分隔'));
                              }
                              
                              // Cross-field validation
                              const crossFieldError = validateFieldCount();
                              if (crossFieldError) {
                                return Promise.reject(new Error(crossFieldError));
                              }
                              
                              return Promise.resolve();
                            }
                          }
                        ]}
                        style={{ marginBottom: 16 }}
                      >
                        <Input
                          placeholder="20, 100, 200"
                          style={{ width: '100%' }}
                          onChange={() => {
                            // Trigger validation for both fields when either changes
                            setTimeout(() => {
                              form.validateFields(['concurrency', 'num_requests']);
                            }, 0);
                          }}
                        />
                      </Form.Item>
                    </Col>
                  </Row>

                  {datasetType === 'custom' && (
                    <Form.Item
                      name="dataset_path"
                      label="数据集路径"
                      rules={[{ required: true, message: '请输入数据集路径' }]}
                      extra="请输入自定义数据集的完整路径"
                    >
                      <Input 
                        placeholder="/path/to/your/dataset"
                        prefix={<LinkOutlined />}
                      />
                    </Form.Item>
                  )}
                  
                  {/* Manual deployment configuration */}
                  <Row gutter={8} justify="space-between" style={{ marginBottom: 16 }}>
                    <Col flex="1">
                      <Form.Item
                        name="instance_type"
                        label="实例类型"
                        rules={[{ required: true, message: '请选择实例类型' }]}
                        style={{ marginBottom: 0 }}
                      >
                        <Select placeholder="选择实例类型">
                          <Option value="g5.xlarge">g5.xlarge</Option>
                          <Option value="g5.2xlarge">g5.2xlarge</Option>
                          <Option value="g5.4xlarge">g5.4xlarge</Option>
                          <Option value="g5.12xlarge">g5.12xlarge</Option>
                          <Option value="g5.24xlarge">g5.24xlarge</Option>
                          <Option value="g5.48xlarge">g5.48xlarge</Option>
                          <Option value="g6e.xlarge">g6e.xlarge</Option>
                          <Option value="g6e.4xlarge">g6e.4xlarge</Option>
                          <Option value="g6e.12xlarge">g6e.12xlarge</Option>
                          <Option value="p4d.24xlarge">p4d.24xlarge</Option>
                          <Option value="p4de.24xlarge">p4de.24xlarge</Option>
                          <Option value="p5.48xlarge">p5.48xlarge</Option>
                          <Option value="p5e.48xlarge">p5e.48xlarge</Option>
                          <Option value="p5en.48xlarge">p5en.48xlarge</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col flex="1">
                      <Form.Item
                        name="framework"
                        label="推理框架"
                        rules={[{ required: true, message: '请选择推理框架' }]}
                        style={{ marginBottom: 0 }}
                      >
                        <Select placeholder="选择推理框架">
                          <Option value="vllm">vLLM</Option>
                          <Option value="sglang">SGLang</Option>
                          <Option value="tgi">TGI (Text Generation Inference)</Option>
                          <Option value="transformers">Transformers</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col flex="1">
                      <Form.Item
                        name="tp_size"
                        label="张量并行 (TP Size)"
                        rules={[{ required: true, message: '请输入张量并行数' }]}
                        style={{ marginBottom: 0 }}
                      >
                        <InputNumber
                          min={1}
                          max={8}
                          placeholder="1"
                          style={{ width: '100%' }}
                        />
                      </Form.Item>
                    </Col>
                    <Col flex="1">
                      <Form.Item
                        name="dp_size"
                        label="数据并行 (DP Size)"
                        rules={[{ required: true, message: '请输入数据并行数' }]}
                        style={{ marginBottom: 0 }}
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

              {/* Token and VLM Parameters */}
              <Row gutter={8} justify="space-between" style={{ marginBottom: 16 }}>
                <Col flex="1">
                  <Form.Item
                    name="input_tokens"
                    label="输入Token"
                    rules={shouldEnableTokenParams() ? [{ required: true, message: '请输入Token数量' }] : []}
                    style={{ marginBottom: 0 }}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="32"
                      min={1}
                      max={4000}
                      disabled={!shouldEnableTokenParams()}
                    />
                  </Form.Item>
                </Col>
                <Col flex="1">
                  <Form.Item
                    name="output_tokens"
                    label="输出Token"
                    rules={shouldEnableTokenParams() ? [{ required: true, message: '请输入Token数量' }] : []}
                    style={{ marginBottom: 0 }}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="32"
                      min={1}
                      max={4000}
                      disabled={!shouldEnableTokenParams()}
                    />
                  </Form.Item>
                </Col>
                <Col flex="1">
                  <Form.Item
                    name="image_width"
                    label="图像宽度"
                    rules={shouldEnableImageParams() ? [{ required: true, message: '请输入图像宽度' }] : []}
                    initialValue={512}
                    style={{ marginBottom: 0 }}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="512"
                      min={64}
                      max={2048}
                      step={64}
                      disabled={!shouldEnableImageParams()}
                    />
                  </Form.Item>
                </Col>
                <Col flex="1">
                  <Form.Item
                    name="image_height"
                    label="图像高度"
                    rules={shouldEnableImageParams() ? [{ required: true, message: '请输入图像高度' }] : []}
                    initialValue={512}
                    style={{ marginBottom: 0 }}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="512"
                      min={64}
                      max={2048}
                      step={64}
                      disabled={!shouldEnableImageParams()}
                    />
                  </Form.Item>
                </Col>
                <Col flex="1">
                  <Form.Item
                    name="image_num"
                    label="图像数量"
                    rules={shouldEnableImageParams() ? [{ required: true, message: '请输入图像数量' }] : []}
                    initialValue={1}
                    style={{ marginBottom: 0 }}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="1"
                      min={1}
                      max={10}
                      disabled={!shouldEnableImageParams()}
                    />
                  </Form.Item>
                </Col>
              </Row>
              
              {/* Parameter enablement info */}
              <div style={{ marginBottom: '16px' }}>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  Token参数仅在LLM模型+random数据集或VLM模型+random_vl数据集时启用；
                  图像参数仅在VLM模型+random_vl数据集时启用
                </Text>
              </div>

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
        <Col span={24}>
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