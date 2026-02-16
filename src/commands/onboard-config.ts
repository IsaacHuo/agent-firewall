import type { AgentShieldConfig } from "../config/config.js";

export function applyOnboardingLocalWorkspaceConfig(
  baseConfig: AgentShieldConfig,
  workspaceDir: string,
): AgentShieldConfig {
  return {
    ...baseConfig,
    agents: {
      ...baseConfig.agents,
      defaults: {
        ...baseConfig.agents?.defaults,
        workspace: workspaceDir,
      },
    },
    gateway: {
      ...baseConfig.gateway,
      mode: "local",
    },
  };
}
