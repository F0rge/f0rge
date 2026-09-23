module.exports = {
  transform: {
    "^.+\\.[jt]s$": ["@swc/jest", { jsc: { parser: { syntax: "typescript" } } }],
  },
  testEnvironment: "node",
  testMatch: ["**/src/**/*.test.ts"],
  modulePathIgnorePatterns: ["<rootDir>/.medusa/"],
};
