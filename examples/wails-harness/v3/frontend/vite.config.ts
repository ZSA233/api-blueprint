import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";

const examplesRoot = fileURLToPath(new URL("../../../", import.meta.url));

export default defineConfig({
  build: {
    emptyOutDir: true,
    outDir: "dist",
    target: "es2022",
  },
  server: {
    fs: {
      allow: [examplesRoot],
    },
  },
});
