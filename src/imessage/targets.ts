// Stub — iMessage channel removed in security-testing edition.
export function parseIMessageTarget(_raw: string) { return { target: _raw }; }
export function normalizeIMessageHandle(handle: string) { return handle?.trim().toLowerCase() ?? ""; }
