import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: true,
    include: ["frontend/static/js/**/*.test.js"],
    coverage: {
      provider: "v8",
      reportsDirectory: "coverage/frontend",
      reporter: ["text", "lcov", "cobertura"],
      include: ["frontend/static/js/**/*.js"],
      exclude: [
        "frontend/static/js/**/*.test.js",
        "frontend/static/js/__tests__/**",
        "frontend/static/js/vendor.js",
      ],
    },
  },
});
