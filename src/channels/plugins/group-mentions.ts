// @ts-nocheck — Trimmed for security-testing edition
import type { AgentShieldConfig } from "../../config/config.js";
import type { GroupToolPolicyConfig } from "../../config/types.tools.js";

type GroupMentionParams = {
  cfg: AgentShieldConfig;
  groupId?: string | null;
  groupChannel?: string | null;
  groupSpace?: string | null;
  accountId?: string | null;
  senderId?: string | null;
  senderName?: string | null;
  senderUsername?: string | null;
  senderE164?: string | null;
};

export function resolveTelegramGroupRequireMention(): boolean | undefined {
  return undefined;
}

export function resolveWhatsAppGroupRequireMention(): boolean {
  return true;
}

export function resolveIMessageGroupRequireMention(): boolean {
  return true;
}

export function resolveDiscordGroupRequireMention(): boolean {
  return true;
}

export function resolveGoogleChatGroupRequireMention(): boolean {
  return true;
}

export function resolveGoogleChatGroupToolPolicy(): GroupToolPolicyConfig | undefined {
  return undefined;
}

export function resolveSlackGroupRequireMention(): boolean {
  return true;
}

export function resolveBlueBubblesGroupRequireMention(): boolean {
  return true;
}

export function resolveTelegramGroupToolPolicy(): GroupToolPolicyConfig | undefined {
  return undefined;
}

export function resolveWhatsAppGroupToolPolicy(): GroupToolPolicyConfig | undefined {
  return undefined;
}

export function resolveIMessageGroupToolPolicy(): GroupToolPolicyConfig | undefined {
  return undefined;
}

export function resolveDiscordGroupToolPolicy(): GroupToolPolicyConfig | undefined {
  return undefined;
}

export function resolveSlackGroupToolPolicy(): GroupToolPolicyConfig | undefined {
  return undefined;
}

export function resolveBlueBubblesGroupToolPolicy(): GroupToolPolicyConfig | undefined {
  return undefined;
}
