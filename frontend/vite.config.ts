import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Long-lived vendor libraries get their own chunks so (a) no single chunk exceeds
// the 500 kB warning threshold and (b) app-code deploys do not invalidate the
// browser cache for React / Recharts / lightweight-charts.
const VENDOR_CHUNKS: Array<[string, RegExp]> = [
  ['vendor-react', /[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/],
  ['vendor-charts', /[\\/]node_modules[\\/](lightweight-charts|fancy-canvas)[\\/]/],
  [
    'vendor-recharts',
    /[\\/]node_modules[\\/](recharts|recharts-scale|d3-[^\\/]+|internmap|victory-vendor|lodash|react-smooth|eventemitter3|decimal\.js-light|tiny-invariant|clsx|react-is|prop-types|fast-equals|dom-helpers|@babel)[\\/]/,
  ],
  ['vendor-icons', /[\\/]node_modules[\\/]lucide-react[\\/]/],
];

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          for (const [name, pattern] of VENDOR_CHUNKS) {
            if (pattern.test(id)) return name;
          }
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
