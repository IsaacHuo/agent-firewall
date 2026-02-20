import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const here = path.dirname(fileURLToPath(import.meta.url));

function normalizeBase(input: string): string {
  const trimmed = input.trim();
  if (!trimmed) {
    return "/";
  }
  if (trimmed === "./") {
    return "./";
  }
  if (trimmed.endsWith("/")) {
    return trimmed;
  }
  return `${trimmed}/`;
}

export default defineConfig(({ command }) => {
  const envBase = process.env.AGENT_SHIELD_CONTROL_UI_BASE_PATH?.trim();
  const base = envBase ? normalizeBase(envBase) : "./";

  // In dev mode, auto-read the gateway token from config file so the UI can connect.
  // Reads directly from JSON to avoid shell/ANSI issues with `openclaw config get`.
  if (command === "serve" && !process.env.VITE_DEV_GATEWAY_TOKEN) {
    try {
      const home = process.env.HOME ?? "";
      const configPath = path.join(home, ".openclaw", "openclaw.json");
      const config = JSON.parse(fs.readFileSync(configPath, "utf-8"));
      const token = config?.gateway?.auth?.token;
      if (typeof token === "string" && token.trim()) {
        process.env.VITE_DEV_GATEWAY_TOKEN = token.trim();
      }
    } catch {
      // config not found — no token
    }
  }

  const _devToken = process.env.VITE_DEV_GATEWAY_TOKEN ?? "";

  const gatewayPort = 18789;

  return {
    base,
    publicDir: path.resolve(here, "public"),
    optimizeDeps: {
      include: ["lit/directives/repeat.js"],
    },
    build: {
      outDir: path.resolve(here, "../dist/control-ui"),
      emptyOutDir: true,
      sourcemap: true,
    },
    server: {
      host: true,
      port: 5173,
      strictPort: true,
      // Proxy WebSocket connections to the gateway so the browser can connect
      // via the same Vite origin — no CORS/origin issues, no port mismatch.
      proxy:
        command === "serve"
          ? {
              "/_gw": {
                target: `ws://localhost:${gatewayPort}`,
                ws: true,
                rewriteWsOrigin: true,
                rewrite: (p) => p.replace(/^\/_gw/, ""),
              },
            }
          : undefined,
    },
  };
});
