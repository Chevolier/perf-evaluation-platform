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
  Collapse,
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
const { Panel } = Collapse;

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

  // Find result by key in the tree structure
  const findResultByKey = (tree, targetKey) => {
    for (const model of tree) {
      for (const session of model.sessions) {
        if (session.key === targetKey) {
          return session;
        }
      }
    }
    return null;
  };

  // Render tree structure with checkboxes
  const renderResultsTree = () => {
    if (!resultsTree || resultsTree.length === 0) {
      return <Empty description="No results found" />;
    }

    return (
      <Collapse defaultActiveKey={resultsTree.map(model => model.model)} size="small">
        {resultsTree.map(model => (
          <Panel 
            header={
              <Space>
                <FolderOutlined />
                <Text strong>{model.model}</Text>
                <Tag color="blue">{model.sessions.length} sessions</Tag>
              </Space>
            }
            key={model.model}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              {model.sessions.map(session => (
                <Card key={session.key} size="small" style={{ marginBottom: 8 }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Space>
                      <Checkbox
                        checked={selectedResults.includes(session.key)}
                        onChange={(e) => handleResultCheck(session.key, e.target.checked)}
                      />
                      <FileTextOutlined />
                      <Text strong>{session.session_id}</Text>
                      {selectedResults.includes(session.key) && (
                        <CheckCircleOutlined style={{ color: '#52c41a' }} />
                      )}
                    </Space>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {new Date(session.timestamp).toLocaleString()}
                    </Text>
                    <Space wrap>
                      <Tag>Concurrency: {session.config?.stress_test_config?.concurrency || 'N/A'}</Tag>
                      <Tag>Requests: {session.config?.stress_test_config?.total_requests || 'N/A'}</Tag>
                      <Tag>Framework: {session.config?.deployment_config?.framework || 'N/A'}</Tag>
                      <Tag>Instance: {session.config?.deployment_config?.instance_type || 'N/A'}</Tag>
                    </Space>
                  </Space>
                </Card>
              ))}
            </Space>
          </Panel>
        ))}
      </Collapse>
    );
  };

  // Prepare summary chart data (metrics vs concurrency)
  const prepareSummaryChartData = () => {
    const chartData = [];
    
    Object.entries(resultData).forEach(([key, result]) => {
      const summary = result.data?.summary;
      const config = result.config;
      
      if (summary && config) {
        const concurrency = config.stress_test_config?.concurrency || 0;
        const modelLabel = `${result.model}_${result.session_id}`;
        
        // Add data points for each metric
        Object.entries(summary).forEach(([metric, value]) => {
          if (typeof value === 'number') {
            chartData.push({
              concurrency,
              metric,
              value,
              modelLabel,
              session: result.session_id
            });
          }
        });
      }
    });
    
    return chartData;
  };

  // Prepare percentile chart data
  const preparePercentileChartData = () => {
    const chartData = [];
    
    Object.entries(resultData).forEach(([key, result]) => {
      const percentiles = result.data?.percentiles;
      const modelLabel = `${result.model}_${result.session_id}`;
      
      if (percentiles && Array.isArray(percentiles)) {
        percentiles.forEach(p => {
          // Add data for each metric in percentiles
          Object.entries(p).forEach(([metric, value]) => {
            if (metric !== 'Percentiles' && typeof value === 'number') {
              chartData.push({
                percentile: p.Percentiles,
                metric,
                value,
                modelLabel,
                session: result.session_id
              });
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

    // Group by metric type
    const metricGroups = chartData.reduce((acc, item) => {
      if (!acc[item.metric]) {
        acc[item.metric] = [];
      }
      acc[item.metric].push(item);
      return acc;
    }, {});

    return (
      <Row gutter={[16, 16]}>
        {Object.entries(metricGroups).map(([metric, data]) => (
          <Col span={12} key={metric}>
            <Card title={metric} size="small">
              <div style={{ height: 250 }}>
                <Line
                  data={data}
                  xField="concurrency"
                  yField="value"
                  seriesField="modelLabel"
                  smooth={true}
                  point={{
                    size: 4,
                    shape: 'circle',
                  }}
                  tooltip={{
                    formatter: (datum) => ({
                      name: datum.modelLabel,
                      value: `${datum.value?.toFixed(4)} ${getMetricUnit(metric)}`
                    })
                  }}
                  yAxis={{
                    label: {
                      text: `${metric} ${getMetricUnit(metric)}`,
                    },
                  }}
                  xAxis={{
                    label: {
                      text: 'Concurrency',
                    },
                  }}
                />
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    );
  };

  // Render percentile charts
  const renderPercentileCharts = () => {
    const chartData = preparePercentileChartData();
    
    if (chartData.length === 0) {
      return <Empty description="No percentile data available" />;
    }

    // Group by metric type
    const metricGroups = chartData.reduce((acc, item) => {
      if (!acc[item.metric]) {
        acc[item.metric] = [];
      }
      acc[item.metric].push(item);
      return acc;
    }, {});

    return (
      <Row gutter={[16, 16]}>
        {Object.entries(metricGroups).map(([metric, data]) => (
          <Col span={12} key={metric}>
            <Card title={`${metric} Percentiles`} size="small">
              <div style={{ height: 250 }}>
                <Line
                  data={data}
                  xField="percentile"
                  yField="value"
                  seriesField="modelLabel"
                  smooth={true}
                  point={{
                    size: 3,
                    shape: 'circle',
                  }}
                  tooltip={{
                    formatter: (datum) => ({
                      name: datum.modelLabel,
                      value: `${datum.value?.toFixed(4)} ${getMetricUnit(metric)}`
                    })
                  }}
                  yAxis={{
                    label: {
                      text: `${metric} ${getMetricUnit(metric)}`,
                    },
                  }}
                  xAxis={{
                    label: {
                      text: 'Percentile',
                    },
                  }}
                />
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    );
  };

  // Get metric unit for display
  const getMetricUnit = (metric) => {
    const lowerMetric = metric.toLowerCase();
    if (lowerMetric.includes('time') || lowerMetric.includes('latency') || lowerMetric.includes('ttft') || lowerMetric.includes('tpot') || lowerMetric.includes('itl')) {
      return '(s)';
    }
    if (lowerMetric.includes('throughput') || lowerMetric.includes('tok/s')) {
      return '(tok/s)';
    }
    if (lowerMetric.includes('req/s')) {
      return '(req/s)';
    }
    if (lowerMetric.includes('tokens')) {
      return '(tokens)';
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
            bodyStyle={{ height: 'calc(100vh - 280px)', overflow: 'auto' }}
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
            bodyStyle={{ height: 'calc(100vh - 280px)', overflow: 'auto' }}
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
                {/* Summary Charts Section */}
                <div>
                  <Title level={4}>
                    <DashboardOutlined /> Performance Metrics vs Concurrency
                  </Title>
                  <Text type="secondary">
                    Shows how different metrics change with concurrency levels
                  </Text>
                  <Divider />
                  {renderSummaryCharts()}
                </div>

                {/* Percentile Charts Section */}
                <div>
                  <Title level={4}>
                    <LineChartOutlined /> Percentile Analysis
                  </Title>
                  <Text type="secondary">
                    Distribution of performance metrics across percentiles
                  </Text>
                  <Divider />
                  {renderPercentileCharts()}
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
                          <Space>
                            <Tag>
                              Concurrency: {result.config?.stress_test_config?.concurrency || 'N/A'}
                            </Tag>
                          </Space>
                          <Space>
                            <Tag>
                              Requests: {result.config?.stress_test_config?.total_requests || 'N/A'}
                            </Tag>
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