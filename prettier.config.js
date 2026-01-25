const config = {
  trailingComma: "all",
  plugins: ["prettier-plugin-jinja-template"],
  quoteProps: "consistent",
  bracketSameLine: true,
  useTabs: false,
  singleAttributePerLine: false,
  printWidth: 80,
  proseWrap: "preserve",
  overrides: [
    {
      files: ["*.html"],
      options: {
        parser: "jinja-template",
      },
    },
    {
      files: "*.md",
      options: {
        proseWrap: "always",
        printWidth: 80,
        tabWidth: 2,
      },
    },
    {
      files: "*.toml",
      options: {
        tabWidth: 2,
      },
    },
  ],
};

export default config;
