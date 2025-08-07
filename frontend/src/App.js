import React, { useState } from 'react';
import { Layout, Typography } from 'antd';
import ModelSelectionPage from './pages/ModelSelectionPage';
import MaterialUploadPage from './pages/MaterialUploadPage';
import ConfigurationPage from './pages/ConfigurationPage';
import InferencePage from './pages/InferencePage';
import 'antd/dist/reset.css';

const { Header, Content } = Layout;
const { Title } = Typography;

function App() {
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedModels, setSelectedModels] = useState([]);
  const [dataset, setDataset] = useState({ type: 'image', files: [], prompt: '' });
  const [params, setParams] = useState({ max_tokens: 1024, temperature: 0.1 });

  const handleNext = () => {
    setCurrentStep(currentStep + 1);
  };

  const handlePrev = () => {
    setCurrentStep(currentStep - 1);
  };

  const handleReset = () => {
    setCurrentStep(0);
    setSelectedModels([]);
    setDataset({ type: 'image', files: [], prompt: '' });
    setParams({ max_tokens: 1024, temperature: 0.1 });
  };

  const renderCurrentPage = () => {
    switch (currentStep) {
      case 0:
        return (
          <ModelSelectionPage
            selectedModels={selectedModels}
            onModelChange={setSelectedModels}
            onNext={handleNext}
          />
        );
      case 1:
        return (
          <MaterialUploadPage
            dataset={dataset}
            onDatasetChange={setDataset}
            selectedModels={selectedModels}
            onNext={handleNext}
            onPrev={handlePrev}
          />
        );
      case 2:
        return (
          <ConfigurationPage
            params={params}
            onParamsChange={setParams}
            selectedModels={selectedModels}
            dataset={dataset}
            onNext={handleNext}
            onPrev={handlePrev}
          />
        );
      case 3:
        return (
          <InferencePage
            selectedModels={selectedModels}
            dataset={dataset}
            params={params}
            onPrev={handlePrev}
            onReset={handleReset}
          />
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
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
      }}>
        <Title level={2} style={{ color: '#fff', margin: 0 }}>
          多模态大模型评测平台
        </Title>
      </Header>
      <Content style={{ backgroundColor: '#f0f2f5' }}>
        {renderCurrentPage()}
      </Content>
    </Layout>
  );
}

export default App;
