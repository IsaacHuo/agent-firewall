# TraceView Component Library

A Vue 3 component library for visualizing AI agent traces, ported from Invariant Explorer's TraceView.

## Features

- **Message Expansion/Collapse**: Click to expand/collapse individual messages
- **Tool Call Highlighting**: Visual indicators for tool calls and responses
- **Role-Based Styling**: Different visual styles for user, assistant, system, and tool messages
- **Code Highlighting**: Syntax highlighting for code blocks and JSON
- **Image Display**: Inline image viewing with fullscreen support
- **Annotations**: Address-based annotations with severity levels
- **Side-by-Side Editor**: Optional JSON editor for trace editing
- **Permalink Support**: Copy permalink to specific messages

## Components

### TraceView

Main container component for displaying traces.

```vue
<TraceView
  :trace="messages"
  :highlights="highlights"
  :trace-id="traceId"
  :side-by-side="true"
  title="My Trace"
  @update:trace="handleTraceUpdate"
  @select-message="handleMessageSelect"
/>
```

**Props:**

- `trace`: Array of trace messages
- `highlights`: Object mapping addresses to colors
- `traceId`: Unique identifier for the trace
- `sideBySide`: Enable side-by-side editor view
- `title`: Title for the trace view
- `editor`: Show/hide the JSON editor

**Events:**

- `update:trace`: Emitted when trace is edited
- `select-message`: Emitted when a message is selected

### TraceLine

Individual message line component.

```vue
<TraceLine
  :message="message"
  :index="0"
  :expanded="true"
  :selected="false"
  :highlights="highlights"
  @toggle="handleToggle"
  @select="handleSelect"
/>
```

### TraceHighlight

Annotation display component.

```vue
<TraceHighlight
  address="messages[0].content"
  content="Potential security issue detected"
  severity="warning"
  source="l1"
/>
```

### Plugins

#### CodeHighlighter

Displays code with syntax highlighting and highlight markers.

```vue
<CodeHighlighter
  :content="code"
  language="json"
  :highlights="highlights"
  address="messages[0].tool_calls[0].function.arguments"
/>
```

#### ImageViewer

Displays images with fullscreen support.

```vue
<ImageViewer url="https://example.com/image.png" alt="Example Image" />
```

## Data Structure

### TraceMessage

```typescript
interface TraceMessage {
  role: "user" | "assistant" | "system" | "tool" | "function";
  content: string | null | TraceContent[];
  tool_calls?: ToolCall[];
  tool_call_id?: string | number | null;
}
```

### Highlight

```typescript
interface Highlight {
  address: string; // e.g., "messages[0].content:5-10"
  color: string; // CSS color
  label?: string; // Optional label
}
```

### Annotation

```typescript
interface Annotation {
  id: string;
  trace_id: string;
  address: string;
  content: string;
  severity: "info" | "warning" | "error";
  source: "user" | "l1" | "l2" | "policy" | "agent_scan";
  created_at: string;
}
```

## Styling

The component uses CSS custom properties for theming:

```css
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --bg-code: #f8f8f8;
  --bg-hover: #e8e8e8;
  --border-color: #e0e0e0;
  --border-hover: #999;
  --text-primary: #333;
  --text-secondary: #666;
  --primary-color: #007bff;
  --error-color: #dc3545;
}
```

## Integration with Agent Firewall

The TraceView component integrates with Agent Firewall's storage layer:

```typescript
import { TraceView } from '@/components/TraceView'
import { getStorageBackend } from '@/api/storage'

const storage = getStorageBackend()
const trace = await storage.get_trace(traceId)

// Display trace
<TraceView :trace="trace.messages" :trace-id="trace.id" />
```

## Future Enhancements

- [ ] Monaco editor integration for advanced JSON editing
- [ ] Virtual scrolling for large traces (1000+ messages)
- [ ] Advanced syntax highlighting with Prism.js or Shiki
- [ ] Annotation editing UI
- [ ] Export trace to various formats (JSON, Markdown, PDF)
- [ ] Search and filter within traces
- [ ] Diff view for comparing traces
