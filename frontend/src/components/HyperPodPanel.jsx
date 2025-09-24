import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  CloudServerOutlined,
  CodeOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';

const { Text } = Typography;
const DEFAULT_PRESET = 'small';
const presetDescriptions = {
  small: 'Small • 1× ml.g5.xlarge',
  medium: 'Medium • 2× ml.g5.2xlarge',
  large: 'Large • 4× ml.g5.4xlarge',
};

const statusColor = (status) => {
  switch (status) {
    case 'succeeded':
      return 'green';
    case 'destroyed':
      return 'blue';
    case 'failed':
    case 'destroy_failed':
      return 'red';
    case 'running':
      return 'gold';
    default:
      return 'default';
  }
};

const formatPresetLabel = (value) => presetDescriptions[value] || value;

const HyperPodPanel = () => {
  const [form] = Form.useForm();
  const [sizes, setSizes] = useState([
    { value: DEFAULT_PRESET, label: formatPresetLabel(DEFAULT_PRESET) },
  ]);
  const [loadingSizes, setLoadingSizes] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [destroying, setDestroying] = useState(false);
  const [logModal, setLogModal] = useState({ open: false, loading: false, jobId: null, content: '' });

  const fetchPresets = useCallback(async () => {
    setLoadingSizes(true);
    try {
      const response = await fetch('/api/hyperpod/presets');
      if (!response.ok) {
        throw new Error('Failed to load cluster sizes');
      }
      const data = await response.json();
      if (Array.isArray(data.presets) && data.presets.length) {
        const options = data.presets.map((item) => ({
          value: item,
          label: formatPresetLabel(item),
        }));
        setSizes(options);
        const currentValue = form.getFieldValue('cluster_size');
        if (!currentValue && options[0]) {
          form.setFieldsValue({ cluster_size: options[0].value });
        }
      }
    } catch (error) {
      message.warning(error.message || 'Unable to fetch cluster sizes');
    } finally {
      setLoadingSizes(false);
    }
  }, [form]);

  const fetchJobs = useCallback(async () => {
    setJobsLoading(true);
    try {
      const response = await fetch('/api/hyperpod/jobs');
      if (!response.ok) {
        throw new Error('Failed to load jobs');
      }
      const data = await response.json();
      if (Array.isArray(data.jobs)) {
        setJobs(data.jobs);
      }
    } catch (error) {
      message.warning(error.message || 'Unable to fetch HyperPod jobs');
    } finally {
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPresets();
    fetchJobs();
    const interval = setInterval(fetchJobs, 10000);
    return () => clearInterval(interval);
  }, [fetchJobs, fetchPresets]);

  const handleDeploy = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const selectedSize = values.cluster_size || DEFAULT_PRESET;
      setSubmitting(true);
      const response = await fetch('/api/hyperpod/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          preset: selectedSize,
          dry_run: values.dry_run,
          overrides: {
            region: values.region || undefined,
            cluster_tag: values.cluster_tag || undefined,
            gpu_instance_type: values.gpu_instance_type || undefined,
            gpu_instance_count: values.gpu_instance_count || undefined,
            availability_zone: values.availability_zone || undefined,
            stack_name: values.stack_name || undefined,
          },
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || 'Failed to submit deployment');
      }
      message.success('HyperPod deployment submitted');
      fetchJobs();
    } catch (error) {
      if (error?.errorFields) {
        return;
      }
      message.error(error.message || 'Deployment failed');
    } finally {
      setSubmitting(false);
    }
  }, [form, fetchJobs]);

  const handleDestroy = useCallback(
    async (preset, region) => {
      try {
        setDestroying(true);
        const response = await fetch('/api/hyperpod/destroy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            preset,
            overrides: {
              region,
            },
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.message || 'Failed to submit destroy request');
        }
        message.success('Destroy request submitted');
        fetchJobs();
      } catch (error) {
        message.error(error.message || 'Destroy request failed');
      } finally {
        setDestroying(false);
      }
    },
    [fetchJobs]
  );

  const openLogs = useCallback(async (jobId) => {
    setLogModal({ open: true, loading: true, jobId, content: '' });
    try {
      const response = await fetch(`/api/hyperpod/jobs/${jobId}/logs?tail=400`);
      if (!response.ok) {
        throw new Error('Failed to load logs');
      }
      const data = await response.json();
      setLogModal({ open: true, loading: false, jobId, content: data.logs?.logs || '' });
    } catch (error) {
      setLogModal({ open: true, loading: false, jobId, content: error.message || 'Unable to load logs' });
    }
  }, []);

  const columns = useMemo(
    () => [
      {
        title: 'Job ID',
        dataIndex: 'job_id',
        key: 'job_id',
        render: (value) => <Text code>{value}</Text>,
      },
      {
        title: 'Cluster Size',
        dataIndex: 'preset',
        key: 'preset',
        render: (value) => (value ? <Tag color="geekblue">{formatPresetLabel(value)}</Tag> : '—'),
      },
      {
        title: 'Region',
        dataIndex: 'region',
        key: 'region',
        render: (value) => (value ? <Tag color="geekblue">{value}</Tag> : '—'),
      },
      {
        title: 'Status',
        dataIndex: 'status',
        key: 'status',
        render: (value) => <Tag color={statusColor(value)}>{value}</Tag>,
      },
      {
        title: 'Dry-run',
        dataIndex: 'dry_run',
        key: 'dry_run',
        render: (value) => (value ? <Tag color="default">dry-run</Tag> : <Tag color="green">live</Tag>),
      },
      {
        title: 'Updated',
        dataIndex: 'updated_at',
        key: 'updated_at',
        render: (value) => (value ? new Date(value).toLocaleString() : '—'),
      },
      {
        title: 'Actions',
        key: 'actions',
        render: (_, record) => (
          <Space>
            <Button size="small" icon={<CodeOutlined />} onClick={() => openLogs(record.job_id)}>
              Logs
            </Button>
            <Button
              size="small"
              danger
              loading={destroying}
              onClick={() => handleDestroy(record.preset, record.region)}
              disabled={record.action === 'destroy'}
            >
              Destroy
            </Button>
          </Space>
        ),
      },
    ],
    [destroying, handleDestroy, openLogs]
  );

  return (
    <Card
      title={
        <Space>
          <CloudServerOutlined />
          <span>InfraForge HyperPod Console</span>
        </Space>
      }
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchJobs} loading={jobsLoading}>
            Refresh Jobs
          </Button>
        </Space>
      }
      style={{ marginBottom: 24 }}
    >
      <Form
        form={form}
        layout="inline"
        initialValues={{ dry_run: true, cluster_size: DEFAULT_PRESET }}
        style={{ marginBottom: 16, gap: 12, flexWrap: 'wrap' }}
      >
        <Form.Item
          name="cluster_size"
          label="Cluster Size"
          rules={[{ required: true, message: 'Please choose a cluster size' }]}
        >
          <Select style={{ minWidth: 220 }} options={sizes} loading={loadingSizes} placeholder="Select size" />
        </Form.Item>
        <Form.Item
          name="region"
          label="Region"
          rules={[{ required: true, message: 'Please enter a region' }]}
        >
          <Input placeholder="e.g. us-east-1" style={{ width: 160 }} allowClear />
        </Form.Item>
        <Form.Item name="availability_zone" label="AZ Override">
          <Input placeholder="Optional" style={{ width: 140 }} allowClear />
        </Form.Item>
        <Form.Item name="cluster_tag" label="Cluster Tag">
          <Input placeholder="Optional custom tag" style={{ width: 200 }} allowClear />
        </Form.Item>
        <Form.Item name="stack_name" label="Stack Name">
          <Input placeholder="Optional" style={{ width: 160 }} allowClear />
        </Form.Item>
        <Form.Item name="gpu_instance_type" label="GPU Type">
          <Input placeholder="Optional override" style={{ width: 180 }} allowClear />
        </Form.Item>
        <Form.Item name="gpu_instance_count" label="GPU Count">
          <Input placeholder="Optional" style={{ width: 120 }} allowClear />
        </Form.Item>
        <Form.Item name="dry_run" label="Dry-run" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item>
          <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleDeploy} loading={submitting}>
            Launch Deploy
          </Button>
        </Form.Item>
      </Form>

      <Table
        rowKey="job_id"
        dataSource={jobs}
        columns={columns}
        size="small"
        loading={jobsLoading}
        pagination={{ pageSize: 5 }}
      />

      <Modal
        title={`HyperPod Logs - ${logModal.jobId || ''}`}
        open={logModal.open}
        footer={null}
        onCancel={() => setLogModal({ open: false, loading: false, jobId: null, content: '' })}
        width={720}
      >
        <pre
          style={{
            maxHeight: 360,
            overflow: 'auto',
            background: '#1e1e1e',
            color: '#f5f5f5',
            padding: 16,
            borderRadius: 4,
          }}
        >
          {logModal.loading ? 'Loading logs…' : logModal.content || 'No logs yet'}
        </pre>
      </Modal>
    </Card>
  );
};

export default HyperPodPanel;
