// jest-dom adds custom jest matchers for asserting on DOM nodes.
import '@testing-library/jest-dom';

// Mock fetch to return valid responses
global.fetch = jest.fn((url) => {
  if (url.includes('/api/model-list')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        status: 'success',
        models: {
          bedrock: {},
          emd: {},
          external: {}
        }
      }),
    });
  }
  
  if (url.includes('/api/check-model-status')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        model_status: {}
      }),
    });
  }
  
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve({}),
  });
});

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(() => null),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock;
