import js from "@eslint/js";
import react from "eslint-plugin-react";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: { ...globals.browser } },
    plugins: { react },
    settings: { react: { version: "18" } },
    rules: {
      "react/no-danger": "error",
      // CSP (style-src 'self') blokuje atrybut style=; style tylko w styles.css.
      "react/forbid-dom-props": ["error", { forbid: ["style"] }],
    },
  },
);
