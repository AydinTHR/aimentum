import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // injectManifest, not generateSW: this app's worker exists to handle
      // push, which a generated worker cannot do.
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      registerType: "autoUpdate",
      injectManifest: { globPatterns: ["**/*.{js,css,html,svg,png,woff2}"] },
      // The dev server serves the real worker so push can be tested locally
      // rather than only after a build.
      devOptions: { enabled: true, type: "module" },
      manifest: {
        name: "Aimentum",
        short_name: "Aimentum",
        description: "Your accountability agent. It reaches out to you, not the other way around.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "portrait",
        background_color: "#09090b",
        theme_color: "#09090b",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/icons/maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
    }),
  ],
});
