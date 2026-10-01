import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Pinned rather than left to auto-increment: the backend's CORS allowlist
    // names this exact origin, so a drifting port would break every API call
    // while the dev server still looked healthy.
    port: 5174,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
    globals: true,
  },
});
