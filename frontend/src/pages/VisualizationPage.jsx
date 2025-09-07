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
  message
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
  DownloadOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;

// API base URL - connect to our Flask backend
const API_BASE = process.env.REACT_APP_API_BASE || '';

const VisualizationPage = () => {
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);
  const [resultsTree, setResultsTree] = useState([]);
  
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

  // Fetch all results from outputs directory
  const fetchResultsStructure = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/api/results/structure`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setResultsTree(data.structure || []);
    } catch (err) {
      setError(`Failed to fetch results structure: ${err.message}`);
      message.error(`Failed to fetch results: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

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
      setResultData(newResultData);
    } else {
      // Remove all sessions in this group
      setSelectedResults(prev => prev.filter(key => !allSessionKeys.includes(key)));
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
        defaultExpandAll={false}
        showLine={true}
        showIcon={false}
        blockNode={true}
        style={{ width: '100%' }}
      />
    );
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
    
    // Get all unique sessions sorted for consistent indexing
    const uniqueSessions = [...new Set(Object.values(resultData).map(r => `${r.model}_${r.deployment_method || 'emd'}_${r.instance_type}_${r.framework}_${r.session_id}`))].sort();
    console.log('Unique sessions for styling:', uniqueSessions);
    
    Object.entries(resultData).forEach(([key, result]) => {
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
          
          // Add data points for the 6 specific metrics requested
          const metrics = [
            { name: 'Request throughput (req/s)', value: row.RPS_req_s },
            { name: 'Output token throughput (tok/s)', value: row.Gen_Throughput_tok_s },
            { name: 'Total token throughput (tok/s)', value: row.Total_Throughput_tok_s },
            { name: 'Average latency (s)', value: row.Avg_Latency_s },
            { name: 'Average time to first token (s)', value: row.Avg_TTFT_s },
            { name: 'Average time per output token (s)', value: row.Avg_TPOT_s }
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


  // Render summary charts (metrics vs concurrency)
  const renderSummaryCharts = () => {
    const chartData = prepareSummaryChartData();
    
    if (chartData.length === 0) {
      return <Empty description="No summary data available" />;
    }

    // Define the 6 specific metrics requested (in display order)
    const allowedMetrics = [
      'Request throughput (req/s)',
      'Output token throughput (tok/s)',
      'Total token throughput (tok/s)',
      'Average latency (s)',
      'Average time to first token (s)',
      'Average time per output token (s)'
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


  // Get metric unit for display
  const getMetricUnit = (metric) => {
    if (metric === 'Request throughput (req/s)') {
      return 'req/s';
    }
    if (metric === 'Output token throughput (tok/s)' || metric === 'Total token throughput (tok/s)') {
      return 'tok/s';
    }
    if (metric === 'Average latency (s)' || metric === 'Average time to first token (s)' || metric === 'Average time per output token (s)') {
      return 'seconds';
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

  // Download report as PDF
  const downloadReport = async () => {
    if (selectedResults.length === 0) {
      message.warning('请先选择要导出的结果');
      return;
    }

    setDownloading(true);
    
    try {
      // Import libraries dynamically to avoid bundle size issues
      const html2canvas = (await import('html2canvas')).default;
      const jsPDF = (await import('jspdf')).default;

      message.loading('正在生成PDF报告...', 0);

      const doc = new jsPDF('p', 'mm', 'a4');
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = 20;
      let currentY = margin;

      // Title
      doc.setFontSize(20);
      doc.setFont('helvetica', 'bold');
      doc.text('Benchmark Results Visualization Report', pageWidth / 2, currentY, { align: 'center' });
      currentY += 20;

      // Generated timestamp
      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      const timestamp = new Date().toLocaleString();
      doc.text(`Generated on: ${timestamp}`, margin, currentY);
      currentY += 15;

      // Selected results summary
      doc.setFontSize(12);
      doc.setFont('helvetica', 'bold');
      doc.text('Selected Results:', margin, currentY);
      currentY += 8;

      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      selectedResults.forEach((resultKey, index) => {
        const result = resultData[resultKey];
        if (result && currentY < pageHeight - 30) {
          const summaryText = `${index + 1}. ${result.model} - ${result.session_id} (${result.deployment_method || 'emd'}, ${result.instance_type}, ${result.framework})`;
          doc.text(summaryText, margin + 5, currentY);
          currentY += 6;
        } else if (result && currentY >= pageHeight - 30) {
          doc.addPage();
          currentY = margin;
          const summaryText = `${index + 1}. ${result.model} - ${result.session_id} (${result.deployment_method || 'emd'}, ${result.instance_type}, ${result.framework})`;
          doc.text(summaryText, margin + 5, currentY);
          currentY += 6;
        }
      });

      currentY += 10;

      // Add performance metrics tables for each selected session
      doc.setFontSize(14);
      doc.setFont('helvetica', 'bold');
      doc.text('Performance Metrics Tables', margin, currentY);
      currentY += 12;

      for (const resultKey of selectedResults) {
        const result = resultData[resultKey];
        if (result && result.data?.performance_data) {
          const performanceData = result.data.performance_data;
          
          // Check if we need a new page for the table and parameters
          const tableHeight = (performanceData.length + 4) * 6 + 80; // Estimate table height with borders + parameters
          if (currentY + tableHeight > pageHeight - margin) {
            doc.addPage();
            currentY = margin;
          }

          // Table header with background
          doc.setFontSize(14);
          doc.setFont('helvetica', 'bold');
          doc.text(`${result.model} - ${result.session_id} Performance Metrics`, margin, currentY);
          currentY += 15;

          // Fetch config data from config.json
          let configData = {};
          try {
            const configResponse = await fetch(`${API_BASE}/api/results/data`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({ result_path: result.path.replace('performance_metrics.csv', 'config.json') }),
            });
            if (configResponse.ok) {
              const configResult = await configResponse.json();
              configData = configResult || {};
            }
          } catch (error) {
            console.warn('Failed to fetch config.json:', error);
          }

          // Add key parameters table
          doc.setFontSize(10);
          doc.setFont('helvetica', 'bold');
          doc.text('Configuration Parameters', margin, currentY);
          currentY += 8;

          // Configuration table setup
          const configHeaders = ['Parameter', 'Value'];
          const configColWidths = [60, 80];
          const configTableWidth = configColWidths.reduce((sum, width) => sum + width, 0);
          const configTableStartX = margin;
          const configTableStartY = currentY;

          // Configuration parameters to display
          const configParams = [
            { label: 'Model', value: result.model || configData.model || 'N/A' },
            { label: 'Deployment Method', value: result.deployment_method || configData.deployment_method || 'emd' },
            { label: 'Instance Type', value: result.instance_type || configData.instance_type || 'N/A' },
            { label: 'Framework', value: result.framework || configData.framework || 'N/A' },
            { label: 'Dataset', value: result.dataset || configData.dataset || 'N/A' },
            { label: 'TP (Tensor Parallel)', value: result.tp?.toString() || configData.tp?.toString() || 'N/A' },
            { label: 'DP (Data Parallel)', value: result.dp?.toString() || configData.dp?.toString() || 'N/A' },
            { label: 'Input Tokens', value: result.input_tokens?.toString() || configData.input_tokens?.toString() || 'N/A' },
            { label: 'Output Tokens', value: result.output_tokens?.toString() || configData.output_tokens?.toString() || 'N/A' }
          ];

          // Draw config table header
          doc.setFillColor(240, 240, 240);
          doc.rect(configTableStartX, configTableStartY - 2, configTableWidth, 8, 'F');
          doc.setDrawColor(0, 0, 0);
          doc.rect(configTableStartX, configTableStartY - 2, configTableWidth, 8);

          // Config table column headers
          doc.setFontSize(9);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(0, 0, 0);
          let configXPos = configTableStartX + 2;
          
          configHeaders.forEach((header, i) => {
            doc.text(header, configXPos, currentY + 3);
            
            // Draw vertical lines between columns
            if (i < configHeaders.length - 1) {
              const lineX = configXPos + configColWidths[i] - 2;
              doc.line(lineX, configTableStartY - 2, lineX, configTableStartY + 6);
            }
            configXPos += configColWidths[i];
          });
          currentY += 8;

          // Config table data rows
          doc.setFont('helvetica', 'normal');
          doc.setFontSize(8);
          let configRowIndex = 0;
          
          configParams.forEach(param => {
            // Alternate row colors
            if (configRowIndex % 2 === 1) {
              doc.setFillColor(248, 248, 248);
              doc.rect(configTableStartX, currentY - 2, configTableWidth, 6, 'F');
            }

            // Draw row border
            doc.setDrawColor(0, 0, 0);
            doc.rect(configTableStartX, currentY - 2, configTableWidth, 6);

            configXPos = configTableStartX + 2;
            const configValues = [param.label, param.value];

            configValues.forEach((value, i) => {
              doc.text(String(value), configXPos, currentY + 2);
              
              // Draw vertical lines between columns
              if (i < configValues.length - 1) {
                const lineX = configXPos + configColWidths[i] - 2;
                doc.line(lineX, currentY - 2, lineX, currentY + 4);
              }
              configXPos += configColWidths[i];
            });
            currentY += 6;
            configRowIndex++;
          });

          currentY += 10;

          // Table setup
          const headers = ['Concurrency', 'RPS', 'Gen Tput', 'Total Tput', 'Avg Lat', 'Avg TTFT', 'Avg TPOT'];
          const colWidths = [20, 20, 20, 22, 20, 20, 22];
          const tableWidth = colWidths.reduce((sum, width) => sum + width, 0);
          const tableStartX = margin;
          const tableStartY = currentY;

          // Draw table border
          doc.setDrawColor(0, 0, 0);
          doc.setLineWidth(0.5);
          doc.rect(tableStartX, tableStartY - 2, tableWidth, 8); // Header background rectangle
          
          // Fill header background (light gray)
          doc.setFillColor(240, 240, 240);
          doc.rect(tableStartX, tableStartY - 2, tableWidth, 8, 'F');
          
          // Draw header border again (on top of fill)
          doc.setDrawColor(0, 0, 0);
          doc.rect(tableStartX, tableStartY - 2, tableWidth, 8);

          // Table column headers
          doc.setFontSize(8);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(0, 0, 0);
          let xPos = tableStartX + 2;
          
          headers.forEach((header, i) => {
            doc.text(header, xPos, currentY + 3);
            
            // Draw vertical lines between columns
            if (i < headers.length - 1) {
              const lineX = xPos + colWidths[i] - 2;
              doc.line(lineX, tableStartY - 2, lineX, tableStartY + 6);
            }
            xPos += colWidths[i];
          });
          currentY += 8;

          // Table data rows
          doc.setFont('helvetica', 'normal');
          let rowIndex = 0;
          
          performanceData.forEach(row => {
            // Check if we need a new page mid-table
            if (currentY > pageHeight - 35) {
              doc.addPage();
              currentY = margin;
              
              // Repeat table header on new page
              doc.setFontSize(12);
              doc.setFont('helvetica', 'bold');
              doc.text(`${result.model} - ${result.session_id} Performance Metrics (continued)`, margin, currentY);
              currentY += 12;
              
              // Repeat headers
              const newTableStartY = currentY;
              doc.setFillColor(240, 240, 240);
              doc.rect(tableStartX, newTableStartY - 2, tableWidth, 8, 'F');
              doc.setDrawColor(0, 0, 0);
              doc.rect(tableStartX, newTableStartY - 2, tableWidth, 8);
              
              doc.setFontSize(8);
              doc.setFont('helvetica', 'bold');
              xPos = tableStartX + 2;
              headers.forEach((header, i) => {
                doc.text(header, xPos, currentY + 3);
                if (i < headers.length - 1) {
                  const lineX = xPos + colWidths[i] - 2;
                  doc.line(lineX, newTableStartY - 2, lineX, newTableStartY + 6);
                }
                xPos += colWidths[i];
              });
              currentY += 8;
              doc.setFont('helvetica', 'normal');
              rowIndex = 0;
            }

            // Alternate row colors
            if (rowIndex % 2 === 1) {
              doc.setFillColor(248, 248, 248);
              doc.rect(tableStartX, currentY - 2, tableWidth, 6, 'F');
            }

            // Draw row border
            doc.setDrawColor(0, 0, 0);
            doc.rect(tableStartX, currentY - 2, tableWidth, 6);

            xPos = tableStartX + 2;
            const values = [
              row.Concurrency || 0,
              (row.RPS_req_s || 0).toFixed(2),
              (row.Gen_Throughput_tok_s || 0).toFixed(2),
              (row.Total_Throughput_tok_s || 0).toFixed(2),
              (row.Avg_Latency_s || 0).toFixed(3),
              (row.Avg_TTFT_s || 0).toFixed(3),
              (row.Avg_TPOT_s || 0).toFixed(4)
            ];

            values.forEach((value, i) => {
              doc.text(String(value), xPos, currentY + 2);
              
              // Draw vertical lines between columns
              if (i < values.length - 1) {
                const lineX = xPos + colWidths[i] - 2;
                doc.line(lineX, currentY - 2, lineX, currentY + 4);
              }
              xPos += colWidths[i];
            });
            currentY += 6;
            rowIndex++;
          });

          // Add spacing after table
          currentY += 15;
        }
      }

      // Capture charts
      const chartRows = document.querySelectorAll('[data-chart-row]');
      
      for (let i = 0; i < chartRows.length; i++) {
        const row = chartRows[i];
        
        try {
          // Check if we need a new page
          if (currentY > pageHeight - 100) {
            doc.addPage();
            currentY = margin;
          }

          const canvas = await html2canvas(row, {
            scale: 2,
            useCORS: true,
            backgroundColor: '#ffffff',
            width: row.offsetWidth,
            height: row.offsetHeight
          });

          const imgData = canvas.toDataURL('image/png');
          const imgWidth = pageWidth - (margin * 2);
          const imgHeight = (canvas.height * imgWidth) / canvas.width;

          // Check if image fits in current page
          if (currentY + imgHeight > pageHeight - margin) {
            doc.addPage();
            currentY = margin;
          }

          doc.addImage(imgData, 'PNG', margin, currentY, imgWidth, imgHeight);
          currentY += imgHeight + 10;

        } catch (error) {
          console.error(`Error capturing chart ${i}:`, error);
        }
      }

      // Save the PDF
      const filename = `benchmark-visualization-report-${new Date().toISOString().slice(0, 10)}.pdf`;
      doc.save(filename);

      message.destroy();
      message.success('PDF报告已生成并下载');

    } catch (error) {
      message.destroy();
      console.error('Error generating PDF:', error);
      message.error('生成PDF报告时出现错误');
    } finally {
      setDownloading(false);
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
                    RPS, Gen Throughput, Total Throughput, Avg Latency, Avg Time to First Token, and Avg Time per Output Token vs Concurrency
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