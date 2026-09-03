export function showNiaWorkingRow(streaming: boolean, streamingText: string): boolean {
  return streaming && !streamingText.trim();
}

export function niaWorkingElapsedSeconds(startedAtMs: number, nowMs: number): number {
  return Math.max(0, Math.floor((nowMs - startedAtMs) / 1000));
}

export function formatNiaWorkingTitle(elapsedSeconds: number): string {
  return `Working ${Math.max(0, Math.floor(elapsedSeconds))}s`;
}

export function formatNiaToolLabel(name: string): string {
  const trimmed = name.trim();
  if (!trimmed || trimmed === "tool") {
    return "a tool";
  }
  if (trimmed === "run_nia_action") {
    return "an action";
  }
  return trimmed;
}

export function niaThinkingSummary(options: {
  toolNames: string[];
  hasReasoning: boolean;
  answerStarted: boolean;
}): string {
  const lastTool = options.toolNames[options.toolNames.length - 1];
  if (!options.answerStarted) {
    if (lastTool) {
      return `Calling ${formatNiaToolLabel(lastTool)}…`;
    }
    return "Thinking";
  }
  if (lastTool) {
    return formatNiaToolLabel(lastTool);
  }
  if (options.hasReasoning) {
    return "Thought for a few seconds";
  }
  return "Thought for a few seconds";
}

export function niaReasoningToggleLabel(options: {
  expanded: boolean;
  streaming: boolean;
  answerStarted: boolean;
}): string {
  return options.expanded ? "Hide reasoning" : "Show reasoning";
}

export function niaThinkingTitle(options: {
  streaming: boolean;
  answerStarted: boolean;
  elapsedSeconds: number;
  toolNames: string[];
  hasReasoning: boolean;
}): string {
  // Working Ns belongs only on the primary spinner; the accordion uses a quieter label.
  return niaThinkingSummary({
    toolNames: options.toolNames,
    hasReasoning: options.hasReasoning,
    answerStarted: options.answerStarted,
  });
}

export function showNiaReasoningToggle(options: {
  working: boolean;
  hasActivity: boolean;
}): boolean {
  return options.hasActivity && !options.working;
}

export function niaThinkingBody(options: {
  thinkingText: string;
  toolNames: string[];
  waiting: boolean;
}): string {
  const trimmed = options.thinkingText.trim();
  if (trimmed) {
    return trimmed;
  }
  const lastTool = options.toolNames[options.toolNames.length - 1];
  if (lastTool) {
    return `Calling ${formatNiaToolLabel(lastTool)}…`;
  }
  if (options.waiting) {
    return "";
  }
  return "No extra detail.";
}

export function appendThinkingLine(current: string, delta: string): string {
  return `${current}${delta}`;
}

export function appendToolLine(current: string, name: string, phase: "start" | "end"): string {
  const label = formatNiaToolLabel(name);
  const line = phase === "start" ? `Calling ${label}…` : `Finished ${label}`;
  return current ? `${current}\n${line}` : line;
}
