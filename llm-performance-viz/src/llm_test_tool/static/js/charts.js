// Charts management module
import { STATE, CONFIG, getApiUrl } from './config.js';
import { showLoading, clearError, showError } from './ui.js';

export async function generateCharts() {
    if (STATE.selectedCombinations.length === 0) {
        clearCharts();
        return;
    }

    showLoading(true);
    clearError();

    try {
        const response = await fetch(getApiUrl('/api/comparison-data'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                combinations: STATE.selectedCombinations
            })
        });

        const data = await response.json();
        createCharts(data);
    } catch (error) {
        showError('Failed to generate charts: ' + error.message);
    } finally {
        showLoading(false);
    }
}

export function createCharts(data) {
    clearCharts();
    window.currentChartData = data;

    const container = document.getElementById('charts-container');

    if (Object.keys(STATE.chartVisibility).length === 0) {
        initializeChartSettings(CONFIG.CHART_TYPES);
    }

    CONFIG.CHART_TYPES.forEach(chartType => {
        if (STATE.chartVisibility[chartType.id] !== false) {
            const wrapper = document.createElement('div');
            wrapper.className = 'chart-wrapper';
            wrapper.id = `wrapper-${chartType.id}`;
            wrapper.innerHTML = `
                <div class="chart-title">${chartType.title}</div>
                <div class="chart-container">
                    <canvas id="${chartType.id}"></canvas>
                </div>
            `;
            container.appendChild(wrapper);

            createChart(chartType.id, chartType.title, chartType.metric, chartType.unit, data);
        }
    });
}

export function createChart(canvasId, title, metric, unit, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    const datasets = data.map((item, index) => {
        const combo = item.combination;
        const chartData = item.data.sort((a, b) => a.processes - b.processes);

        const processedData = chartData.map(d => ({
            x: d.processes,
            y: metric === 'success_rate' ? d[metric] * 100 : d[metric]
        }));

        const runtimeName = combo.runtime;
        const instanceSize = combo.instance_type.includes('4xlarge') ? '4x' :
            combo.instance_type.includes('48xlarge') ? '48x' :
                combo.instance_type.split('.')[1] || combo.instance_type;
        const instanceBase = combo.instance_type.split('.')[0];
        const instanceInfo = `${instanceBase}.${instanceSize}`;
        const modelName = combo.model_name;
        const tokenInfo = `${combo.input_tokens}(${combo.random_tokens})->${combo.output_tokens}`;
        const label = `${runtimeName}/${instanceInfo}/${modelName} ${tokenInfo}`;

        return {
            label: label,
            data: processedData,
            borderColor: CONFIG.COLORS[index % CONFIG.COLORS.length],
            backgroundColor: CONFIG.COLORS[index % CONFIG.COLORS.length] + '20',
            borderWidth: 2,
            fill: false,
            tension: 0.1
        };
    });

    STATE.charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 8,
                        font: { size: 9 },
                        boxWidth: 8,
                        maxWidth: 300
                    }
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: {
                        display: true,
                        text: 'Concurrent Processes'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: `${title.split(' vs ')[0]} (${unit})`
                    },
                    ...(metric === 'success_rate' && {
                        min: 0,
                        max: 100
                    })
                }
            }
        }
    });
}

export function clearCharts() {
    Object.values(STATE.charts).forEach(chart => {
        if (chart) {
            chart.destroy();
        }
    });
    STATE.charts = {};
    document.getElementById('charts-container').innerHTML = '';
    window.currentChartData = null;
}

export function initializeChartSettings(chartTypes) {
    const settingsContainer = document.getElementById('chart-settings');

    chartTypes.forEach(chartType => {
        if (STATE.chartVisibility[chartType.id] === undefined) {
            STATE.chartVisibility[chartType.id] = true;
        }
    });

    settingsContainer.innerHTML = '';
    chartTypes.forEach(chartType => {
        const setting = document.createElement('div');
        setting.className = 'chart-setting';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `chart-${chartType.id}`;
        checkbox.checked = STATE.chartVisibility[chartType.id];
        checkbox.addEventListener('change', () => toggleChart(chartType.id));

        const label = document.createElement('label');
        label.htmlFor = `chart-${chartType.id}`;
        label.textContent = chartType.title.replace(' vs Concurrency', '');

        setting.appendChild(checkbox);
        setting.appendChild(label);
        settingsContainer.appendChild(setting);
    });

    const buttonsDiv = document.createElement('div');
    buttonsDiv.className = 'chart-settings-buttons';
    buttonsDiv.innerHTML = `
        <button onclick="window.chartControls.showAllCharts()">Show All</button>
        <button onclick="window.chartControls.hideAllCharts()">Hide All</button>
    `;
    settingsContainer.appendChild(buttonsDiv);
}

export function toggleChart(chartId) {
    STATE.chartVisibility[chartId] = !STATE.chartVisibility[chartId];
    
    const checkbox = document.getElementById(`chart-${chartId}`);
    if (checkbox) {
        checkbox.checked = STATE.chartVisibility[chartId];
    }
    
    if (STATE.selectedCombinations.length > 0) {
        generateCharts();
    }
    
    updateUrlWithState();
}

export function showAllCharts() {
    Object.keys(STATE.chartVisibility).forEach(chartId => {
        STATE.chartVisibility[chartId] = true;
        const checkbox = document.getElementById(`chart-${chartId}`);
        if (checkbox) {
            checkbox.checked = true;
        }
    });
    
    if (STATE.selectedCombinations.length > 0) {
        generateCharts();
    }
    updateUrlWithState();
}

export function hideAllCharts() {
    Object.keys(STATE.chartVisibility).forEach(chartId => {
        STATE.chartVisibility[chartId] = false;
        const checkbox = document.getElementById(`chart-${chartId}`);
        if (checkbox) {
            checkbox.checked = false;
        }
    });
    
    if (STATE.selectedCombinations.length > 0) {
        generateCharts();
    }
    updateUrlWithState();
}

export function updateComparisonList() {
    const listContainer = document.getElementById('comparison-list');
    const itemsContainer = document.getElementById('comparison-items');

    if (STATE.selectedCombinations.length === 0) {
        listContainer.style.display = 'none';
        return;
    }

    listContainer.style.display = 'block';
    itemsContainer.innerHTML = '';

    STATE.selectedCombinations.forEach((combo, index) => {
        const item = document.createElement('div');
        item.className = 'comparison-item';
        item.innerHTML = `
            <span>${combo.runtime} - ${combo.instance_type} - ${combo.model_name} 
            (in:${combo.input_tokens}, out:${combo.output_tokens}, rand:${combo.random_tokens})</span>
            <button class="remove-btn" onclick="window.chartControls.removeFromComparison(${index})">Remove</button>
        `;
        itemsContainer.appendChild(item);
    });
}

export function updateUrlWithState() {
    const url = new URL(window.location);

    url.searchParams.delete('combinations');
    url.searchParams.delete('filter');
    url.searchParams.delete('charts');

    if (STATE.selectedCombinations.length > 0) {
        const combinationsData = STATE.selectedCombinations.map(combo => ({
            r: combo.runtime,
            i: combo.instance_type,
            m: combo.model_name,
            it: combo.input_tokens,
            ot: combo.output_tokens,
            rt: combo.random_tokens
        }));
        url.searchParams.set('combinations', btoa(JSON.stringify(combinationsData)));
    }

    const filterInput = document.getElementById('tree-filter');
    if (filterInput && filterInput.value.trim()) {
        url.searchParams.set('filter', filterInput.value.trim());
    }

    const hiddenCharts = Object.keys(STATE.chartVisibility).filter(chartId => STATE.chartVisibility[chartId] === false);
    const settingsContent = document.getElementById('chart-settings');
    const settingsCollapsed = settingsContent && !settingsContent.classList.contains('expanded');

    if (hiddenCharts.length > 0 || settingsCollapsed) {
        const chartState = {
            visibility: STATE.chartVisibility,
            settingsExpanded: !settingsCollapsed
        };
        url.searchParams.set('charts', btoa(JSON.stringify(chartState)));
    }

    window.history.replaceState({}, '', url);
}