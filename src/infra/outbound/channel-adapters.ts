import type { ChannelId } from "../../channels/plugins/types.js";

// Trimmed for security testing edition — Discord removed.
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export type CrossContextComponentsBuilder = (message: string) => unknown[];

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export type CrossContextComponentsFactory = (params: {
  originLabel: string;
  message: string;
  cfg: unknown;
  accountId?: string | null;
}) => unknown[];

export type ChannelMessageAdapter = {
  supportsComponentsV2: boolean;
  buildCrossContextComponents?: CrossContextComponentsFactory;
};

const DEFAULT_ADAPTER: ChannelMessageAdapter = {
  supportsComponentsV2: false,
};

export function getChannelMessageAdapter(_channel: ChannelId): ChannelMessageAdapter {
  return DEFAULT_ADAPTER;
}
