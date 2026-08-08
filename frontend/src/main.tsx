import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";

import App from "./App.tsx";
import "./index.css";

// Push subscriptions live on the service worker registration, so the app
// registers it at startup rather than when the owner opens Settings.
registerSW({ immediate: true });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
