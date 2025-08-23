// Tree management module
import { STATE, getApiUrl } from './config.js';
import { analytics } from './main.js';
import { updateSelectedInfo, updateModelCheckboxStates } from './ui.js';
import { loadTokenParameters } from './tokens.js';
import { updateComparisonList, generateCharts, clearCharts, updateUrlWithState } from './charts.js';

export async function loadTreeStructure(reload = false) {
    const url = reload ? getApiUrl('/api/tree-structure?reload=true') : getApiUrl('/api/tree-structure');
    const response = await fetch(url);
    const data = await response.json();
    STATE.treeData = data.tree;
    renderTree();
}

export function renderTree() {
    const treeContainer = document.getElementById('runtime-tree');
    treeContainer.innerHTML = '';

    STATE.treeData.forEach(runtimeNode => {
        const runtimeElement = createTreeNode(runtimeNode, 0);
        treeContainer.appendChild(runtimeElement);
    });
}

export function createTreeNode(node, level) {
    const li = document.createElement('li');
    li.className = 'tree-node';

    const item = document.createElement('div');
    item.className = 'tree-item';
    if (node.children && node.children.length > 0) {
        item.classList.add('expandable');
    }

    const toggle = document.createElement('span');
    toggle.className = 'tree-toggle';
    if (node.children && node.children.length > 0) {
        toggle.classList.add('expanded');
    } else {
        toggle.classList.add('leaf');
    }

    const label = document.createElement('span');
    label.className = 'tree-label';
    label.textContent = node.label;

    // Add checkbox for model nodes (leaf nodes)
    let checkbox = null;
    if (node.type === 'model') {
        checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'tree-checkbox';
        checkbox.disabled = false;

        // Add checkbox event handler
        checkbox.addEventListener('change', (e) => {
            e.stopPropagation();
            handleModelCheckboxChange(node, checkbox.checked);
        });
    }

    const count = document.createElement('span');
    count.className = 'tree-count';
    count.textContent = node.count;

    item.appendChild(toggle);
    if (checkbox) {
        item.appendChild(checkbox);
    }
    item.appendChild(label);
    item.appendChild(count);

    // Store node data on the DOM element for reliable identification
    if (node.type === 'model') {
        item.dataset.nodeData = JSON.stringify({
            runtime: node.runtime,
            instance_type: node.instance_type,
            model_name: node.model_name,
            type: node.type,
            label: node.label
        });
    }

    // Add click handler
    item.addEventListener('click', (e) => {
        e.stopPropagation();
        if (e.target.classList.contains('tree-checkbox')) {
            return;
        }
        handleTreeItemClick(node, item, toggle);
    });

    li.appendChild(item);

    // Add children if they exist
    if (node.children && node.children.length > 0) {
        const childrenContainer = document.createElement('ul');
        childrenContainer.className = 'tree-children expanded';

        node.children.forEach(child => {
            const childElement = createTreeNode(child, level + 1);
            childrenContainer.appendChild(childElement);
        });

        li.appendChild(childrenContainer);
    }

    return li;
}

async function handleTreeItemClick(node, itemElement, toggleElement) {
    // Handle expansion/collapse for parent nodes
    if (node.children && node.children.length > 0) {
        const childrenContainer = itemElement.parentElement.querySelector('.tree-children');
        const isExpanded = childrenContainer.classList.contains('expanded');

        if (isExpanded) {
            childrenContainer.classList.remove('expanded');
            toggleElement.classList.remove('expanded');
            toggleElement.classList.add('collapsed');
        } else {
            childrenContainer.classList.add('expanded');
            toggleElement.classList.remove('collapsed');
            toggleElement.classList.add('expanded');
        }
    }

    // Handle selection for model nodes (leaf nodes)
    if (node.type === 'model') {
        // Clear previous selection
        document.querySelectorAll('.tree-item.selected').forEach(item => {
            item.classList.remove('selected');
        });

        // Set new selection
        itemElement.classList.add('selected');
        STATE.currentSelection = {
            runtime: node.runtime,
            instance_type: node.instance_type,
            model_name: node.model_name
        };

        // Update selected info display
        updateSelectedInfo();

        // Load token parameters for this selection
        await loadTokenParameters();
    }
}

async function handleModelCheckboxChange(node, isChecked) {
    if (isChecked) {
        const inputTokensSlider = document.getElementById('input-tokens');
        const outputTokensSlider = document.getElementById('output-tokens');
        const randomTokensSlider = document.getElementById('random-tokens');

        let inputTokens, outputTokens, randomTokens;

        if (inputTokensSlider.disabled || outputTokensSlider.disabled || randomTokensSlider.disabled) {
            inputTokens = 1600;
            outputTokens = 400;
            randomTokens = 1600;
        } else {
            inputTokens = parseInt(inputTokensSlider.value);
            outputTokens = parseInt(outputTokensSlider.value);
            randomTokens = parseInt(randomTokensSlider.value);
        }

        const combination = {
            runtime: node.runtime,
            instance_type: node.instance_type,
            model_name: node.model_name,
            input_tokens: inputTokens,
            output_tokens: outputTokens,
            random_tokens: randomTokens
        };

        // Check if combination already exists
        const exists = STATE.selectedCombinations.some(c =>
            c.runtime === combination.runtime &&
            c.instance_type === combination.instance_type &&
            c.model_name === combination.model_name &&
            c.input_tokens === combination.input_tokens &&
            c.output_tokens === combination.output_tokens &&
            c.random_tokens === combination.random_tokens
        );

        if (!exists) {
            STATE.selectedCombinations.push(combination);
            updateComparisonList();
            generateCharts();
            updateUrlWithState();
            
            // Log chart addition via checkbox
            analytics.logEvent('chart_added_successfully', combination);
        }
    } else {
        // Remove from comparison
        const modelKey = `${node.runtime}-${node.instance_type}-${node.model_name}`;
        const removedCombinations = STATE.selectedCombinations.filter(c =>
            `${c.runtime}-${c.instance_type}-${c.model_name}` === modelKey
        );
        
        STATE.selectedCombinations = STATE.selectedCombinations.filter(c =>
            `${c.runtime}-${c.instance_type}-${c.model_name}` !== modelKey
        );
        updateComparisonList();

        if (STATE.selectedCombinations.length > 0) {
            generateCharts();
        } else {
            clearCharts();
        }
        updateUrlWithState();
        
        // Log chart removal
        removedCombinations.forEach(combo => {
            analytics.logEvent('chart_removed', combo);
        });
    }
}

export function filterTree(filterText) {
    const tree = document.getElementById('runtime-tree');
    const allNodes = tree.querySelectorAll('.tree-node');

    if (!filterText) {
        allNodes.forEach(node => {
            node.classList.remove('filtered-hidden');
            const item = node.querySelector('.tree-item');
            if (item) {
                item.classList.remove('filter-match');
            }
        });
        return;
    }

    const searchText = filterText.toLowerCase();
    const matchingNodes = new Set();
    
    allNodes.forEach(node => {
        const item = node.querySelector('.tree-item');
        const label = item.querySelector('.tree-label');

        if (label && label.textContent.toLowerCase().includes(searchText)) {
            matchingNodes.add(node);
            item.classList.add('filter-match');

            // Mark all parent nodes as matching
            let parent = node.parentElement;
            while (parent && parent.classList.contains('tree-children')) {
                const parentNode = parent.parentElement;
                if (parentNode && parentNode.classList.contains('tree-node')) {
                    matchingNodes.add(parentNode);
                    parent = parentNode.parentElement;
                } else {
                    break;
                }
            }

            // Mark all child nodes as matching
            const childNodes = node.querySelectorAll('.tree-node');
            childNodes.forEach(child => matchingNodes.add(child));
        } else {
            item.classList.remove('filter-match');
        }
    });

    // Show/hide nodes based on matches
    allNodes.forEach(node => {
        if (matchingNodes.has(node)) {
            node.classList.remove('filtered-hidden');

            // Auto-expand parent nodes that contain matches
            const childrenContainer = node.querySelector('.tree-children');
            const toggle = node.querySelector('.tree-toggle');
            if (childrenContainer && toggle && !toggle.classList.contains('leaf')) {
                childrenContainer.classList.add('expanded');
                toggle.classList.remove('collapsed');
                toggle.classList.add('expanded');
            }
        } else {
            node.classList.add('filtered-hidden');
        }
    });
}

export function findNodeFromTreeItem(treeItem) {
    const nodeDataStr = treeItem.dataset.nodeData;
    if (nodeDataStr) {
        try {
            return JSON.parse(nodeDataStr);
        } catch (e) {
            console.warn('Failed to parse node data:', e);
        }
    }
    
    const label = treeItem.querySelector('.tree-label').textContent;
    
    function searchTree(nodes) {
        for (const node of nodes) {
            if (node.label === label && node.type === 'model') {
                return node;
            }
            if (node.children) {
                const found = searchTree(node.children);
                if (found) return found;
            }
        }
        return null;
    }
    
    return searchTree(STATE.treeData);
}