export function showNiaWorkingRow(streaming: boolean, streamingText: string): boolean {
  return streaming && !streamingText.trim();
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

export function appendThinkingLine(current: string, delta: string): string {
  return `${current}${delta}`;
}

export function appendToolLine(current: string, name: string, phase: "start" | "end"): string {
  const label = formatNiaToolLabel(name);
  const line = phase === "start" ? `Calling ${label}…` : `Finished ${label}`;
  return current ? `${current}\n${line}` : line;
}
