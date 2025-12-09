import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  base: './',
  build: {
    outDir: 'frontend/static/dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        // Main vendor bundle
        vendor: resolve(__dirname, 'frontend/static/js/vendor.js'),
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: '[name].js',
        assetFileNames: '[name].[ext]'
      }
    }
  }
});
