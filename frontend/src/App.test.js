/**
 * @jest-environment jsdom
 */
import { render, waitFor } from '@testing-library/react';
import App from './App';

// Disable act environment checks for this complex async component
global.IS_REACT_ACT_ENVIRONMENT = false;

jest.useFakeTimers();

test('renders application header', async () => {
  const { container } = render(<App />);
  
  // Run pending timers and promises
  await waitFor(() => {
    jest.runAllTimers();
  }, { timeout: 100 });
  
  // Check that the header with title exists (renders synchronously)
  const title = container.querySelector('h2');
  expect(title).toBeTruthy();
  expect(title.textContent).toMatch(/大模型性能评测平台/);
});
