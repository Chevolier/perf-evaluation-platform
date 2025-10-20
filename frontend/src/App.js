import React, { useState, useEffect } from 'react';
import { Layout, Typography, Menu, Modal, Button } from 'antd';
import { 
  SettingOutlined, 
  PlayCircleOutlined, 
  ThunderboltOutlined,
  RobotOutlined,
  LineChartOutlined,
  BarChartOutlined
} from '@ant-design/icons';
import ModelSelectionModal from './components/ModelSelectionModal';
import PlaygroundPage from './pages/PlaygroundPage';
import ModelHubPage from './pages/ModelHubPage';
import StressTestPage from './pages/StressTestPage';
import VisualizationPage from './pages/VisualizationPage';
import 'antd/dist/reset.css';

const { Header, Content, Sider } = Layout;
const { Title } = Typography;

// Helper function to get current page from URL
const getCurrentPageFromURL = () => {
  const hash = window.location.hash.replace('#', '');
  const validPages = ['model-hub', 'playground', 'stress-test', 'visualization', 'settings'];
  return validPages.includes(hash) ? hash : 'model-hub';
};

// Helper function to update URL when page changes
const updateURL = (page) => {
  window.history.replaceState(null, null, `#${page}`);
};

function App() {
  // Load playground state from localStorage
  const [selectedModels, setSelectedModels] = useState(() => {
    try {
      const saved = localStorage.getItem('playground_selectedModels');
      return saved ? JSON.parse(saved) : [];
    } catch (error) {
      console.error('Failed to load selected models from localStorage:', error);
      return [];
    }
  });
  
  const [dataset, setDataset] = useState(() => {
    try {
      const saved = localStorage.getItem('playground_dataset');
      return saved ? JSON.parse(saved) : { type: 'image', files: [], prompt: '' };
    } catch (error) {
      console.error('Failed to load dataset from localStorage:', error);
      return { type: 'image', files: [], prompt: '' };
    }
  });
  
  const [params, setParams] = useState(() => {
    try {
      // Force update to new default values - remove this block after deployment
      const newDefaults = { max_tokens: 1024, temperature: 0.6 };
      localStorage.setItem('playground_params', JSON.stringify(newDefaults));
      return newDefaults;

      // Original code - uncomment this and remove the above after users see new defaults
      // const saved = localStorage.getItem('playground_params');
      // return saved ? JSON.parse(saved) : { max_tokens: 1024, temperature: 0.6 };
    } catch (error) {
      console.error('Failed to load params from localStorage:', error);
      return { max_tokens: 1024, temperature: 0.6 };
    }
  });
  
  // 侧边栏状态
  const [collapsed, setCollapsed] = useState(false);
  const [currentPage, setCurrentPage] = useState(getCurrentPageFromURL);
  
  // 模型选择弹窗状态
  const [modelModalVisible, setModelModalVisible] = useState(false);

  // Function to handle page navigation
  const navigateToPage = (page) => {
    setCurrentPage(page);
    updateURL(page);
  };

  const menuItems = [
    {
      key: 'model-hub',
      icon: <RobotOutlined />,
      label: '模型部署',
      onClick: () => navigateToPage('model-hub')
    },
    {
      key: 'playground',
      icon: <PlayCircleOutlined />,
      label: '在线体验',
      onClick: () => navigateToPage('playground')
    },
    {
      key: 'stress-test',
      icon: <ThunderboltOutlined />,
      label: '性能评测',
      onClick: () => navigateToPage('stress-test')
    },
    // {
    //   key: 'model-evaluation',
    //   icon: <LineChartOutlined />,
    //   label: '效果评测',
    //   onClick: () => navigateToPage('model-evaluation')
    // },
    {
      key: 'visualization',
      icon: <BarChartOutlined />,
      label: '结果展示',
      onClick: () => navigateToPage('visualization')
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置',
      onClick: () => navigateToPage('settings')
    }
  ];

  // Save playground state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('playground_selectedModels', JSON.stringify(selectedModels));
    } catch (error) {
      console.error('Failed to save selected models to localStorage:', error);
    }
  }, [selectedModels]);

  useEffect(() => {
    try {
      localStorage.setItem('playground_dataset', JSON.stringify(dataset));
    } catch (error) {
      console.error('Failed to save dataset to localStorage:', error);
    }
  }, [dataset]);

  useEffect(() => {
    try {
      localStorage.setItem('playground_params', JSON.stringify(params));
    } catch (error) {
      console.error('Failed to save params to localStorage:', error);
    }
  }, [params]);

  // Listen for URL hash changes (browser back/forward buttons)
  useEffect(() => {
    const handleHashChange = () => {
      const newPage = getCurrentPageFromURL();
      setCurrentPage(newPage);
    };

    window.addEventListener('hashchange', handleHashChange);
    
    // Cleanup
    return () => {
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, []);

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
      case 'visualization':
        return <VisualizationPage />;
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
          大模型性能评测平台
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