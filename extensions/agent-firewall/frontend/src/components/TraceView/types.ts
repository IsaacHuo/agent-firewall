/**
 * TraceView Type Definitions
 *
 * These types define the structure of traces, messages, and annotations
 * compatible with both Agent Firewall and Invariant Explorer formats.
 */

export interface TraceMessage {
  role: "user" | "assistant" | "system" | "tool" | "function";
  content: string | null | TraceContent[];
  tool_calls?: ToolCall[];
  tool_call_id?: string | number | null;
  name?: string;
}

export interface TraceContent {
  type: "text" | "image_url";
  text?: string;
  image_url?: {
    url: string;
    detail?: "auto" | "low" | "high";
  };
}

export interface ToolCall {
  id: string | number;
  type: "function";
  function: {
    name: string;
    arguments: any;
  };
}

export interface Trace {
  id: string;
  session_id?: string;
  messages: TraceMessage[];
  metadata?: Record<string, any>;
  created_at?: string;
  analysis?: TraceAnalysis;
}

export interface TraceAnalysis {
  verdict: "ALLOW" | "BLOCK" | "ESCALATE";
  threat_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  l1_result?: {
    patterns_found: string[];
    risk_score: number;
  };
  l2_result?: {
    is_injection: boolean;
    confidence: number;
    reasoning: string;
  };
  agent_scan_result?: {
    issues: Array<{
      code: string;
      severity: "error" | "warning";
      message: string;
    }>;
    toxic_flows?: Array<{
      type: string;
      description: string;
    }>;
  };
}

export interface Annotation {
  id: string;
  trace_id: string;
  address: string;
  content: string;
  severity: "info" | "warning" | "error";
  source: "user" | "l1" | "l2" | "policy" | "agent_scan";
  created_at: string;
}

export interface Highlight {
  address: string;
  color: string;
  label?: string;
  severity?: "info" | "warning" | "error";
}

export interface TraceViewProps {
  trace: TraceMessage[];
  highlights?: Record<string, string>;
  annotations?: Annotation[];
  traceId?: string;
  sideBySide?: boolean;
  title?: string;
  editor?: boolean;
}

export interface TraceLineProps {
  message: TraceMessage;
  index: number;
  expanded: boolean;
  selected: boolean;
  highlights: Highlight[];
  annotations?: Annotation[];
}
