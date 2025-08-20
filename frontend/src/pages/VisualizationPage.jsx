import React, { useState, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Spin,
  Alert,
  Select,
  Button,
  Tree,
  Typography,
  Statistic,
  Table,
  Tabs,
  Space,
  Tag,
  Tooltip
} from 'antd';
import { Line, Column, Scatter } from '@ant-design/plots';
import {
  ReloadOutlined,
  BarChartOutlined,
  LineChartOutlined,
  DashboardOutlined,
  DollarOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;
const { TabPane } = Tabs;

// API base URL - should match viz_server.py
const API_BASE = process.env.REACT_APP_VIZ_API_BASE || 'http://localhost:8000';

const VisualizationPage = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [treeData, setTreeData] = useState([]);
  const [selectedModels, setSelectedModels] = useState([]);
  const [comparisonData, setComparisonData] = useState([]);
  const [stats, setStats] = useState(null);
  const [instancePrices, setInstancePrices] = useState({});
  const [activeTab, setActiveTab] = useState('overview');

  // Fetch tree structure
  const fetchTreeStructure = async (reload = false) => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/api/tree-structure?reload=${reload}`);
      const data = await response.json();
      setTreeData(data.tree || []);
    } catch (err) {
      setError(`Failed to fetch tree structure: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/stats`);
      const data = await response.json();
      setStats(data);
    } catch (err) {
      setError(`Failed to fetch stats: ${err.message}`);
    }
  };

  // Fetch instance prices
  const fetchInstancePrices = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/instance-prices`);
      const data = await response.json();
      setInstancePrices(data.prices || {});
    } catch (err) {
      console.warn('Failed to fetch instance prices:', err.message);
    }
  };

  // Fetch comparison data
  const fetchComparisonData = async (combinations) => {
    if (!combinations || combinations.length === 0) return;
    
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/api/comparison-data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ combinations }),
      });
      const data = await response.json();
      setComparisonData(data);
    } catch (err) {
      setError(`Failed to fetch comparison data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Handle model selection from tree
  const handleTreeSelect = (selectedKeys, info) => {
    const selectedNodes = info.selectedNodes?.filter(node => node.type === 'model') || [];
    const combinations = selectedNodes.map(node => ({
      runtime: node.runtime,
      instance_type: node.instance_type,
      model_name: node.model_name,
      id: node.id
    }));
    
    setSelectedModels(combinations);
    if (combinations.length > 0) {
      fetchComparisonData(combinations);
    }
  };

  // Prepare chart data
  const prepareChartData = () => {
    if (!comparisonData || comparisonData.length === 0) return [];
    
    const chartData = [];
    comparisonData.forEach(item => {
      const { combination, data } = item;
      const label = `${combination.runtime}-${combination.instance_type}-${combination.model_name}`;
      
      data.forEach(record => {
        chartData.push({
          ...record,
          combination_label: label,
          processes: record.processes || 0,
          first_token_latency: record.first_token_latency_mean || 0,
          end_to_end_latency: record.end_to_end_latency_mean || 0,
          throughput: record.output_tokens_per_second_mean || 0,
          cost_per_million_tokens: record.cost_per_million_tokens || 0,
          success_rate: (record.success_rate || 0) * 100
        });
      });
    });
    
    return chartData;
  };

  // Prepare table data
  const prepareTableData = () => {
    const chartData = prepareChartData();
    return chartData.map((item, index) => ({
      key: index,
      ...item
    }));
  };

  useEffect(() => {
    fetchTreeStructure();
    fetchStats();
    fetchInstancePrices();
  }, []);

  const tableColumns = [
    {
      title: 'Configuration',
      dataIndex: 'combination_label',
      key: 'combination_label',
      width: 200,
      render: (text) => <Text strong>{text}</Text>
    },
    {
      title: 'Processes',
      dataIndex: 'processes',
      key: 'processes',
      width: 100,
      sorter: (a, b) => a.processes - b.processes
    },
    {
      title: 'Input Tokens',
      dataIndex: 'input_tokens',
      key: 'input_tokens',
      width: 120,
      sorter: (a, b) => a.input_tokens - b.input_tokens
    },
    {
      title: 'Output Tokens',
      dataIndex: 'output_tokens',
      key: 'output_tokens',
      width: 120,
      sorter: (a, b) => a.output_tokens - b.output_tokens
    },
    {
      title: 'First Token Latency (ms)',
      dataIndex: 'first_token_latency',
      key: 'first_token_latency',
      width: 180,
      render: (value) => value?.toFixed(2) || 'N/A',
      sorter: (a, b) => a.first_token_latency - b.first_token_latency
    },
    {
      title: 'End-to-End Latency (ms)',
      dataIndex: 'end_to_end_latency',
      key: 'end_to_end_latency',
      width: 180,
      render: (value) => value?.toFixed(2) || 'N/A',
      sorter: (a, b) => a.end_to_end_latency - b.end_to_end_latency
    },
    {
      title: 'Throughput (tokens/s)',
      dataIndex: 'throughput',
      key: 'throughput',
      width: 160,
      render: (value) => value?.toFixed(2) || 'N/A',
      sorter: (a, b) => a.throughput - b.throughput
    },
    {
      title: 'Success Rate (%)',
      dataIndex: 'success_rate',
      key: 'success_rate',
      width: 140,
      render: (value) => (
        <Tag color={value >= 95 ? 'green' : value >= 80 ? 'orange' : 'red'}>
          {value?.toFixed(1) || 'N/A'}%
        </Tag>
      ),
      sorter: (a, b) => a.success_rate - b.success_rate
    },
    {
      title: 'Cost ($/M tokens)',
      dataIndex: 'cost_per_million_tokens',
      key: 'cost_per_million_tokens',
      width: 160,
      render: (value) => value > 0 ? `$${value.toFixed(2)}` : 'N/A',
      sorter: (a, b) => a.cost_per_million_tokens - b.cost_per_million_tokens
    }
  ];

  const chartData = prepareChartData();
  const tableData = prepareTableData();

  return (
    <div style={{ padding: '24px', background: '#f0f2f5', minHeight: '100vh' }}>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card>
            <Row justify="space-between" align="middle">
              <Col>
                <Title level={2} style={{ margin: 0 }}>
                  <BarChartOutlined /> 可视化结果
                </Title>
              </Col>
              <Col>
                <Button 
                  icon={<ReloadOutlined />} 
                  onClick={() => fetchTreeStructure(true)}
                  loading={loading}
                >
                  Refresh Data
                </Button>
              </Col>
            </Row>
          </Card>
        </Col>

        {/* Overview Stats */}
        {stats && (
          <Col span={24}>
            <Card title={<><DashboardOutlined /> Overview Statistics</>}>
              <Row gutter={16}>
                <Col span={6}>
                  <Statistic 
                    title="Total Tests" 
                    value={stats.total_tests} 
                    formatter={(value) => value.toLocaleString()}
                  />
                </Col>
                <Col span={6}>
                  <Statistic 
                    title="Unique Combinations" 
                    value={stats.unique_combinations}
                    formatter={(value) => value.toLocaleString()}
                  />
                </Col>
                <Col span={6}>
                  <Statistic 
                    title="Average Throughput" 
                    value={stats.performance_summary?.avg_throughput || 0}
                    formatter={(value) => `${value.toFixed(1)} tokens/s`}
                  />
                </Col>
                <Col span={6}>
                  <Statistic 
                    title="Average Success Rate" 
                    value={(stats.performance_summary?.avg_success_rate || 0) * 100}
                    formatter={(value) => `${value.toFixed(1)}%`}
                    suffix="%"
                  />
                </Col>
              </Row>
            </Card>
          </Col>
        )}

        <Col span={8}>
          <Card 
            title="Model Selection" 
            style={{ height: '600px' }}
            bodyStyle={{ height: '520px', overflow: 'auto' }}
          >
            {loading ? (
              <Spin size="large" style={{ display: 'block', textAlign: 'center', marginTop: '200px' }} />
            ) : error ? (
              <Alert message="Error" description={error} type="error" showIcon />
            ) : (
              <Tree
                checkable
                multiple
                onSelect={handleTreeSelect}
                treeData={treeData.map(runtime => ({
                  title: `${runtime.label} (${runtime.count})`,
                  key: runtime.id,
                  children: runtime.children?.map(instance => ({
                    title: `${instance.label} (${instance.count})`,
                    key: instance.id,
                    children: instance.children?.map(model => ({
                      title: `${model.label} (${model.count})`,
                      key: model.id,
                      type: model.type,
                      runtime: model.runtime,
                      instance_type: model.instance_type,
                      model_name: model.model_name
                    }))
                  }))
                }))}
              />
            )}
          </Card>
        </Col>

        <Col span={16}>
          <Card style={{ height: '600px' }}>
            <Tabs activeKey={activeTab} onChange={setActiveTab}>
              <TabPane tab={<><LineChartOutlined /> Performance Charts</> } key="charts">
                {chartData.length > 0 ? (
                  <div style={{ height: '500px', overflow: 'auto' }}>
                    <Row gutter={[16, 16]}>
                      <Col span={24}>
                        <Title level={4}>Throughput vs Processes</Title>
                        <div style={{ height: '200px' }}>
                          <Line
                            data={chartData}
                            xField="processes"
                            yField="throughput"
                            seriesField="combination_label"
                            smooth={true}
                            animation={{
                              appear: {
                                animation: 'path-in',
                                duration: 1000,
                              },
                            }}
                            point={{
                              size: 4,
                              shape: 'circle',
                            }}
                            tooltip={{
                              formatter: (datum) => {
                                return {
                                  name: 'Throughput',
                                  value: `${datum.throughput?.toFixed(2)} tokens/s`
                                };
                              }
                            }}
                            yAxis={{
                              label: {
                                text: 'Throughput (tokens/s)',
                              },
                            }}
                            xAxis={{
                              label: {
                                text: 'Processes',
                              },
                            }}
                          />
                        </div>
                      </Col>
                      
                      <Col span={24}>
                        <Title level={4}>Latency Comparison</Title>
                        <div style={{ height: '200px' }}>
                          <Column
                            data={[
                              ...chartData.map(d => ({
                                ...d,
                                latency_type: 'First Token',
                                latency_value: d.first_token_latency
                              })),
                              ...chartData.map(d => ({
                                ...d,
                                latency_type: 'End-to-End',
                                latency_value: d.end_to_end_latency
                              }))
                            ]}
                            xField="processes"
                            yField="latency_value"
                            seriesField="latency_type"
                            isGroup={true}
                            columnStyle={{
                              radius: [2, 2, 0, 0],
                            }}
                            tooltip={{
                              formatter: (datum) => {
                                return {
                                  name: datum.latency_type,
                                  value: `${datum.latency_value?.toFixed(2)} ms`
                                };
                              }
                            }}
                            yAxis={{
                              label: {
                                text: 'Latency (ms)',
                              },
                            }}
                            xAxis={{
                              label: {
                                text: 'Processes',
                              },
                            }}
                          />
                        </div>
                      </Col>
                    </Row>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '50px' }}>
                    <Text type="secondary">Select models from the tree to view performance charts</Text>
                  </div>
                )}
              </TabPane>
              
              <TabPane tab={<><DollarOutlined /> Cost Analysis</> } key="cost">
                {chartData.length > 0 && chartData.some(d => d.cost_per_million_tokens > 0) ? (
                  <div style={{ height: '500px', overflow: 'auto' }}>
                    <Title level={4}>Cost per Million Tokens vs Throughput</Title>
                    <div style={{ height: '300px' }}>
                      <Scatter
                        data={chartData.filter(d => d.cost_per_million_tokens > 0)}
                        xField="throughput"
                        yField="cost_per_million_tokens"
                        colorField="combination_label"
                        size={6}
                        pointStyle={{
                          fillOpacity: 0.8,
                          stroke: '#bbb',
                          lineWidth: 1,
                        }}
                        tooltip={{
                          formatter: (datum) => [
                            { name: 'Throughput', value: `${datum.throughput?.toFixed(2)} tokens/s` },
                            { name: 'Cost', value: `$${datum.cost_per_million_tokens?.toFixed(2)}/M tokens` },
                            { name: 'Configuration', value: datum.combination_label }
                          ]
                        }}
                        yAxis={{
                          label: {
                            text: 'Cost per Million Tokens ($)',
                          },
                        }}
                        xAxis={{
                          label: {
                            text: 'Throughput (tokens/s)',
                          },
                        }}
                        legend={{
                          position: 'bottom',
                        }}
                      />
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '50px' }}>
                    <Text type="secondary">
                      {chartData.length === 0 
                        ? 'Select models to view cost analysis' 
                        : 'No pricing data available for selected models'
                      }
                    </Text>
                  </div>
                )}
              </TabPane>
            </Tabs>
          </Card>
        </Col>

        {/* Data Table */}
        {tableData.length > 0 && (
          <Col span={24}>
            <Card title="Detailed Performance Data">
              <Table
                columns={tableColumns}
                dataSource={tableData}
                scroll={{ x: 1500 }}
                pagination={{ pageSize: 10 }}
                size="small"
              />
            </Card>
          </Col>
        )}

        {/* Selected Models Summary */}
        {selectedModels.length > 0 && (
          <Col span={24}>
            <Card title="Selected Models">
              <Space wrap>
                {selectedModels.map((model, index) => (
                  <Tag key={index} color="blue" style={{ marginBottom: '4px' }}>
                    {model.runtime} - {model.instance_type} - {model.model_name}
                  </Tag>
                ))}
              </Space>
            </Card>
          </Col>
        )}
      </Row>
    </div>
  );
};

export default VisualizationPage;