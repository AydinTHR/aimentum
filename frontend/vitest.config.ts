import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Kept separate from vite.config.ts so the test run does not drag in the PWA
// plugin, which would try to build a service worker for every test.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
