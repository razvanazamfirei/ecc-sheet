/** @type {import('jest').Config} */
export default {
    testEnvironment: "node",
    roots: ["<rootDir>/frontend/static/js"],
    testMatch: ["**/__tests__/**/*.js", "**/*.test.js"],
    collectCoverageFrom: [
        "frontend/static/js/**/*.js",
        "!frontend/static/js/**/*.test.js",
        "!frontend/static/js/__tests__/**",
        "!frontend/static/js/vendor.js",
    ],
    coverageDirectory: "coverage/frontend",
    coverageReporters: ["text", "lcov", "cobertura"],
    transform: {},
    moduleFileExtensions: ["js"],
};
