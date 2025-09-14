import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Row,
  Col,
  Spin,
  Alert,
  Button,
  Typography,
  Checkbox,
  Space,
  Tag,
  Tree,
  Divider,
  Empty,
  message,
  Popconfirm
} from 'antd';
import { Line } from '@ant-design/plots';
import {
  ReloadOutlined,
  BarChartOutlined,
  LineChartOutlined,
  DashboardOutlined,
  FolderOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  DownloadOutlined,
  DeleteOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;

// API base URL - connect to our Flask backend
const API_BASE = process.env.REACT_APP_API_BASE || '';

// AWS Instance pricing per hour (USD) - on-demand pricing
const INSTANCE_PRICING = {
  'g5.xlarge': 1.006,
  'g5.2xlarge': 1.212,
  'g5.4xlarge': 1.624,
  'g5.8xlarge': 2.472,
  'g5.12xlarge': 4.944,
  'g5.16xlarge': 6.592,
  'g5.24xlarge': 9.888,
  'g5.48xlarge': 19.776,
  'p4d.24xlarge': 32.7726,
  'p4de.24xlarge': 40.9656,
  'p5.48xlarge': 98.32,
  // Default fallback for unknown instances
  'default': 2.0
};

const VisualizationPage = () => {
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [deleting, setDeleting] = useState({});
  const [error, setError] = useState(null);
  const [resultsTree, setResultsTree] = useState([]);
  const [expandedKeys, setExpandedKeys] = useState([]);
  const [chartKey, setChartKey] = useState(0); // Force chart re-render
  
  // Load visualization state from localStorage
  const [selectedResults, setSelectedResults] = useState(() => {
    try {
      const saved = localStorage.getItem('visualization_selectedResults');
      return saved ? JSON.parse(saved) : [];
    } catch (error) {
      console.error('Failed to load selected results from localStorage:', error);
      return [];
    }
  });
  
  const [resultData, setResultData] = useState(() => {
    try {
      const saved = localStorage.getItem('visualization_resultData');
      return saved ? JSON.parse(saved) : {};
    } catch (error) {
      console.error('Failed to load result data from localStorage:', error);
      return {};
    }
  });

  // Clean up stale selected results that no longer exist in the current tree structure
  const cleanupStaleSelectedResults = (treeStructure) => {
    // Get all valid session keys from the current tree structure
    const getAllValidKeys = (nodes) => {
      const validKeys = [];
      
      const traverse = (nodeList) => {
        for (const node of nodeList) {
          if (node.children) {
            traverse(node.children);
          } else if (node.sessions) {
            // This is a leaf node with sessions
            node.sessions.forEach(session => {
              validKeys.push(session.key);
            });
          }
        }
      };
      
      traverse(nodes);
      return new Set(validKeys);
    };
    
    const validKeys = getAllValidKeys(treeStructure);
    console.log('Valid keys from current tree:', Array.from(validKeys));
    console.log('Current selectedResults:', selectedResults);
    
    // Filter out any selected results that don't exist in the current tree
    const cleanedResults = selectedResults.filter(key => validKeys.has(key));
    
    if (cleanedResults.length !== selectedResults.length) {
      console.log(`Cleaning up stale selectedResults: ${selectedResults.length} -> ${cleanedResults.length}`);
      setSelectedResults(cleanedResults);
      setChartKey(prev => prev + 1); // Force chart re-render
      
      // Also clean up resultData
      setResultData(prev => {
        const cleanedData = {};
        cleanedResults.forEach(key => {
          if (prev[key]) {
            cleanedData[key] = prev[key];
          }
        });
        return cleanedData;
      });
      
      // Update localStorage
      localStorage.setItem('visualization_selectedResults', JSON.stringify(cleanedResults));
      localStorage.setItem('visualization_resultData', JSON.stringify({})); // Clear stale result data
      if (cleanedResults.length < selectedResults.length) {
        message.info(`Cleaned up ${selectedResults.length - cleanedResults.length} outdated selections due to structure changes`);
      }
    }
  };

  // Fetch all results from outputs directory
  const fetchResultsStructure = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/api/results/structure`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setResultsTree(data.structure || []);
      
      // Clean up stale selectedResults that no longer exist in the tree
      cleanupStaleSelectedResults(data.structure || []);
    } catch (err) {
      setError(`Failed to fetch results structure: ${err.message}`);
      message.error(`Failed to fetch results: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [selectedResults]);

  // Fetch specific result data
  const fetchResultData = async (resultPath) => {
    try {
      const response = await fetch(`${API_BASE}/api/results/data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ result_path: resultPath }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      return data;
    } catch (err) {
      message.error(`Failed to fetch result data: ${err.message}`);
      return null;
    }
  };

  // Handle result selection/deselection
  const handleResultCheck = async (resultKey, checked) => {
    if (checked) {
      // Add to selected results
      const resultInfo = findResultByKey(resultsTree, resultKey);
      if (resultInfo) {
        setSelectedResults(prev => [...prev, resultKey]);
        setChartKey(prev => prev + 1); // Force chart re-render
        
        // Fetch data for this result
        const data = await fetchResultData(resultInfo.path);
        if (data) {
          setResultData(prev => ({
            ...prev,
            [resultKey]: {
              ...resultInfo,
              data: data
            }
          }));
        }
      }
    } else {
      // Remove from selected results
      setSelectedResults(prev => prev.filter(key => key !== resultKey));
      setChartKey(prev => prev + 1); // Force chart re-render
      setResultData(prev => {
        const newData = { ...prev };
        delete newData[resultKey];
        return newData;
      });
    }
  };

  // Handle checking all sessions in a group (model or instance_framework_dataset level)
  const handleGroupCheckAll = async (nodeKey, checked) => {
    const allSessionKeys = getAllSessionKeysInNode(resultsTree, nodeKey);
    
    if (checked) {
      // Add all sessions in this group
      const newSelectedResults = [...selectedResults];
      const newResultData = { ...resultData };
      
      for (const sessionKey of allSessionKeys) {
        if (!selectedResults.includes(sessionKey)) {
          newSelectedResults.push(sessionKey);
          
          // Fetch data for each session
          const resultInfo = findResultByKey(resultsTree, sessionKey);
          if (resultInfo) {
            const data = await fetchResultData(resultInfo.path);
            if (data) {
              newResultData[sessionKey] = {
                ...resultInfo,
                data: data
              };
            }
          }
        }
      }
      
      setSelectedResults(newSelectedResults);
      setChartKey(prev => prev + 1); // Force chart re-render
      setResultData(newResultData);
    } else {
      // Remove all sessions in this group
      setSelectedResults(prev => prev.filter(key => !allSessionKeys.includes(key)));
      setChartKey(prev => prev + 1); // Force chart re-render
      setResultData(prev => {
        const newData = { ...prev };
        allSessionKeys.forEach(key => {
          delete newData[key];
        });
        return newData;
      });
    }
  };

  // Get all session keys within a node (recursively)
  const getAllSessionKeysInNode = (tree, nodeKey) => {
    const sessionKeys = [];
    
    const searchNode = (nodes) => {
      for (const node of nodes) {
        if (node.key === nodeKey) {
          // Found the target node, collect all sessions underneath it
          collectAllSessions(node, sessionKeys);
          return sessionKeys;
        } else if (node.children) {
          // Continue searching in children
          const result = searchNode(node.children);
          if (result.length > 0) return result;
        }
      }
      return sessionKeys;
    };
    
    const collectAllSessions = (node, keys) => {
      if (node.sessions) {
        // This node has sessions directly
        node.sessions.forEach(session => {
          keys.push(session.key);
        });
      }
      if (node.children) {
        // Recurse into children
        node.children.forEach(child => {
          collectAllSessions(child, keys);
        });
      }
    };
    
    return searchNode(tree);
  };

  // Find result by key in the hierarchical tree structure
  const findResultByKey = (tree, targetKey) => {
    const searchNode = (nodes) => {
      for (const node of nodes) {
        if (node.children) {
          // This is a parent node, search its children
          const result = searchNode(node.children);
          if (result) return result;
        } else if (node.sessions) {
          // This is a leaf node with sessions
          for (const session of node.sessions) {
            if (session.key === targetKey) {
              return session;
            }
          }
        }
      }
      return null;
    };
    
    return searchNode(tree);
  };

  // Delete a session
  const handleDeleteSession = async (sessionId, sessionKey) => {
    try {
      setDeleting(prev => ({ ...prev, [sessionId]: true }));
      
      const response = await fetch(`${API_BASE}/api/stress-test/delete/${sessionId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.status === 'success') {
        message.success(`Session ${sessionId} deleted successfully`);
        
        // Remove from selected results if it was selected
        setSelectedResults(prev => prev.filter(key => key !== sessionKey));
        setChartKey(prev => prev + 1); // Force chart re-render
        
        // Remove from result data
        setResultData(prev => {
          const newData = { ...prev };
          delete newData[sessionKey];
          return newData;
        });
        
        // Refresh the results tree
        fetchResultsStructure();
      } else {
        throw new Error(result.message || 'Failed to delete session');
      }
    } catch (error) {
      console.error('Delete error:', error);
      message.error(`Failed to delete session: ${error.message}`);
    } finally {
      setDeleting(prev => ({ ...prev, [sessionId]: false }));
    }
  };


  // Prepare summary chart data (metrics vs concurrency) with styling info
  const prepareSummaryChartData = () => {
    const chartData = [];
    
    // Create stable style mapping first
    const colors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16', '#a0d911', '#2f54eb'];
    const shapes = ['circle', 'square', 'diamond', 'triangle', 'triangle-down', 'hexagon', 'bowtie', 'cross', 'tick', 'plus'];
    const dashPatterns = [
      [0], // solid
      [4, 4], // dashed
      [2, 2], // dotted
      [8, 4, 2, 4], // dash-dot
      [8, 4, 2, 4, 2, 4], // dash-dot-dot
      [12, 4], // long dash
      [2, 6], // sparse dot
      [6, 2, 2, 2], // dash-dot short
      [10, 2], // long dash short
      [4, 2, 4, 6] // complex pattern
    ];
    
    // Get unique sessions from ONLY selected results for consistent indexing
    const selectedResultData = selectedResults.map(key => resultData[key]).filter(Boolean);
    const uniqueSessions = [...new Set(selectedResultData.map(r => `${r.model}_${r.deployment_method || 'emd'}_${r.instance_type}_${r.framework}_${r.session_id}`))].sort();
    console.log('Unique sessions for styling (selected only):', uniqueSessions);
    
    // Process only selected results
    selectedResults.forEach(key => {
      const result = resultData[key];
      if (!result) return;
      const performanceData = result.data?.performance_data || [];
      const modelLabel = `${result.model}_${result.deployment_method || 'emd'}_${result.instance_type}_${result.framework}_${result.session_id}`;
      
      // Get style index for this session
      const styleIndex = uniqueSessions.indexOf(modelLabel);
      const sessionColor = colors[styleIndex % colors.length];
      const sessionShape = shapes[styleIndex % shapes.length];
      const sessionDashPattern = dashPatterns[styleIndex % dashPatterns.length];
      
      console.log(`Session ${modelLabel} gets index ${styleIndex}, color ${sessionColor}, shape ${sessionShape}`);
      
      if (performanceData && Array.isArray(performanceData)) {
        // Process each concurrency level from the CSV data
        performanceData.forEach(row => {
          const concurrency = row.Concurrency || 0;
          
          // Calculate output pricing per million tokens
          const outputThroughput = row.Gen_Throughput_tok_s || 0;
          const instanceType = result.instance_type || 'default';
          const hourlyPrice = INSTANCE_PRICING[instanceType] || INSTANCE_PRICING['default'];

          // Calculate cost: time to generate 1M tokens (hours) * hourly price
          const timeForMillionTokensHours = outputThroughput > 0 ? (1000000 / outputThroughput) / 3600 : 0;
          const outputPricingPerMillionTokens = timeForMillionTokensHours * hourlyPrice;

          // Add data points for the 8 specific metrics requested
          const metrics = [
            { name: 'Request throughput (req/s)', value: row.RPS_req_s },
            { name: 'Output token throughput (tok/s)', value: row.Gen_Throughput_tok_s },
            { name: 'Total token throughput (tok/s)', value: row.Total_Throughput_tok_s },
            { name: 'Average latency (s)', value: row.Avg_Latency_s },
            { name: 'Average time to first token (s)', value: row.Avg_TTFT_s },
            { name: 'Average time per output token (s)', value: row.Avg_TPOT_s },
            { name: 'Average inter-token latency (s)', value: row.Avg_ITL_s },
            { name: 'Output pricing per million tokens ($)', value: outputPricingPerMillionTokens }
          ];
          
          metrics.forEach(metric => {
            console.log(`Processing metric ${metric.name}: value=${metric.value}, type=${typeof metric.value}`);
            if (typeof metric.value === 'number' && !isNaN(metric.value)) {
              const dataPoint = {
                concurrency,
                metric: metric.name,
                yValue: metric.value,
                modelLabel,
                session: result.session_id,
                // Add styling info directly to data points
                seriesColor: sessionColor,
                seriesShape: sessionShape,
                seriesDashPattern: sessionDashPattern,
                seriesIndex: styleIndex,
                // Add color field for the chart library
                color: sessionColor,
                // Add shape field for markers
                shape: sessionShape
              };
              chartData.push(dataPoint);
              console.log(`Added datapoint: ${modelLabel}, metric: ${metric.name}, yValue: ${metric.value}, concurrency: ${concurrency}`);
            } else {
              console.log(`Skipping invalid metric ${metric.name}: value=${metric.value}, type=${typeof metric.value}`);
            }
          });
        });
      }
    });
    
    return chartData;
  };




  // Get metric unit for display
  const getMetricUnit = (metric) => {
    if (metric === 'Request throughput (req/s)') {
      return 'req/s';
    }
    if (metric === 'Output token throughput (tok/s)' || metric === 'Total token throughput (tok/s)') {
      return 'tok/s';
    }
    if (metric === 'Average latency (s)' || metric === 'Average time to first token (s)' || metric === 'Average time per output token (s)' || metric === 'Average inter-token latency (s)') {
      return 'seconds';
    }
    if (metric === 'Output pricing per million tokens ($)') {
      return 'USD per 1M tokens';
    }
    return '';
  };

  // Save visualization state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('visualization_selectedResults', JSON.stringify(selectedResults));
    } catch (error) {
      console.error('Failed to save selected results to localStorage:', error);
    }
  }, [selectedResults]);

  useEffect(() => {
    try {
      localStorage.setItem('visualization_resultData', JSON.stringify(resultData));
    } catch (error) {
      console.error('Failed to save result data to localStorage:', error);
    }
  }, [resultData]);

  // Download report as HTML
  const downloadReport = async () => {
    if (selectedResults.length === 0) {
      message.warning('请先选择要导出的结果');
      return;
    }

    setDownloading(true);

    try {
      message.loading('正在生成HTML报告...', 0);

      const timestamp = new Date().toLocaleString();

      // Prepare chart data for HTML generation
      const chartData = prepareSummaryChartData();
      const allowedMetrics = [
        'Request throughput (req/s)',
        'Output token throughput (tok/s)',
        'Total token throughput (tok/s)',
        'Average latency (s)',
        'Average time to first token (s)',
        'Average time per output token (s)',
        'Average inter-token latency (s)',
        'Output pricing per million tokens ($)'
      ];

      // Group chart data by metrics
      const metricGroups = chartData.reduce((acc, item) => {
        if (allowedMetrics.includes(item.metric)) {
          if (!acc[item.metric]) {
            acc[item.metric] = [];
          }
          acc[item.metric].push(item);
        }
        return acc;
      }, {});

      // Generate performance tables HTML
      let tablesHtml = '';
      for (const resultKey of selectedResults) {
        const result = resultData[resultKey];
        if (!result || !result.data?.performance_data) continue;

        const performanceData = result.data.performance_data;

        tablesHtml += `
          <h3>📊 ${result.model} - ${result.session_id}</h3>
          <table class="performance-table">
            <thead>
              <tr>
                <th>Concurrency</th>
                <th>RPS</th>
                <th>Gen Throughput</th>
                <th>Total Throughput</th>
                <th>Avg Latency</th>
                <th>Avg TTFT</th>
                <th>Avg TPOT</th>
                <th>Avg ITL</th>
                <th>Cost/1M$ Tokens</th>
              </tr>
            </thead>
            <tbody>
              ${performanceData.map(row => {
                const outputThroughput = row.Gen_Throughput_tok_s || 0;
                const instanceType = result.instance_type || 'default';
                const hourlyPrice = INSTANCE_PRICING[instanceType] || INSTANCE_PRICING['default'];
                const timeForMillionTokensHours = outputThroughput > 0 ? (1000000 / outputThroughput) / 3600 : 0;
                const outputPricingPerMillionTokens = timeForMillionTokensHours * hourlyPrice;

                return `
                  <tr>
                    <td>${row.Concurrency || 0}</td>
                    <td>${(row.RPS_req_s || 0).toFixed(2)}</td>
                    <td>${(row.Gen_Throughput_tok_s || 0).toFixed(2)}</td>
                    <td>${(row.Total_Throughput_tok_s || 0).toFixed(2)}</td>
                    <td>${(row.Avg_Latency_s || 0).toFixed(3)}</td>
                    <td>${(row.Avg_TTFT_s || 0).toFixed(3)}</td>
                    <td>${(row.Avg_TPOT_s || 0).toFixed(4)}</td>
                    <td>${(row.Avg_ITL_s || row.Avg_TPOT_s || 0).toFixed(4)}</td>
                    <td>$${outputPricingPerMillionTokens.toFixed(3)}</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        `;
      }

      // Generate complete HTML
      const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Benchmark Results Visualization Report</title>
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
        .results-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .result-card {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
        }
        .result-title {
            font-weight: bold;
            font-size: 16px;
            color: #1890ff;
            margin-bottom: 10px;
        }
        .result-detail {
            margin: 5px 0;
            font-size: 14px;
        }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 30px;
            margin: 30px 0;
        }
        .chart-container {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
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
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Benchmark Results Visualization Report</h1>
        <div class="timestamp">Generated on: ${timestamp}</div>

        <h2>📊 Selected Results Summary</h2>
        <div class="results-summary">
            ${selectedResults.map((resultKey, index) => {
              const result = resultData[resultKey];
              if (!result) return '';
              return `
                <div class="result-card">
                    <div class="result-title">${index + 1}. ${result.model} - ${result.session_id}</div>
                    <div class="result-detail"><strong>Deployment:</strong> ${result.deployment_method || 'emd'}</div>
                    <div class="result-detail"><strong>Instance:</strong> ${result.instance_type}</div>
                    <div class="result-detail"><strong>Framework:</strong> ${result.framework}</div>
                    <div class="result-detail"><strong>Dataset:</strong> ${result.dataset || 'N/A'}</div>
                    <div class="result-detail"><strong>Tokens:</strong> ${result.tokens_desc || 'N/A'}</div>
                </div>
              `;
            }).join('')}
        </div>

        <h2>📈 Interactive Performance Charts</h2>
        <div class="charts-grid">
            ${allowedMetrics.filter(metric => metricGroups[metric]).map(metric => {
              const data = metricGroups[metric];
              const uniqueSeries = [...new Set(data.map(d => d.modelLabel))].sort();

              // Prepare data for Plotly
              const traces = uniqueSeries.map((series, index) => {
                const seriesData = data.filter(d => d.modelLabel === series).sort((a, b) => a.concurrency - b.concurrency);
                const colors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16'];

                return {
                  x: seriesData.map(d => d.concurrency),
                  y: seriesData.map(d => d.yValue),
                  type: 'scatter',
                  mode: 'lines+markers',
                  name: series,
                  line: {
                    color: colors[index % colors.length],
                    width: 3
                  },
                  marker: {
                    size: 8,
                    color: colors[index % colors.length]
                  },
                  hovertemplate: '<b>%{fullData.name}</b><br>' +
                                '%{y}<br>' +
                                '<extra></extra>'
                };
              });

              return `
                <div class="chart-container">
                    <div class="chart-title">${metric}</div>
                    <div id="chart-${metric.replace(/[^a-zA-Z0-9]/g, '')}" style="height: 400px;"></div>
                    <script>
                        Plotly.newPlot('chart-${metric.replace(/[^a-zA-Z0-9]/g, '')}', ${JSON.stringify(traces)}, {
                            title: false,
                            xaxis: { title: 'Concurrency Level' },
                            yaxis: { title: '${getMetricUnit(metric)}' },
                            hovermode: 'x unified',
                            showlegend: true,
                            legend: { orientation: 'h', y: -0.2 },
                            margin: { t: 20, r: 20, b: 80, l: 80 }
                        }, {responsive: true});
                    </script>
                </div>
              `;
            }).join('')}
        </div>

        <h2>📋 Performance Metrics Tables</h2>
        ${tablesHtml}
    </div>
</body>
</html>`;

      // Create blob and download HTML file directly
      const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `benchmark-visualization-report-${new Date().toISOString().slice(0, 10)}.html`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      message.destroy();
      message.success('HTML报告已生成并下载');

    } catch (error) {
      message.destroy();
      console.error('Error generating HTML report:', error);
      message.error('生成HTML报告时出现错误');
    } finally {
      setDownloading(false);
    }
  };

  // Render hierarchical tree structure with checkboxes
  const renderResultsTree = () => {
    if (!resultsTree || resultsTree.length === 0) {
      return <Empty description="No results found" />;
    }

    // Convert hierarchical structure to tree data for Tree component
    const convertToTreeData = (nodes) => {
      return nodes.map(node => {
        if (node.children) {
          // This is a parent node (model or instance_framework_dataset)
          const totalSessions = countTotalSessions(node.children);
          const allSessionKeys = getAllSessionKeysInNode([node], node.key);
          const selectedCount = allSessionKeys.filter(key => selectedResults.includes(key)).length;
          const allSelected = selectedCount === totalSessions && totalSessions > 0;
          const someSelected = selectedCount > 0 && selectedCount < totalSessions;

          return {
            title: (
              <Space>
                <FolderOutlined />
                <Text strong>{node.title}</Text>
                <Tag color="blue">{totalSessions} sessions</Tag>
                {totalSessions > 0 && (
                  <Checkbox
                    checked={allSelected}
                    indeterminate={someSelected}
                    onChange={(e) => handleGroupCheckAll(node.key, e.target.checked)}
                    onClick={(e) => e.stopPropagation()}
                  />
                )}
                {selectedCount > 0 && (
                  <Tag color="green">{selectedCount} selected</Tag>
                )}
              </Space>
            ),
            key: node.key,
            children: convertToTreeData(node.children),
            selectable: false
          };
        } else if (node.sessions) {
          // This is a leaf node (input_output_tokens level) with sessions
          const allSessionKeys = node.sessions.map(s => s.key);
          const selectedCount = allSessionKeys.filter(key => selectedResults.includes(key)).length;
          const allSelected = selectedCount === node.sessions.length && node.sessions.length > 0;
          const someSelected = selectedCount > 0 && selectedCount < node.sessions.length;

          return {
            title: (
              <Space>
                <FileTextOutlined />
                <Text>{node.title}</Text>
                <Tag color="green">{node.sessions.length} sessions</Tag>
                {node.sessions.length > 0 && (
                  <Checkbox
                    checked={allSelected}
                    indeterminate={someSelected}
                    onChange={(e) => handleGroupCheckAll(node.key, e.target.checked)}
                    onClick={(e) => e.stopPropagation()}
                  />
                )}
                {selectedCount > 0 && (
                  <Tag color="orange">{selectedCount} selected</Tag>
                )}
              </Space>
            ),
            key: node.key,
            children: node.sessions.map(session => ({
              title: (
                <Card size="small" style={{ marginBottom: 4, width: '100%' }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                      <Space>
                        <Checkbox
                          checked={selectedResults.includes(session.key)}
                          onChange={(e) => handleResultCheck(session.key, e.target.checked)}
                          onClick={(e) => e.stopPropagation()}
                        />
                        <Text strong>{session.session_id}</Text>
                        {selectedResults.includes(session.key) && (
                          <CheckCircleOutlined style={{ color: '#52c41a' }} />
                        )}
                      </Space>
                      <Popconfirm
                        title="Delete Session"
                        description="Are you sure you want to delete this session? This will permanently remove all session files from disk."
                        onConfirm={() => handleDeleteSession(session.session_id, session.key)}
                        okText="Yes, Delete"
                        cancelText="Cancel"
                        okType="danger"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          loading={deleting[session.session_id]}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Popconfirm>
                    </Space>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {new Date(session.timestamp).toLocaleString()}
                    </Text>
                    <Space wrap size="small">
                      <Tag size="small">Concurrency: {(() => {
                        console.log('Available Results - Session object:', session);
                        console.log('Available Results - Concurrency value:', session.concurrency, 'Type:', typeof session.concurrency);
                        const val = String(session.concurrency);
                        if (/^\d+$/.test(val)) {
                          try {
                            const num = parseInt(val, 10);
                            console.log('Available Results - Parsed concurrency:', num);
                            return num.toLocaleString();
                          } catch (e) {
                            console.error('Available Results - Error parsing concurrency:', e);
                          }
                        }
                        return val;
                      })()}</Tag>
                      <Tag size="small">Requests: {(() => {
                        console.log('Available Results - Requests value:', session.total_requests, 'Type:', typeof session.total_requests);
                        const val = String(session.total_requests);
                        if (/^\d+$/.test(val)) {
                          try {
                            const num = parseInt(val, 10);
                            console.log('Available Results - Parsed requests:', num);
                            return num.toLocaleString();
                          } catch (e) {
                            console.error('Available Results - Error parsing requests:', e);
                          }
                        }
                        return val;
                      })()}</Tag>
                    </Space>
                  </Space>
                </Card>
              ),
              key: session.key,
              isLeaf: true,
              selectable: false,
              session: session
            })),
            selectable: false
          };
        }
        return null;
      }).filter(Boolean);
    };

    // Helper function to count total sessions in a tree
    const countTotalSessions = (nodes) => {
      let count = 0;
      for (const node of nodes) {
        if (node.children) {
          count += countTotalSessions(node.children);
        } else if (node.sessions) {
          count += node.sessions.length;
        }
      }
      return count;
    };

    const treeData = convertToTreeData(resultsTree);

    return (
      <Tree
        treeData={treeData}
        expandedKeys={expandedKeys}
        onExpand={(keys) => setExpandedKeys(keys)}
        showLine={true}
        showIcon={false}
        blockNode={true}
        style={{ width: '100%' }}
      />
    );
  };

  // Render summary charts (metrics vs concurrency)
  const renderSummaryCharts = () => {
    const chartData = prepareSummaryChartData();

    if (chartData.length === 0) {
      return <Empty description="No summary data available" />;
    }

    // Define the 8 specific metrics requested (in display order)
    const allowedMetrics = [
      'Request throughput (req/s)',
      'Output token throughput (tok/s)',
      'Total token throughput (tok/s)',
      'Average latency (s)',
      'Average time to first token (s)',
      'Average time per output token (s)',
      'Average inter-token latency (s)',
      'Output pricing per million tokens ($)'
    ];

    // Group by metric type and filter to only allowed metrics
    const metricGroups = chartData.reduce((acc, item) => {
      if (allowedMetrics.includes(item.metric)) {
        if (!acc[item.metric]) {
          acc[item.metric] = [];
        }
        acc[item.metric].push(item);
      }
      return acc;
    }, {});

    return (
      <Row gutter={[16, 16]} data-chart-row>
        {allowedMetrics.filter(metric => metricGroups[metric]).map((metric) => {
          const data = metricGroups[metric];
          console.log(`Rendering chart for metric ${metric}:`, data);
          console.log(`Sample data point for ${metric}:`, data[0]);

          // Create simple color array - the chart library expects colors in series order
          const uniqueSeries = [...new Set(data.map(d => d.modelLabel))].sort();
          const colorArray = uniqueSeries.map(series => {
            const firstDataPoint = data.find(d => d.modelLabel === series);
            return firstDataPoint.seriesColor;
          });

          console.log(`Series order for ${metric}:`, uniqueSeries);
          console.log(`Color array for ${metric}:`, colorArray);
          console.log(`Sample data points for ${metric}:`, data.slice(0, 2));

          return (
            <Col span={12} key={metric}>
              <Card title={metric} size="small">
                <div style={{ height: 300 }}>
                  <Line
                    key={`${metric}-${chartKey}`}
                    data={data}
                    xField="concurrency"
                    yField="yValue"
                    seriesField="modelLabel"
                    colorField="modelLabel"
                    smooth={true}
                    color={colorArray}
                    point={{
                      size: 20,
                      shape: 'circle',
                      style: {
                        fillOpacity: 0.8,
                        stroke: '#fff',
                        lineWidth: 2
                      }
                    }}
                    lineStyle={(datum) => {
                      const dashPatterns = [
                        undefined, // solid
                        [8, 8], // dashed
                        [2, 4], // dotted
                        [8, 4, 2, 4], // dash-dot
                        [8, 4, 2, 4, 2, 4] // dash-dot-dot
                      ];
                      const seriesIndex = uniqueSeries.indexOf(datum.modelLabel);
                      return {
                        lineWidth: 4,
                        lineDash: dashPatterns[seriesIndex % dashPatterns.length]
                      };
                    }}
                    legend={{
                      position: 'bottom'
                    }}
                    xAxis={{
                      title: {
                        text: 'Concurrency Level',
                        style: { fontSize: 12 }
                      }
                    }}
                    yAxis={{
                      title: {
                        text: getMetricUnit(metric),
                        style: { fontSize: 12 }
                      }
                    }}
                  />
              </div>
            </Card>
          </Col>
        );
        })}
      </Row>
    );
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
    fetchResultsStructure();
  }, []);

  // Add keyboard event listener for refresh
  useEffect(() => {
    document.addEventListener('keydown', handlePageRefresh);
    
    return () => {
      document.removeEventListener('keydown', handlePageRefresh);
    };
  }, [handlePageRefresh]);

  return (
    <div style={{ padding: '24px', background: '#f0f2f5', minHeight: '100vh' }}>
      <Row gutter={[16, 16]}>
        {/* Header */}
        <Col span={24}>
          <Card>
            <Row justify="space-between" align="middle">
              <Col>
                <Title level={2} style={{ margin: 0 }}>
                  <BarChartOutlined /> Benchmark Results Visualization
                </Title>
                <Text type="secondary">
                  Select benchmark results from the left panel to visualize performance metrics
                </Text>
              </Col>
              <Col>
                <Space>
                  <Button 
                    icon={<ReloadOutlined />} 
                    onClick={fetchResultsStructure}
                    loading={loading}
                  >
                    Refresh Results
                  </Button>
                  <Button 
                    type="primary"
                    icon={<DownloadOutlined />} 
                    onClick={downloadReport}
                    loading={downloading}
                    disabled={selectedResults.length === 0}
                  >
                    下载报告
                  </Button>
                </Space>
              </Col>
            </Row>
          </Card>
        </Col>

        {/* Results Tree (Left Panel) */}
        <Col span={8}>
          <Card 
            title={
              <Space>
                <FolderOutlined />
                Available Results
                {selectedResults.length > 0 && (
                  <Tag color="green">{selectedResults.length} selected</Tag>
                )}
              </Space>
            }
            style={{ height: 'calc(100vh - 200px)' }}
            styles={{ body: { height: 'calc(100vh - 280px)', overflow: 'auto' } }}
          >
            {loading ? (
              <Spin size="large" style={{ display: 'block', textAlign: 'center', marginTop: '100px' }} />
            ) : error ? (
              <Alert message="Error" description={error} type="error" showIcon />
            ) : (
              renderResultsTree()
            )}
          </Card>
        </Col>

        {/* Visualization Panel (Right Panel) */}
        <Col span={16}>
          <Card 
            title={
              <Space>
                <LineChartOutlined />
                Performance Visualization
                {selectedResults.length > 0 && (
                  <Tag color="blue">{selectedResults.length} results selected</Tag>
                )}
              </Space>
            }
            style={{ height: 'calc(100vh - 200px)' }}
            styles={{ body: { height: 'calc(100vh - 280px)', overflow: 'auto' } }}
          >
            {selectedResults.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '100px 0' }}>
                <Empty 
                  description="Select benchmark results from the left panel to view visualizations"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              </div>
            ) : (
              <Space direction="vertical" style={{ width: '100%' }} size="large">
                {/* Performance Metrics vs Concurrency */}
                <div>
                  <Title level={4}>
                    <DashboardOutlined /> Performance Metrics vs Concurrency
                  </Title>
                  <Text type="secondary">
                    RPS, Throughput, Latency metrics, Inter-token Latency, and Output Pricing per Million Tokens vs Concurrency
                  </Text>
                  <Divider />
                  {renderSummaryCharts()}
                </div>
              </Space>
            )}
          </Card>
        </Col>

        {/* Selected Results Summary */}
        {selectedResults.length > 0 && (
          <Col span={24}>
            <Card title="Selected Results Summary">
              <Row gutter={[16, 16]}>
                {selectedResults.map(resultKey => {
                  const result = resultData[resultKey];
                  if (!result) return null;
                  
                  return (
                    <Col span={6} key={resultKey}>
                      <Card size="small" style={{ textAlign: 'center' }}>
                        <Space direction="vertical">
                          <Text strong>{result.model}</Text>
                          <Text type="secondary">{result.session_id}</Text>
                          <Space wrap size="small">
                            <Tag size="small">Deployment: {result.deployment_method || 'emd'}</Tag>
                            <Tag size="small">Instance: {result.instance_type}</Tag>
                            <Tag size="small">Framework: {result.framework}</Tag>
                            <Tag size="small">TP Size: {result.tp_size || 1}</Tag>
                            <Tag size="small">Dataset: {result.dataset}</Tag>
                          </Space>
                          <Space wrap size="small">
                            <Tag size="small">Tokens: {result.tokens_desc}</Tag>
                            <Tag size="small">Concurrency: {(() => {
                              console.log('Summary Concurrency value:', result.concurrency, 'Type:', typeof result.concurrency);
                              const val = String(result.concurrency);
                              // Handle large numbers by parsing as integer
                              if (/^\d+$/.test(val)) {
                                try {
                                  const num = parseInt(val, 10);
                                  console.log('Parsed concurrency:', num);
                                  return num.toLocaleString();
                                } catch (e) {
                                  console.error('Error parsing concurrency:', e);
                                }
                              }
                              return val;
                            })()}</Tag>
                            <Tag size="small">Requests: {(() => {
                              console.log('Summary Requests value:', result.total_requests, 'Type:', typeof result.total_requests);
                              const val = String(result.total_requests);
                              // Handle large numbers by parsing as integer
                              if (/^\d+$/.test(val)) {
                                try {
                                  const num = parseInt(val, 10);
                                  console.log('Parsed requests:', num);
                                  return num.toLocaleString();
                                } catch (e) {
                                  console.error('Error parsing requests:', e);
                                }
                              }
                              return val;
                            })()}</Tag>
                          </Space>
                        </Space>
                      </Card>
                    </Col>
                  );
                })}
              </Row>
            </Card>
          </Col>
        )}
      </Row>
    </div>
  );
};

export default VisualizationPage;