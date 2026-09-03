"use client";

import { Accordion, AccordionItem, InlineLoading } from "@carbon/react";
import { useEffect, useState } from "react";

import {
  niaThinkingBody,
  niaThinkingTitle,
  niaWorkingElapsedSeconds,
  showNiaWorkingRow,
} from "@/lib/nia-thinking";

export function NiaMilestoneList({ labels }: { labels: string[] }) {
  const lines = labels.map((label) => label.trim()).filter(Boolean);
  if (lines.length === 0) {
    return null;
  }
  return (
    <ul className="vellano-nia-dock__milestones">
      {lines.map((label, index) => (
        <li key={`${index}-${label}`} className="vellano-nia-dock__milestone">
          {label}
        </li>
      ))}
    </ul>
  );
}

type NiaThinkingProps = {
  streaming: boolean;
  streamingText: string;
  thinkingText: string;
  toolNames: string[];
  milestones?: string[];
};

export function NiaThinking({
  streaming,
  streamingText,
  thinkingText,
  toolNames,
  milestones = [],
}: NiaThinkingProps) {
  const [expanded, setExpanded] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const working = showNiaWorkingRow(streaming, streamingText);
  const hasActivity = Boolean(thinkingText.trim() || toolNames.length);

  useEffect(() => {
    if (!streaming) {
      return undefined;
    }
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(niaWorkingElapsedSeconds(startedAt, Date.now()));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [streaming]);

  if (!streaming && !hasActivity) {
    return null;
  }

  const title = niaThinkingTitle({
    streaming,
    answerStarted: Boolean(streamingText.trim()),
    elapsedSeconds,
    toolNames,
    hasReasoning: Boolean(thinkingText.trim()),
  });
  const body = niaThinkingBody({
    thinkingText,
    toolNames,
    waiting: working,
  });

  return (
    <div className="vellano-nia-dock__thinking">
      {working ? (
        <div className="vellano-nia-dock__working">
          <InlineLoading description={title} />
        </div>
      ) : null}
      <NiaMilestoneList labels={milestones} />
      {hasActivity || working ? (
        <Accordion align="start" size="sm">
          <AccordionItem
            title={title}
            open={expanded}
            onHeadingClick={() => setExpanded((current) => !current)}
          >
            {body ? <pre className="vellano-nia-dock__thinking-body">{body}</pre> : null}
          </AccordionItem>
        </Accordion>
      ) : null}
    </div>
  );
}
