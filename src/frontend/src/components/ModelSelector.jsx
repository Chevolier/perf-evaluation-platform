import React from 'react';
import { Checkbox, Divider } from 'antd';

const modelGroups = [
  {
    label: 'API模型',
    options: [
      { label: 'Claude 4', value: 'Claude4' },
      { label: 'Claude 3.5 Sonnet', value: 'Claude3.5' },
      { label: 'Nova Pro', value: 'Nova Pro' },
    ]
  },
  {
    label: '本地开源模型 (EMD)',
    options: [
      { label: 'Qwen2-VL-7B-Instruct', value: 'qwen2-vl-7b' },
      { label: 'Qwen2.5-VL-7B-Instruct', value: 'qwen2.5-vl-7b' },
      { label: 'Qwen2.5-VL-32B-Instruct', value: 'qwen2.5-vl-32b' },
      { label: 'Qwen2.5-0.5B-Instruct', value: 'qwen2.5-0.5b' },
      { label: 'Gemma-3-4B-IT', value: 'gemma-3-4b' },
      { label: 'UI-TARS-1.5-7B', value: 'ui-tars-1.5-7b' },
    ]
  }
];

const ModelSelector = ({ value, onChange }) => {
  const handleGroupChange = (newValues) => {
    onChange(newValues);
  };

  return (
    <div>
      {modelGroups.map(group => {
        // Get the values for this group
        const groupValues = group.options.map(opt => opt.value);
        const selectedInGroup = value.filter(v => groupValues.includes(v));
        
        return (
          <div key={group.label} style={{ marginBottom: 12 }}>
            <Divider orientation="left" style={{ fontWeight: 'bold' }}>{group.label}</Divider>
            <Checkbox.Group
              options={group.options}
              value={selectedInGroup}
              onChange={(newGroupValues) => {
                // Remove old values from this group and add new ones
                const otherValues = value.filter(v => !groupValues.includes(v));
                const allValues = [...otherValues, ...newGroupValues];
                handleGroupChange(allValues);
              }}
              style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
            />
          </div>
        );
      })}
    </div>
  );
};

export default ModelSelector; 