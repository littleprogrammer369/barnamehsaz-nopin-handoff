import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Vite dev-server proxy: browser calls the same-origin /api/v1 prefix and
// Vite forwards to the backend URL configured via env. This keeps the browser
// code free of hardcoded hostnames (09 / Phase 5 constraint).
const apiTarget = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";
const apiPrefix = process.env.VITE_API_PREFIX ?? "/api/v1";

export default defineConfig({
  base: '/barnamehsaz/',
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      [apiPrefix]: {
        target: apiTarget,
        changeOrigin: true,
        // strip nothing: backend already serves under the same prefix
      },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      [apiPrefix]: {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    css: false,
  },
} as any);
