import React, { useState } from 'react';
import { Layout, Typography, Menu, Modal, Button } from 'antd';
import { 
  SettingOutlined, 
  PlayCircleOutlined, 
  ThunderboltOutlined,
  RobotOutlined,
  LineChartOutlined 
} from '@ant-design/icons';
import ModelSelectionModal from './components/ModelSelectionModal';
import PlaygroundPage from './pages/PlaygroundPage';
import ModelHubPage from './pages/ModelHubPage';
import StressTestPage from './pages/StressTestPage';
import 'antd/dist/reset.css';

const { Header, Content, Sider } = Layout;
const { Title } = Typography;

function App() {
  const [selectedModels, setSelectedModels] = useState([]);
  const [dataset, setDataset] = useState({ type: 'image', files: [], prompt: '' });
  const [params, setParams] = useState({ max_tokens: 1024, temperature: 0.1 });
  
  // 侧边栏状态
  const [collapsed, setCollapsed] = useState(false);
  const [currentPage, setCurrentPage] = useState('model-hub');
  
  // 模型选择弹窗状态
  const [modelModalVisible, setModelModalVisible] = useState(false);

  const menuItems = [
    {
      key: 'model-hub',
      icon: <RobotOutlined />,
      label: 'Model Hub',
      onClick: () => setCurrentPage('model-hub')
    },
    {
      key: 'playground',
      icon: <PlayCircleOutlined />,
      label: 'Playground',
      onClick: () => setCurrentPage('playground')
    },
    {
      key: 'model-evaluation',
      icon: <LineChartOutlined />,
      label: '模型评测',
      onClick: () => setCurrentPage('model-evaluation')
    },
    {
      key: 'stress-test',
      icon: <ThunderboltOutlined />,
      label: '压力测试',
      onClick: () => setCurrentPage('stress-test')
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置',
      onClick: () => setCurrentPage('settings')
    }
  ];

  const renderContent = () => {
    switch (currentPage) {
      case 'model-hub':
        return <ModelHubPage />;
      case 'playground':
        return (
          <PlaygroundPage
            selectedModels={selectedModels}
            dataset={dataset}
            onDatasetChange={setDataset}
            params={params}
            onParamsChange={setParams}
            onModelChange={setSelectedModels}
          />
        );
      case 'model-evaluation':
        return (
          <div style={{ padding: '20px', textAlign: 'center' }}>
            <Title level={3}>模型评测</Title>
            <p style={{ color: '#666' }}>功能开发中，敬请期待...</p>
          </div>
        );
      case 'stress-test':
        return <StressTestPage />;
      case 'settings':
        return (
          <div style={{ padding: '20px', textAlign: 'center' }}>
            <Title level={3}>系统设置</Title>
            <p style={{ color: '#666' }}>功能开发中，敬请期待...</p>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ 
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 
        color: '#fff', 
        fontSize: '24px', 
        fontWeight: 'bold',
        textAlign: 'center',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '64px'
      }}>
        <Title level={2} style={{ color: '#fff', margin: 0 }}>
          多模态大模型评测平台
        </Title>
      </Header>
      
      <Layout>
        <Sider 
          collapsible 
          collapsed={collapsed} 
          onCollapse={setCollapsed}
          width={200}
          style={{
            background: '#fff',
            boxShadow: '2px 0 6px rgba(0, 0, 0, 0.1)'
          }}
        >
          <div style={{ padding: '16px 0' }}>
            {selectedModels.length > 0 && (
              <div style={{ 
                padding: '8px 16px', 
                marginBottom: '8px',
                background: '#f6f6f6',
                fontSize: '12px',
                color: '#666'
              }}>
                {collapsed ? 
                  `${selectedModels.length}个模型` : 
                  `已选择 ${selectedModels.length} 个模型`
                }
              </div>
            )}
          </div>
          
          <Menu
            mode="inline"
            selectedKeys={[currentPage]}
            style={{ borderRight: 0 }}
            items={menuItems}
          />
        </Sider>
        
        <Layout style={{ background: '#f0f2f5' }}>
          <Content style={{ 
            margin: 0, 
            minHeight: 280,
            background: '#f0f2f5'
          }}>
            {renderContent()}
          </Content>
        </Layout>
      </Layout>

      {/* 模型选择弹窗 */}
      <ModelSelectionModal
        visible={modelModalVisible}
        onCancel={() => setModelModalVisible(false)}
        selectedModels={selectedModels}
        onModelChange={setSelectedModels}
        onOk={() => setModelModalVisible(false)}
      />
    </Layout>
  );
}

export default App;