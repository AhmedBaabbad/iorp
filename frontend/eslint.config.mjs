import { FlatCompat } from "@eslint/eslintrc";
import { defineConfig, globalIgnores } from "eslint/config";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const compat = new FlatCompat({
  baseDirectory: __dirname,
});

export default defineConfig([
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  globalIgnores([
    ".next/**",
    ".next-*/**", // alternate build outputs (QA runs); never source
    "next-env.d.ts",
    "node_modules/**",
  ]),
]);
