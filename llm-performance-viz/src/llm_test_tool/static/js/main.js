// Main application module
import { Analytics } from './analytics.js';
import { STATE } from './config.js';
import { loadTreeStructure, filterTree } from './tree.js';
import { disableTokenSliders, setupSliderEventListeners } from './tokens.js';
import { generateCharts, updateComparisonList, clearCharts, updateUrlWithState, showAllCharts, hideAllCharts } from './charts.js';
import { showError, showSuccess, toggleChartSettings, updateModelCheckboxStates, updateSelectedInfo } from './ui.js';
import { findNodeFromTreeItem } from './tree.js';

// Initialize analytics
export const analytics = new Analytics();

// Initialize the application
async function init() {
    try {
        await loadTreeStructure();
        setupFilterEventListeners();
        disableTokenSliders();
        setupSliderEventListeners();

        setTimeout(() => {
            restoreStateFromUrl();
        }, 500);
    } catch (error) {
        showError('Failed to initialize application: ' + error.message);
    }
}

// Setup filter event listeners
function setupFilterEventListeners() {
    const filterInput = document.getElementById('tree-filter');
    const filterClear = document.getElementById('filter-clear');
    const refreshBtn = document.getElementById('refresh-tree');

    if (filterInput) {
        filterInput.addEventListener('input', function () {
            const filterText = this.value.trim();
            filterTree(filterText);

            if (filterText && filterClear) {
                filterClear.style.display = 'flex';
            } else if (filterClear) {
                filterClear.style.display = 'none';
            }

            updateUrlWithState();
        });
    }

    if (filterClear) {
        filterClear.addEventListener('click', function () {
            if (filterInput) {
                filterInput.value = '';
                filterTree('');
                filterInput.focus();
            }
            this.style.display = 'none';
            updateUrlWithState();
        });
    }

    if (refreshBtn) {
        refreshBtn.addEventListener('click', async function () {
            await refreshTreeData();
        });
    }

    if (filterClear) {
        filterClear.style.display = 'none';
    }

    const settingsToggle = document.getElementById('settings-toggle');
    if (settingsToggle) {
        settingsToggle.addEventListener('click', function (e) {
            e.preventDefault();
            toggleChartSettings();
        });
    }
}

// Refresh tree data from disk
async function refreshTreeData() {
    const refreshBtn = document.getElementById('refresh-tree');
    const refreshIcon = refreshBtn.querySelector('.refresh-icon');

    try {
        refreshBtn.classList.add('loading');
        refreshBtn.disabled = true;

        STATE.currentSelection = null;
        STATE.selectedCombinations = [];
        updateSelectedInfo();
        updateComparisonList();
        clearCharts();
        disableTokenSliders();

        await loadTreeStructure(true);

        const filterInput = document.getElementById('tree-filter');
        if (filterInput.value) {
            filterInput.value = '';
            filterTree('');
            document.getElementById('filter-clear').style.display = 'none';
        }

        document.querySelectorAll('.tree-checkbox').forEach(checkbox => {
            checkbox.checked = false;
            checkbox.disabled = false;
        });

        console.log('Tree data refreshed successfully');
    } catch (error) {
        showError('Failed to refresh tree data: ' + error.message);
    } finally {
        refreshBtn.classList.remove('loading');
        refreshBtn.disabled = false;
    }
}

// Add current selection to chart comparison
function addCurrentToChart() {
    if (!STATE.currentSelection) {
        showError('Please select a model first.');
        return;
    }

    const inputTokens = parseInt(document.getElementById('input-tokens').value);
    const outputTokens = parseInt(document.getElementById('output-tokens').value);
    const randomTokens = parseInt(document.getElementById('random-tokens').value);

    const combination = {
        runtime: STATE.currentSelection.runtime,
        instance_type: STATE.currentSelection.instance_type,
        model_name: STATE.currentSelection.model_name,
        input_tokens: inputTokens,
        output_tokens: outputTokens,
        random_tokens: randomTokens
    };

    const exists = STATE.selectedCombinations.some(c =>
        c.runtime === combination.runtime &&
        c.instance_type === combination.instance_type &&
        c.model_name === combination.model_name &&
        c.input_tokens === combination.input_tokens &&
        c.output_tokens === combination.output_tokens &&
        c.random_tokens === combination.random_tokens
    );

    if (exists) {
        showError('This model with these token settings is already in the comparison.');
        return;
    }

    STATE.selectedCombinations.push(combination);
    updateComparisonList();
    generateCharts();
    updateUrlWithState();
    updateModelCheckboxStates();

    analytics.logEvent('chart_added_successfully', combination);
    showSuccess('Model added to comparison successfully!');
}

// Remove combination from comparison list
function removeFromComparison(index) {
    const removedCombo = STATE.selectedCombinations[index];
    STATE.selectedCombinations.splice(index, 1);
    updateComparisonList();
    
    analytics.logEvent('chart_removed', removedCombo);

    const modelKey = `${removedCombo.runtime}-${removedCombo.instance_type}-${removedCombo.model_name}`;
    document.querySelectorAll('.tree-checkbox').forEach(checkbox => {
        const treeItem = checkbox.closest('.tree-item');
        const treeNode = findNodeFromTreeItem(treeItem);

        if (treeNode && `${treeNode.runtime}-${treeNode.instance_type}-${treeNode.model_name}` === modelKey) {
            checkbox.checked = false;
        }
    });

    if (STATE.selectedCombinations.length > 0) {
        generateCharts();
    } else {
        clearCharts();
    }

    updateUrlWithState();
}

// Clear all combinations
function clearComparison() {
    STATE.selectedCombinations = [];
    updateComparisonList();
    clearCharts();

    document.querySelectorAll('.tree-checkbox').forEach(checkbox => {
        checkbox.checked = false;
    });

    STATE.currentSelection = null;
    updateSelectedInfo();
    disableTokenSliders();
    updateUrlWithState();
}

// Export data functionality
function exportData() {
    if (STATE.selectedCombinations.length === 0) {
        showError('No data to export. Please select some models first.');
        return;
    }

    if (!window.currentChartData) {
        showError('No chart data available. Please wait for charts to load.');
        return;
    }

    const csvContent = generateCSV(window.currentChartData);
    const dataBlob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(dataBlob);

    const link = document.createElement('a');
    link.href = url;
    const now = new Date();
    const timestamp = now.toISOString().replace(/[:.]/g, '-').replace('T', '_').split('.')[0];
    link.download = `llm-performance-data-${timestamp}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    // Log export event
    analytics.logEvent('data_exported', {
        combinations_count: STATE.selectedCombinations.length,
        total_data_points: window.currentChartData.reduce((total, item) => total + item.data.length, 0)
    });
    
    showSuccess('Data exported successfully!');
}

// Generate CSV content with complete performance data
function generateCSV(data) {
    let csvContent = `Export Date: ${new Date().toISOString()}\n\n`;
    
    // CSV Headers
    const headers = [
        'Runtime',
        'Instance Type', 
        'Model Name',
        'Input Tokens',
        'Output Tokens',
        'Random Tokens',
        'Processes',
        'First Token Latency Mean (ms)',
        'First Token Latency P50 (ms)',
        'First Token Latency P90 (ms)',
        'End to End Latency Mean (ms)',
        'End to End Latency P50 (ms)',
        'End to End Latency P90 (ms)',
        'Output Tokens Per Second Mean',
        'Output Tokens Per Second P50',
        'Output Tokens Per Second P90',
        'Success Rate (%)',
        'Requests Per Second',
        'Total Requests',
        'Successful Requests',
        'Failed Requests',
        'Input Throughput (tokens/sec)',
        'Output Throughput (tokens/sec)',
        'Server Throughput (tokens/sec)',
        'Cost Per Million Tokens ($)',
        'Cost Per 1K Requests ($)',
        'Cost Per Million Input Tokens ($)',
        'Cost Per Million Output Tokens ($)',
        'Instance Price Used ($/hour)'
    ];
    
    csvContent += headers.join(',') + '\n';
    
    // Add data rows
    data.forEach(item => {
        const combo = item.combination;
        
        // Sort data by processes for consistent ordering
        const sortedData = item.data.sort((a, b) => a.processes - b.processes);
        
        sortedData.forEach(record => {
            const row = [
                combo.runtime,
                combo.instance_type,
                combo.model_name,
                combo.input_tokens,
                combo.output_tokens,
                combo.random_tokens,
                record.processes,
                record.first_token_latency_mean || 0,
                record.first_token_latency_p50 || 0,
                record.first_token_latency_p90 || 0,
                record.end_to_end_latency_mean || 0,
                record.end_to_end_latency_p50 || 0,
                record.end_to_end_latency_p90 || 0,
                record.output_tokens_per_second_mean || 0,
                record.output_tokens_per_second_p50 || 0,
                record.output_tokens_per_second_p90 || 0,
                (record.success_rate * 100) || 0,
                record.requests_per_second || 0,
                record.total_requests || 0,
                record.successful_requests || 0,
                record.failed_requests || 0,
                record.input_throughput || 0,
                record.output_throughput || 0,
                record.server_throughput || 0,
                record.cost_per_million_tokens || 0,
                record.cost_per_1k_requests || 0,
                record.cost_per_million_input_tokens || 0,
                record.cost_per_million_output_tokens || 0,
                record.instance_price_used || 0
            ];
            
            // Escape any commas in the data and wrap in quotes if needed
            const escapedRow = row.map(value => {
                const stringValue = String(value);
                if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
                    return `"${stringValue.replace(/"/g, '""')}"`;
                }
                return stringValue;
            });
            
            csvContent += escapedRow.join(',') + '\n';
        });
    });
    
    return csvContent;
}

// Restore state from URL
function restoreStateFromUrl() {
    const url = new URL(window.location);

    // Restore chart visibility settings
    const chartsParam = url.searchParams.get('charts');
    if (chartsParam) {
        try {
            const chartState = JSON.parse(atob(chartsParam));
            if (chartState.visibility) {
                STATE.chartVisibility = chartState.visibility;
                if (chartState.settingsExpanded === false) {
                    setTimeout(() => {
                        const settingsContent = document.getElementById('chart-settings');
                        const toggleBtn = document.getElementById('settings-toggle');
                        const toggleIcon = toggleBtn.querySelector('.settings-toggle-icon');

                        if (settingsContent && toggleBtn && toggleIcon) {
                            settingsContent.classList.remove('expanded');
                            toggleBtn.classList.add('collapsed');
                            toggleIcon.textContent = '▶';
                        }
                    }, 100);
                }
            } else {
                STATE.chartVisibility = chartState;
            }
        } catch (error) {
            console.warn('Failed to restore chart settings from URL:', error);
        }
    }

    // Restore filter
    const filter = url.searchParams.get('filter');
    if (filter) {
        const filterInput = document.getElementById('tree-filter');
        const filterClear = document.getElementById('filter-clear');
        if (filterInput) {
            filterInput.value = filter;
            filterTree(filter);
            if (filterClear) {
                filterClear.style.display = 'flex';
            }
        }
    }

    // Restore combinations
    const combinationsParam = url.searchParams.get('combinations');
    if (combinationsParam) {
        try {
            const combinationsData = JSON.parse(atob(combinationsParam));
            const combinations = combinationsData.map(combo => ({
                runtime: combo.r,
                instance_type: combo.i,
                model_name: combo.m,
                input_tokens: combo.it,
                output_tokens: combo.ot,
                random_tokens: combo.rt
            }));

            STATE.selectedCombinations = combinations;
            updateComparisonList();

            if (STATE.selectedCombinations.length > 0) {
                generateCharts();
            }

            setTimeout(() => {
                updateModelCheckboxStates();
            }, 100);
        } catch (error) {
            console.warn('Failed to restore combinations from URL:', error);
        }
    }
}

// Expose global functions
window.addCurrentToChart = addCurrentToChart;
window.exportData = exportData;
window.clearComparison = clearComparison;

// Chart controls
window.chartControls = {
    showAllCharts,
    hideAllCharts,
    removeFromComparison
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', init);