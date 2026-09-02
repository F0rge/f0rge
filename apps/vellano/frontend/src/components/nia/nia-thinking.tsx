"use client";

import { Accordion, AccordionItem, InlineLoading } from "@carbon/react";
import { useState } from "react";

import { niaThinkingSummary, showNiaWorkingRow } from "@/lib/nia-thinking";

type NiaThinkingProps = {
  streaming: boolean;
  streamingText: string;
  thinkingText: string;
  toolNames: string[];
};

export function NiaThinking({
  streaming,
  streamingText,
  thinkingText,
  toolNames,
}: NiaThinkingProps) {
  const [expanded, setExpanded] = useState(false);
  const working = showNiaWorkingRow(streaming, streamingText);
  const hasActivity = Boolean(thinkingText.trim() || toolNames.length);
  if (!streaming && !hasActivity) {
    return null;
  }

  const summary = niaThinkingSummary({
    toolNames,
    hasReasoning: Boolean(thinkingText.trim()),
    answerStarted: Boolean(streamingText.trim()),
  });

  return (
    <div className="vellano-nia-dock__thinking">
      {working ? (
        <div className="vellano-nia-dock__working">
          <InlineLoading description="Nia is working…" />
        </div>
      ) : null}
      {hasActivity || working ? (
        <Accordion align="start" size="sm">
          <AccordionItem
            title={summary}
            open={expanded}
            onHeadingClick={() => setExpanded((current) => !current)}
          >
            <pre className="vellano-nia-dock__thinking-body">
              {thinkingText.trim() || (working ? "Waiting for the first token…" : "No extra detail.")}
            </pre>
          </AccordionItem>
        </Accordion>
      ) : null}
    </div>
  );
}
