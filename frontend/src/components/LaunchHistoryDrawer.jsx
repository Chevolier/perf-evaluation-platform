import React, { useState, useEffect, useCallback } from 'react';
import {
  Drawer,
  Table,
  Tag,
  Button,
  Space,
  Typography,
  message,
  Popconfirm,
  Tooltip,
  Badge,
  Alert,
  Input,
  Select,
  DatePicker
} from 'antd';
import {
  HistoryOutlined,
  ReloadOutlined,
  StopOutlined,
  CopyOutlined,
  LinkOutlined,
  FilterOutlined
} from '@ant-design/icons';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { Option } = Select;
const { RangePicker } = DatePicker;

const LaunchHistoryDrawer = ({ visible, onClose }) => {
  const [launches, setLaunches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    method: null,
    status: null,
    model_key: null
  });
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0
  });

  // Auto-refresh interval for active jobs
  const [refreshInterval, setRefreshInterval] = useState(null);

  // Fetch launches
  const fetchLaunches = useCallback(async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: pageSize.toString(),
        offset: ((page - 1) * pageSize).toString()
      });

      // Add filters
      Object.entries(filters).forEach(([key, value]) => {
        if (value) {
          params.append(key, value);
        }
      });

      const response = await fetch(`/api/launches?${params}`);
      const data = await response.json();

      if (data.success) {
        setLaunches(data.jobs);
        setPagination(prev => ({
          ...prev,
          current: page,
          pageSize,
          total: data.pagination?.count || data.jobs.length
        }));
      } else {
        message.error('Failed to load launch history');
      }
    } catch (error) {
      console.error('Error fetching launches:', error);
      message.error('Failed to load launch history');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // Initial load and when filters change
  useEffect(() => {
    if (visible) {
      fetchLaunches();
    }
  }, [visible, fetchLaunches]);

  // Auto-refresh for active jobs
  useEffect(() => {
    if (visible) {
      const interval = setInterval(() => {
        const hasActiveJobs = launches.some(job => 
          ['queued', 'running'].includes(job.status)
        );
        
        if (hasActiveJobs) {
          fetchLaunches(pagination.current, pagination.pageSize);
        }
      }, 5000); // Refresh every 5 seconds

      setRefreshInterval(interval);

      return () => {
        if (interval) {
          clearInterval(interval);
        }
      };
    }
  }, [visible, launches, pagination.current, pagination.pageSize, fetchLaunches]);

  const handleCancelLaunch = async (jobId) => {
    try {
      const response = await fetch(`/api/launches/${jobId}`, {
        method: 'DELETE'
      });
      const data = await response.json();

      if (data.success) {
        message.success('Launch cancelled successfully');
        fetchLaunches(pagination.current, pagination.pageSize);
      } else {
        message.error(data.error || 'Failed to cancel launch');
      }
    } catch (error) {
      console.error('Error cancelling launch:', error);
      message.error('Failed to cancel launch');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      message.success('Copied to clipboard');
    });
  };

  const getStatusColor = (status) => {
    const colors = {
      'queued': 'blue',
      'running': 'orange',
      'completed': 'green',
      'failed': 'red',
      'cancelled': 'gray'
    };
    return colors[status] || 'default';
  };

  const getStatusIcon = (status) => {
    const icons = {
      'queued': <Badge status="processing" />,
      'running': <Badge status="processing" />,
      'completed': <Badge status="success" />,
      'failed': <Badge status="error" />,
      'cancelled': <Badge status="default" />
    };
    return icons[status] || <Badge status="default" />;
  };

  const columns = [
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status) => (
        <Space>
          {getStatusIcon(status)}
          <Tag color={getStatusColor(status)}>
            {status.toUpperCase()}
          </Tag>
        </Space>
      ),
      filters: [
        { text: 'Queued', value: 'queued' },
        { text: 'Running', value: 'running' },
        { text: 'Completed', value: 'completed' },
        { text: 'Failed', value: 'failed' },
        { text: 'Cancelled', value: 'cancelled' }
      ],
      onFilter: (value, record) => record.status === value
    },
    {
      title: 'Job ID',
      dataIndex: 'job_id',
      key: 'job_id',
      width: 120,
      render: (jobId) => (
        <Tooltip title="Click to copy">
          <Text
            code
            style={{ cursor: 'pointer' }}
            onClick={() => copyToClipboard(jobId)}
          >
            {jobId.slice(0, 8)}...
          </Text>
        </Tooltip>
      )
    },
    {
      title: 'Model',
      dataIndex: 'model_key',
      key: 'model_key',
      width: 150,
      render: (modelKey) => (
        <Text strong>{modelKey}</Text>
      )
    },
    {
      title: 'Method',
      dataIndex: 'method',
      key: 'method',
      width: 120,
      render: (method) => (
        <Tag color="blue">{method}</Tag>
      ),
      filters: [
        { text: 'SageMaker Endpoint', value: 'SAGEMAKER_ENDPOINT' },
        { text: 'HyperPod', value: 'HYPERPOD' },
        { text: 'EKS', value: 'EKS' },
        { text: 'EC2', value: 'EC2' }
      ],
      onFilter: (value, record) => record.method === value
    },
    {
      title: 'Engine',
      dataIndex: 'engine',
      key: 'engine',
      width: 80,
      render: (engine) => (
        <Tag color="green">{engine?.toUpperCase()}</Tag>
      )
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 120,
      render: (createdAt) => (
        <Text type="secondary">
          {dayjs(createdAt).format('MM/DD HH:mm')}
        </Text>
      ),
      sorter: (a, b) => dayjs(a.created_at).unix() - dayjs(b.created_at).unix()
    },
    {
      title: 'Duration',
      key: 'duration',
      width: 100,
      render: (_, record) => {
        if (!record.started_at) return '-';
        
        const endTime = record.completed_at || new Date().toISOString();
        const duration = dayjs(endTime).diff(dayjs(record.started_at), 'minute');
        
        if (duration < 60) {
          return `${duration}m`;
        } else {
          const hours = Math.floor(duration / 60);
          const minutes = duration % 60;
          return `${hours}h ${minutes}m`;
        }
      }
    },
    {
      title: 'Endpoint',
      dataIndex: 'endpoint_url',
      key: 'endpoint_url',
      width: 200,
      render: (endpoint) => {
        if (!endpoint) return '-';
        
        return (
          <Space>
            <Text
              code
              style={{ 
                maxWidth: 150, 
                overflow: 'hidden', 
                textOverflow: 'ellipsis',
                cursor: 'pointer'
              }}
              onClick={() => copyToClipboard(endpoint)}
              title={endpoint}
            >
              {endpoint}
            </Text>
            <Button
              type="link"
              size="small"
              icon={<LinkOutlined />}
              onClick={() => window.open(endpoint, '_blank')}
            />
          </Space>
        );
      }
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_, record) => {
        const canCancel = ['queued', 'running'].includes(record.status);
        
        return (
          <Space>
            {canCancel && (
              <Popconfirm
                title="Cancel this launch?"
                description="This will stop the deployment process."
                onConfirm={() => handleCancelLaunch(record.job_id)}
                okText="Yes"
                cancelText="No"
              >
                <Button
                  type="link"
                  size="small"
                  danger
                  icon={<StopOutlined />}
                >
                  Cancel
                </Button>
              </Popconfirm>
            )}
          </Space>
        );
      }
    }
  ];

  const handleTableChange = (paginationInfo, filters, sorter) => {
    setPagination(prev => ({
      ...prev,
      current: paginationInfo.current,
      pageSize: paginationInfo.pageSize
    }));
    
    fetchLaunches(paginationInfo.current, paginationInfo.pageSize);
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const clearFilters = () => {
    setFilters({
      method: null,
      status: null,
      model_key: null
    });
  };

  const activeJobsCount = launches.filter(job => 
    ['queued', 'running'].includes(job.status)
  ).length;

  return (
    <Drawer
      title={
        <Space>
          <HistoryOutlined />
          <span>Launch History</span>
          {activeJobsCount > 0 && (
            <Badge count={activeJobsCount} size="small" />
          )}
        </Space>
      }
      placement="right"
      size="large"
      onClose={onClose}
      open={visible}
      extra={
        <Space>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => fetchLaunches(pagination.current, pagination.pageSize)}
            loading={loading}
          >
            Refresh
          </Button>
        </Space>
      }
    >
      {/* Active Jobs Alert */}
      {activeJobsCount > 0 && (
        <Alert
          message={`${activeJobsCount} active job(s) running`}
          description="The list will auto-refresh every 5 seconds for active jobs."
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Filters */}
      <div style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            placeholder="Filter by method"
            style={{ width: 150 }}
            allowClear
            value={filters.method}
            onChange={(value) => handleFilterChange('method', value)}
          >
            <Option value="SAGEMAKER_ENDPOINT">SageMaker Endpoint</Option>
            <Option value="HYPERPOD">HyperPod</Option>
            <Option value="EKS">EKS</Option>
            <Option value="EC2">EC2</Option>
          </Select>

          <Select
            placeholder="Filter by status"
            style={{ width: 120 }}
            allowClear
            value={filters.status}
            onChange={(value) => handleFilterChange('status', value)}
          >
            <Option value="queued">Queued</Option>
            <Option value="running">Running</Option>
            <Option value="completed">Completed</Option>
            <Option value="failed">Failed</Option>
            <Option value="cancelled">Cancelled</Option>
          </Select>

          <Input
            placeholder="Filter by model"
            style={{ width: 150 }}
            value={filters.model_key}
            onChange={(e) => handleFilterChange('model_key', e.target.value)}
            allowClear
          />

          <Button
            icon={<FilterOutlined />}
            onClick={clearFilters}
          >
            Clear
          </Button>
        </Space>
      </div>

      {/* Launch History Table */}
      <Table
        columns={columns}
        dataSource={launches}
        rowKey="job_id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total, range) => 
            `${range[0]}-${range[1]} of ${total} launches`
        }}
        onChange={handleTableChange}
        scroll={{ x: 1200 }}
        size="small"
      />
    </Drawer>
  );
};

export default LaunchHistoryDrawer;
