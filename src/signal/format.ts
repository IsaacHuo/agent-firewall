// Stub — Signal channel removed in security-testing edition.
export type SignalTextStyleRange = { start: number; length: number; style: string };
export function markdownToSignalTextChunks(_md: string): Array<{ text: string; styles: SignalTextStyleRange[] }> {
  return [{ text: _md, styles: [] }];
}
