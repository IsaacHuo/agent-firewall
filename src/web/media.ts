// Stub — Web (WhatsApp) channel removed in security-testing edition.
export type LoadedMedia = {
  buffer: Buffer;
  contentType: string | null;
  fileName: string | null;
};
export async function loadWebMedia(
  ..._args: unknown[]
): Promise<LoadedMedia | undefined> {
  return undefined;
}
export function getDefaultLocalRoots(..._args: unknown[]) { return []; }
