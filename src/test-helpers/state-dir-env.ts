import { captureEnv } from "../test-utils/env.js";

export function snapshotStateDirEnv() {
  return captureEnv(["AGENT_SHIELD_STATE_DIR", "CLAWDBOT_STATE_DIR"]);
}

export function restoreStateDirEnv(snapshot: ReturnType<typeof snapshotStateDirEnv>): void {
  snapshot.restore();
}

export function setStateDirEnv(stateDir: string): void {
  process.env.AGENT_SHIELD_STATE_DIR = stateDir;
  delete process.env.CLAWDBOT_STATE_DIR;
}
