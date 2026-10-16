import { defineConfig } from "vite";

// base './' so Core can serve dist/ under /v/{village}/r/{rev}/ without rewriting asset URLs.
export default defineConfig({
  base: "./",
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false },
  test: { environment: "node", include: ["tests/**/*.test.ts"], reporters: ["default"] },
});
