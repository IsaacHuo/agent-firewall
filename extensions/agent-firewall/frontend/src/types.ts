/**
 * Agent Firewall — Type Definitions
 *
 * Centralized type definitions for the security middleware frontend.
 */

// ── Verdict & Threat Levels ─────────────────────────────────────────

export type Verdict = "ALLOW" | "BLOCK" | "ESCALATE";

export type ThreatLevel = "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

// ── Analysis Results ────────────────────────────────────────────────

export interface L1Analysis {
  matched_patterns: string[];
  threat_level: ThreatLevel;
}

export interface L2Analysis {
  is_injection: boolean;
  confidence: number;
  reasoning: string;
}

export interface AnalysisResult {
  request_id: string;
  verdict: Verdict;
  threat_level: ThreatLevel;
  l1_matched_patterns: string[];
  l2_is_injection: boolean;
  l2_confidence: number;
  l2_reasoning: string;
  blocked_reason: string;
}

// ── Events ──────────────────────────────────────────────────────────

export interface FirewallEvent {
  event_type: string;
  timestamp: number;
  session_id: string;
  agent_id: string;
  method: string;
  payload_preview: string;
  analysis: AnalysisResult | null;
  is_alert: boolean;
}

// ── Statistics ──────────────────────────────────────────────────────

export interface AuditStats {
  total: number;
  blocked: number;
  escalated: number;
  queue_depth: number;
}

export interface Stats {
  uptime_seconds: number;
  active_sessions: number;
  dashboard_clients: number;
  audit: AuditStats | null;
  requests_per_minute?: number;
  avg_latency_ms?: number;
}

// ── Configuration ───────────────────────────────────────────────────

export interface NetworkConfig {
  listen_host: string;
  listen_port: number;
  upstream_host: string;
  upstream_port: number;
  transport_mode: "stdio" | "sse" | "websocket";
}

export interface EngineConfig {
  l1_enabled: boolean;
  l2_enabled: boolean;
  l2_model_endpoint: string;
  l2_api_key: string;
  l2_model: string;
  l2_timeout_seconds: number;
}

export interface SessionConfig {
  ring_buffer_size: number;
  ttl_seconds: number;
}

export interface RateLimitConfig {
  requests_per_sec: number;
  burst: number;
}

export interface FirewallConfig {
  network: NetworkConfig;
  engine: EngineConfig;
  session: SessionConfig;
  rate_limit: RateLimitConfig;
  audit_log_path: string;
  blocked_commands: string[];
}

// ── Rules ───────────────────────────────────────────────────────────

export type RuleAction = "BLOCK" | "ALLOW" | "ESCALATE" | "LOG";

export interface PatternRule {
  id: string;
  name: string;
  pattern: string;
  type: "literal" | "regex";
  action: RuleAction;
  threat_level: ThreatLevel;
  enabled: boolean;
  description?: string;
  created_at: number;
  updated_at: number;
}

export interface MethodRule {
  method: string;
  action: RuleAction;
  description?: string;
}

export interface AgentRule {
  agent_id_pattern: string;
  allowed_methods: string[];
  rate_limit?: number;
}

export interface RulesConfig {
  pattern_rules: PatternRule[];
  method_rules: MethodRule[];
  agent_rules: AgentRule[];
  default_action: RuleAction;
}

// ── Security Test ───────────────────────────────────────────────────

export interface TestPayload {
  id: string;
  name: string;
  category: "injection" | "traversal" | "exfiltration" | "command" | "custom";
  payload: string;
  expected_verdict: Verdict;
  description?: string;
}

export interface TestResult {
  payload_id: string;
  actual_verdict: Verdict;
  expected_verdict: Verdict;
  passed: boolean;
  l1_patterns: string[];
  l2_confidence: number;
  latency_ms: number;
  timestamp: number;
}

// ── Audit Log ───────────────────────────────────────────────────────

export interface AuditEntry {
  id: string;
  timestamp: number;
  session_id: string;
  agent_id: string;
  method: string;
  verdict: Verdict;
  threat_level: ThreatLevel;
  matched_patterns: string[];
  payload_hash: string;
  payload_preview?: string;
}

// ── Navigation ──────────────────────────────────────────────────────

export type NavSection =
  | "dashboard"
  | "traffic"
  | "rules"
  | "engine"
  | "rate-limit"
  | "test"
  | "audit";
