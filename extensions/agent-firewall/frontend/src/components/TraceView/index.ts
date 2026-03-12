/**
 * TraceView Component Library
 *
 * A Vue 3 port of Invariant Explorer's TraceView library for visualizing
 * AI agent traces with support for:
 * - Message expansion/collapse
 * - Tool call highlighting
 * - Address-based annotations
 * - Code syntax highlighting
 * - Inline image display
 * - Side-by-side editor
 */

export { default as TraceView } from "./TraceView.vue";
export { default as TraceLine } from "./TraceLine.vue";
export { default as TraceHighlight } from "./TraceHighlight.vue";
export { default as CodeHighlighter } from "./plugins/CodeHighlighter.vue";
export { default as ImageViewer } from "./plugins/ImageViewer.vue";

export type {
  TraceMessage,
  TraceContent,
  ToolCall,
  Trace,
  TraceAnalysis,
  Annotation,
  Highlight,
  TraceViewProps,
  TraceLineProps,
} from "./types";
