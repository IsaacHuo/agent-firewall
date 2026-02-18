// @ts-nocheck — Trimmed for security-testing edition
import type { ChannelDirectoryEntry } from "./types.js";

export type DirectoryConfigParams = {
  accountId?: string | null;
  query?: string | null;
  limit?: number | null;
};

export async function listSlackDirectoryPeersFromConfig(): Promise<ChannelDirectoryEntry[]> {
  return [];
}

export async function listSlackDirectoryGroupsFromConfig(): Promise<ChannelDirectoryEntry[]> {
  return [];
}

export async function listDiscordDirectoryPeersFromConfig(): Promise<ChannelDirectoryEntry[]> {
  return [];
}

export async function listDiscordDirectoryGroupsFromConfig(): Promise<ChannelDirectoryEntry[]> {
  return [];
}

export async function listTelegramDirectoryPeersFromConfig(): Promise<ChannelDirectoryEntry[]> {
  return [];
}

export async function listTelegramDirectoryGroupsFromConfig(): Promise<ChannelDirectoryEntry[]> {
  return [];
}

export async function listWhatsAppDirectoryPeersFromConfig(): Promise<ChannelDirectoryEntry[]> {
  return [];
}

export async function listWhatsAppDirectoryGroupsFromConfig(): Promise<ChannelDirectoryEntry[]> {
  return [];
}
