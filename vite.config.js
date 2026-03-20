import { defineConfig } from "vite";
import { resolve } from "path";
import { codecovVitePlugin } from "@codecov/vite-plugin";

export default defineConfig({
  base: "./",
  build: {
    outDir: "frontend/static/dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        app: resolve(__dirname, "frontend/static/js/app.js"),
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "[name].js",
        assetFileNames: "[name].[ext]",
      },
    },
  },
  plugins: [
    codecovVitePlugin({
      enableBundleAnalysis: process.env.CODECOV_TOKEN !== undefined,
      bundleName: "ecc-sheet",
      uploadToken: process.env.CODECOV_TOKEN,
    }),
  ],
});
