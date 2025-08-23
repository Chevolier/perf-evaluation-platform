// Token management module
import { STATE, CONFIG, getApiUrl } from './config.js';
import { updateModelCheckboxStates, showError } from './ui.js';

export async function loadTokenParameters() {
    if (!STATE.currentSelection) return;

    try {
        const response = await fetch(getApiUrl(`/api/parameters?runtime=${encodeURIComponent(STATE.currentSelection.runtime)}&instance_type=${encodeURIComponent(STATE.currentSelection.instance_type)}&model_name=${encodeURIComponent(STATE.currentSelection.model_name)}`));
        const params = await response.json();

        preserveTokenSelections(params);
        updateModelCheckboxStates();
    } catch (error) {
        console.error('Failed to load parameters:', error);
        showError('Failed to load parameters: ' + error.message);
        enableSlidersWithDefaults();
    }
}

export function preserveTokenSelections(newParams) {
    const sliders = [
        { id: 'input-tokens', key: 'input_tokens', valueId: 'input-tokens-value' },
        { id: 'output-tokens', key: 'output_tokens', valueId: 'output-tokens-value' },
        { id: 'random-tokens', key: 'random_tokens', valueId: 'random-tokens-value' }
    ];

    sliders.forEach(slider => {
        const sliderElement = document.getElementById(slider.id);
        const valueElement = document.getElementById(slider.valueId);
        const values = newParams[slider.key];

        if (values && values.length > 0) {
            const minVal = Math.min(...values);
            const maxVal = Math.max(...values);

            sliderElement.disabled = false;
            sliderElement.min = minVal;
            sliderElement.max = maxVal;

            const currentValue = parseInt(sliderElement.value);
            if (currentValue >= minVal && currentValue <= maxVal && values.includes(currentValue)) {
                sliderElement.value = currentValue;
            } else {
                let defaultValue;
                if (slider.id === 'input-tokens') {
                    defaultValue = values.includes(1600) ? 1600 : values[0];
                } else if (slider.id === 'output-tokens') {
                    defaultValue = values.includes(400) ? 400 : values[0];
                } else if (slider.id === 'random-tokens') {
                    defaultValue = values.includes(1600) ? 1600 : values[0];
                } else {
                    defaultValue = values[0];
                }
                sliderElement.value = defaultValue;
            }

            valueElement.textContent = sliderElement.value;
            sliderElement.availableValues = values;

            if (slider.id === 'random-tokens') {
                sliderElement.originalAvailableValues = [...values];
            }
        } else {
            sliderElement.disabled = true;
            sliderElement.value = 0;
            valueElement.textContent = '-';
            sliderElement.availableValues = [];
        }
    });

    setupSliderEventListeners();
    updateRandomTokensMax();
}

export function enableSlidersWithDefaults() {
    CONFIG.DEFAULT_SLIDERS.forEach(slider => {
        const sliderElement = document.getElementById(slider.id);
        const valueElement = document.getElementById(slider.id + '-value');

        sliderElement.disabled = false;
        sliderElement.min = slider.min;
        sliderElement.max = slider.max;
        sliderElement.value = slider.default;
        valueElement.textContent = slider.default;

        sliderElement.availableValues = [];
        for (let i = slider.min; i <= slider.max; i += 100) {
            sliderElement.availableValues.push(i);
        }
    });

    setupSliderEventListeners();
    updateRandomTokensMax();
}

export function setupSliderEventListeners() {
    const inputTokensSlider = document.getElementById('input-tokens');
    const outputTokensSlider = document.getElementById('output-tokens');
    const randomTokensSlider = document.getElementById('random-tokens');

    // Remove existing event listeners to avoid duplicates
    inputTokensSlider.oninput = null;
    outputTokensSlider.oninput = null;
    randomTokensSlider.oninput = null;

    // Input tokens slider
    inputTokensSlider.addEventListener('input', function () {
        if (this.disabled) return;
        let value = parseInt(this.value);
        if (this.availableValues && this.availableValues.length > 0) {
            value = findClosestAvailableValue(this.value, this.availableValues);
            this.value = value;
        }
        document.getElementById('input-tokens-value').textContent = value;
        updateRandomTokensMax();
        updateCheckedModelCombinations();
    });

    // Output tokens slider
    outputTokensSlider.addEventListener('input', function () {
        if (this.disabled) return;
        let value = parseInt(this.value);
        if (this.availableValues && this.availableValues.length > 0) {
            value = findClosestAvailableValue(this.value, this.availableValues);
            this.value = value;
        }
        document.getElementById('output-tokens-value').textContent = value;
        updateCheckedModelCombinations();
    });

    // Random tokens slider
    randomTokensSlider.addEventListener('input', function () {
        if (this.disabled) return;
        let value = parseInt(this.value);
        if (this.availableValues && this.availableValues.length > 0) {
            value = findClosestAvailableValue(this.value, this.availableValues);
            this.value = value;
        }
        document.getElementById('random-tokens-value').textContent = value;
        updateCheckedModelCombinations();
    });
}

export function findClosestAvailableValue(targetValue, availableValues) {
    if (!availableValues || availableValues.length === 0) return targetValue;

    const target = parseInt(targetValue);
    return availableValues.reduce((prev, curr) => {
        return Math.abs(curr - target) < Math.abs(prev - target) ? curr : prev;
    });
}

export function disableTokenSliders() {
    CONFIG.DEFAULT_SLIDERS.forEach(slider => {
        const sliderElement = document.getElementById(slider.id);
        const valueElement = document.getElementById(slider.id + '-value');
        
        sliderElement.disabled = true;
        sliderElement.value = slider.default;
        valueElement.textContent = slider.default;
    });

    const addChartBtn = document.getElementById('add-chart-btn');
    if (addChartBtn) {
        addChartBtn.disabled = true;
    }
}

export function updateRandomTokensMax() {
    const inputTokensSlider = document.getElementById('input-tokens');
    const randomTokensSlider = document.getElementById('random-tokens');
    const randomTokensValue = document.getElementById('random-tokens-value');

    if (!inputTokensSlider.disabled && !randomTokensSlider.disabled) {
        const inputTokensValue = parseInt(inputTokensSlider.value);
        const originalAvailableValues = randomTokensSlider.originalAvailableValues || randomTokensSlider.availableValues || [];
        const filteredValues = originalAvailableValues.filter(val => val <= inputTokensValue);

        if (filteredValues.length > 0) {
            const newMin = Math.min(...filteredValues);
            const newMax = Math.max(...filteredValues);

            randomTokensSlider.min = newMin;
            randomTokensSlider.max = newMax;
            randomTokensSlider.disabled = false;
            randomTokensSlider.availableValues = filteredValues;

            const currentValue = parseInt(randomTokensSlider.value);
            let needsAdjustment = false;
            let newValue = currentValue;

            if (currentValue > inputTokensValue) {
                newValue = Math.max(...filteredValues);
                needsAdjustment = true;
            } else if (currentValue > newMax || currentValue < newMin) {
                newValue = Math.min(Math.max(currentValue, newMin), newMax);
                needsAdjustment = true;
            } else if (!filteredValues.includes(currentValue)) {
                newValue = findClosestAvailableValue(currentValue, filteredValues);
                needsAdjustment = true;
            }

            if (needsAdjustment) {
                randomTokensSlider.value = newValue;
                randomTokensValue.textContent = newValue;
            }
        } else {
            randomTokensSlider.disabled = true;
            randomTokensValue.textContent = '-';
        }
    }
}

function updateCheckedModelCombinations() {
    if (!STATE.currentSelection) return;

    const inputTokens = parseInt(document.getElementById('input-tokens').value);
    const outputTokens = parseInt(document.getElementById('output-tokens').value);
    const randomTokens = parseInt(document.getElementById('random-tokens').value);

    const currentModelCheckbox = document.querySelector('.tree-item.selected .tree-checkbox');
    const exactConfigExists = STATE.selectedCombinations.some(c =>
        c.runtime === STATE.currentSelection.runtime &&
        c.instance_type === STATE.currentSelection.instance_type &&
        c.model_name === STATE.currentSelection.model_name &&
        c.input_tokens === inputTokens &&
        c.output_tokens === outputTokens &&
        c.random_tokens === randomTokens
    );

    if (currentModelCheckbox) {
        currentModelCheckbox.checked = exactConfigExists;
    }
}