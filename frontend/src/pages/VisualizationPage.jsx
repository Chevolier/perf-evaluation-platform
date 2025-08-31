import React, { useState, useEffect } from 'react';
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
  CheckCircleOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;

// API base URL - connect to our Flask backend
const API_BASE = process.env.REACT_APP_API_BASE || '';

const VisualizationPage = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [resultsTree, setResultsTree] = useState([]);
  const [selectedResults, setSelectedResults] = useState([]);
  const [resultData, setResultData] = useState({});

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
          // This is a parent node (model, instance, framework, dataset)
          return {
            title: (
              <Space>
                <FolderOutlined />
                <Text strong>{node.title}</Text>
                {node.children && (
                  <Tag color="blue">
                    {countTotalSessions(node.children)} sessions
                  </Tag>
                )}
              </Space>
            ),
            key: node.key,
            children: convertToTreeData(node.children),
            selectable: false
          };
        } else if (node.sessions) {
          // This is a leaf node (input_output_tokens level) with sessions
          return {
            title: (
              <Space>
                <FileTextOutlined />
                <Text>{node.title}</Text>
                <Tag color="green">{node.sessions.length} sessions</Tag>
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
                      <Tag size="small">Concurrency: {session.concurrency}</Tag>
                      <Tag size="small">Requests: {session.total_requests}</Tag>
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
    const uniqueSessions = [...new Set(Object.values(resultData).map(r => `${r.model}_${r.instance_type}_${r.framework}_${r.session_id}`))].sort();
    console.log('Unique sessions for styling:', uniqueSessions);
    
    Object.entries(resultData).forEach(([key, result]) => {
      const performanceData = result.data?.performance_data || [];
      const modelLabel = `${result.model}_${result.instance_type}_${result.framework}_${result.session_id}`;
      
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
            if (typeof metric.value === 'number') {
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
              console.log(`Added datapoint: ${modelLabel}, shape: ${sessionShape}, color: ${sessionColor}`);
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
      <Row gutter={[16, 16]}>
        {allowedMetrics.filter(metric => metricGroups[metric]).map((metric) => {
          const data = metricGroups[metric];
          console.log(`Rendering chart for metric ${metric}:`, data);
          
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
                      shapeField: 'shape',
                      style: {
                        stroke: '#fff',
                        lineWidth: 3,
                        fillOpacity: 0.9
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
                    yAxis={{
                      label: {
                        formatter: (value) => `${value}`
                      },
                      title: {
                        text: getMetricUnit(metric),
                        style: { fontSize: 12 }
                      }
                    }}
                    xAxis={{
                      title: {
                        text: 'Concurrency Level',
                        style: { fontSize: 12 }
                      }
                    }}
                    tooltip={{
                      formatter: (datum) => {
                        return {
                          name: datum.modelLabel,
                          value: `${datum.yValue.toFixed(4)} ${getMetricUnit(metric)}`
                        };
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

  useEffect(() => {
    fetchResultsStructure();
  }, []);

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
                <Button 
                  icon={<ReloadOutlined />} 
                  onClick={fetchResultsStructure}
                  loading={loading}
                >
                  Refresh Results
                </Button>
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
                            <Tag size="small">Instance: {result.instance_type}</Tag>
                            <Tag size="small">Framework: {result.framework}</Tag>
                            <Tag size="small">Dataset: {result.dataset}</Tag>
                          </Space>
                          <Space wrap size="small">
                            <Tag size="small">Tokens: {result.tokens_desc}</Tag>
                            <Tag size="small">Concurrency: {result.concurrency}</Tag>
                            <Tag size="small">Requests: {result.total_requests}</Tag>
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