import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Component tests only; pure-logic tests run with node --test (tests/*.test.mjs).
export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    environment: "jsdom",
    include: ["tests/components/**/*.test.tsx"],
    setupFiles: ["tests/components/setup.ts"],
    testTimeout: 20000,
    css: { modules: { classNameStrategy: "non-scoped" } },
  },
});
