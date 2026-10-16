import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  base: "./",
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      workbox: {
        navigateFallbackDenylist: [
          /^\/ws/,
          /^\/v\//,
          /^\/s\//,
          /^\/villages/,
          /^\/auth/,
          /^\/tools/,
          /^\/hooks/,
          /^\/slides\.html/,
          /^\/control\.html/
        ]
      },
      manifest: {
        name: "Village",
        short_name: "Village",
        id: "/",
        start_url: "/?source=pwa",
        display: "standalone",
        orientation: "portrait",
        background_color: "#FBF6EE",
        theme_color: "#2F6B57",
        lang: "es",
        icons: []
      }
    })
  ],
  // CORE_PROXY=http://localhost:8790 npm run dev → same-origin /ws and REST to a live Core (no CORS needed)
  server: process.env.CORE_PROXY
    ? {
        proxy: Object.fromEntries(
          ["/villages", "/clock", "/auth", "/verifications", "/health"].map((p) => [p, { target: process.env.CORE_PROXY, changeOrigin: true }]).concat([
            ["/ws", { target: process.env.CORE_PROXY!.replace(/^http/, "ws"), ws: true, changeOrigin: true } as any]
          ])
        )
      }
    : undefined,
  build: {
    rollupOptions: {
      input: {
        index: resolve(__dirname, "index.html"),
        join: resolve(__dirname, "join.html"),
        control: resolve(__dirname, "control.html")
      }
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
    css: true
  }
});
