// Configuration and constants
export const CONFIG = {
    // Color palette for different combinations
    COLORS: [
        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
        '#FF9F40', '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384'
    ],
    
    // Chart types configuration
    CHART_TYPES: [
        { id: 'first-token-latency', title: 'First Token Latency vs Concurrency', metric: 'first_token_latency_mean', unit: 'seconds' },
        { id: 'output-tokens-per-second', title: 'Output Tokens Per Second vs Concurrency', metric: 'output_tokens_per_second_mean', unit: 'tokens/sec' },
        { id: 'server-throughput', title: 'Server Throughput vs Concurrency', metric: 'server_throughput', unit: 'total tokens/sec' },
        { id: 'end-to-end-latency', title: 'End-to-End Latency vs Concurrency', metric: 'end_to_end_latency_mean', unit: 'seconds' },
        { id: 'requests-per-second', title: 'Request Rate vs Concurrency', metric: 'requests_per_second', unit: 'requests/sec' },
        { id: 'success-rate', title: 'Success Rate vs Concurrency', metric: 'success_rate', unit: '%' },
        { id: 'cost-per-million-tokens', title: 'Cost per Million Tokens vs Concurrency', metric: 'cost_per_million_tokens', unit: '$' },
        { id: 'cost-per-1k-requests', title: 'Cost per 1k Requests vs Concurrency', metric: 'cost_per_1k_requests', unit: '$' },
        { id: 'input-throughput', title: 'Input Throughput vs Concurrency', metric: 'input_throughput', unit: 'tokens/sec' },
        { id: 'output-throughput', title: 'Output Throughput vs Concurrency', metric: 'output_throughput', unit: 'tokens/sec' },
        { id: 'cost-per-million-input-tokens', title: 'Cost per Million Input Tokens vs Concurrency', metric: 'cost_per_million_input_tokens', unit: '$' },
        { id: 'cost-per-million-output-tokens', title: 'Cost per Million Output Tokens vs Concurrency', metric: 'cost_per_million_output_tokens', unit: '$' }
    ],
    
    // Default slider values
    DEFAULT_SLIDERS: [
        { id: 'input-tokens', min: 100, max: 4000, default: 1600 },
        { id: 'output-tokens', min: 50, max: 2000, default: 400 },
        { id: 'random-tokens', min: 100, max: 4000, default: 1600 }
    ]
};

// Global state
export const STATE = {
    treeData: [],
    selectedCombinations: [],
    charts: {},
    currentSelection: null,
    chartVisibility: {}
};

// Utility functions
export function getApiUrl(endpoint) {
    const basePath = window.API_BASE_PATH || '';
    return `${basePath}${endpoint}`;
}