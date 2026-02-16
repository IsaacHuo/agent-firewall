import { afterEach, beforeEach } from "vitest";
import { AgentShieldApp } from "../app.ts";

// oxlint-disable-next-line typescript/unbound-method
const originalConnect = AgentShieldApp.prototype.connect;

export function mountApp(pathname: string) {
  window.history.replaceState({}, "", pathname);
  const app = document.createElement("agent-shield-app") as AgentShieldApp;
  document.body.append(app);
  return app;
}

export function registerAppMountHooks() {
  beforeEach(() => {
    AgentShieldApp.prototype.connect = () => {
      // no-op: avoid real gateway WS connections in browser tests
    };
    window.__AGENT_SHIELD_CONTROL_UI_BASE_PATH__ = undefined;
    localStorage.clear();
    document.body.innerHTML = "";
  });

  afterEach(() => {
    AgentShieldApp.prototype.connect = originalConnect;
    window.__AGENT_SHIELD_CONTROL_UI_BASE_PATH__ = undefined;
    localStorage.clear();
    document.body.innerHTML = "";
  });
}
