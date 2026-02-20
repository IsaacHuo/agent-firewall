// In dev mode, ensure localStorage has the gateway token and correct URL
// before any UI modules load. This runs on every page load / HMR reconnect.
if (import.meta.env.DEV) {
  const devToken = import.meta.env.VITE_DEV_GATEWAY_TOKEN;
  if (devToken) {
    try {
      const K = "agent-shield.control.settings.v1";
      const s = JSON.parse(localStorage.getItem(K) || "{}");
      let dirty = false;
      if (!s.token || !s.token.trim()) {
        s.token = devToken;
        dirty = true;
      }
      const wsu = `ws://${location.hostname}:18789`;
      if (!s.gatewayUrl || /^wss?:\/\/localhost:5173\/?$/.test(s.gatewayUrl)) {
        s.gatewayUrl = wsu;
        dirty = true;
      }
      if (dirty) {
        localStorage.setItem(K, JSON.stringify(s));
      }
    } catch {
      // ignore
    }
  }
}

import "./styles.css";
import "./ui/app.ts";
