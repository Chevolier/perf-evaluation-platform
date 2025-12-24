const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:5000',
      changeOrigin: true,
      // Disable response buffering for streaming
      onProxyRes: function(proxyRes, req, res) {
        // Disable buffering for SSE/streaming responses
        proxyRes.headers['X-Accel-Buffering'] = 'no';
        proxyRes.headers['Cache-Control'] = 'no-cache';
        proxyRes.headers['Connection'] = 'keep-alive';
      },
      // Disable request buffering
      onProxyReq: function(proxyReq, req, res) {
        // Ensure streaming works properly
        proxyReq.setHeader('Accept', 'text/event-stream');
      }
    })
  );
};
