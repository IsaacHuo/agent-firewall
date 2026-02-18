// Channel-specific sendMessage imports removed
import type { OutboundSendDeps } from "../infra/outbound/deliver.js";

export type CliDeps = {
  sendMessageWhatsApp: any;
  sendMessageTelegram: any;
  sendMessageDiscord: any;
  sendMessageSlack: any;
  sendMessageSignal: any;
  sendMessageIMessage: any;
};

export function createDefaultDeps(): CliDeps {
  const noop = async () => undefined;
  return {
    sendMessageWhatsApp: noop,
    sendMessageTelegram: noop,
    sendMessageDiscord: noop,
    sendMessageSlack: noop,
    sendMessageSignal: noop,
    sendMessageIMessage: noop,
  };
}

// Provider docking: extend this mapping when adding new outbound send deps.
export function createOutboundSendDeps(deps: CliDeps): OutboundSendDeps {
  return {
    sendWhatsApp: deps.sendMessageWhatsApp,
    sendTelegram: deps.sendMessageTelegram,
    sendDiscord: deps.sendMessageDiscord,
    sendSlack: deps.sendMessageSlack,
    sendSignal: deps.sendMessageSignal,
    sendIMessage: deps.sendMessageIMessage,
  };
}

export { logWebSelfId } from "../web/auth-store.js";
