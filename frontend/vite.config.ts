import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api → the FastAPI backend so the browser only ever
// talks to one origin (no CORS preflight in dev, cookies/headers stay simple).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
