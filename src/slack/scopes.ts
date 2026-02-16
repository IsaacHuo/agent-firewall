// Stub — Slack channel removed in security-testing edition.
export type SlackScopesResult = { ok: boolean; scopes?: string[] };
export async function fetchSlackScopes(..._args: unknown[]): Promise<SlackScopesResult> { return { ok: false }; }
