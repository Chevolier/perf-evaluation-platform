// UI utility functions
import { STATE } from './config.js';
import { findNodeFromTreeItem } from './tree.js';

export function updateSelectedInfo() {
    const selectedInfo = document.getElementById('selected-info');
    const selectedText = document.getElementById('selected-text');
    const addChartBtn = document.getElementById('add-chart-btn');

    if (STATE.currentSelection) {
        selectedText.innerHTML = `
            <strong>Runtime:</strong> ${STATE.currentSelection.runtime}<br>
            <strong>Instance:</strong> ${STATE.currentSelection.instance_type}<br>
            <strong>Model:</strong> ${STATE.currentSelection.model_name}
        `;
        selectedInfo.style.display = 'block';

        if (addChartBtn) {
            addChartBtn.disabled = false;
        }
    } else {
        selectedInfo.style.display = 'none';

        if (addChartBtn) {
            addChartBtn.disabled = true;
        }
    }
}

export function updateModelCheckboxStates() {
    document.querySelectorAll('.tree-checkbox').forEach(checkbox => {
        const treeItem = checkbox.closest('.tree-item');
        const treeNode = findNodeFromTreeItem(treeItem);

        if (treeNode && treeNode.type === 'model') {
            const modelKey = `${treeNode.runtime}-${treeNode.instance_type}-${treeNode.model_name}`;
            const isInComparison = STATE.selectedCombinations.some(c =>
                `${c.runtime}-${c.instance_type}-${c.model_name}` === modelKey
            );
            checkbox.checked = isInComparison;
        }
    });
}

export function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
}

export function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

export function clearError() {
    document.getElementById('error').style.display = 'none';
}

export function showSuccess(message) {
    const successDiv = document.createElement('div');
    successDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #d4edda;
        color: #155724;
        padding: 15px;
        border-radius: 4px;
        border: 1px solid #c3e6cb;
        z-index: 1000;
        max-width: 300px;
    `;
    successDiv.textContent = message;
    document.body.appendChild(successDiv);

    setTimeout(() => {
        document.body.removeChild(successDiv);
    }, 3000);
}

export function toggleChartSettings() {
    const settingsContent = document.getElementById('chart-settings');
    const toggleBtn = document.getElementById('settings-toggle');
    const toggleIcon = toggleBtn.querySelector('.settings-toggle-icon');

    if (settingsContent && toggleBtn && toggleIcon) {
        if (settingsContent.classList.contains('expanded')) {
            settingsContent.classList.remove('expanded');
            toggleBtn.classList.add('collapsed');
            toggleIcon.textContent = '▶';
        } else {
            settingsContent.classList.add('expanded');
            toggleBtn.classList.remove('collapsed');
            toggleIcon.textContent = '▼';
        }
    }
}