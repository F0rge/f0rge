"use client";

import type { TooltipRenderProps } from "react-joyride";

export function TourTooltip({
  backProps,
  closeProps,
  index,
  isLastStep,
  primaryProps,
  size,
  skipProps,
  step,
  tooltipProps,
}: TooltipRenderProps) {
  return (
    <div className="firstout-tour-tooltip" {...tooltipProps}>
      <button type="button" className="firstout-tour-tooltip__close" {...closeProps}>
        <span aria-hidden="true">×</span>
      </button>
      {step.title ? <h2 id="firstout-tour-title">{step.title}</h2> : null}
      <div id="firstout-tour-body" className="firstout-tour-tooltip__body">
        {step.content}
      </div>
      <p className="firstout-tour-tooltip__meta">
        Step {index + 1} of {size}
      </p>
      <div className="firstout-tour-tooltip__actions">
        <button
          type="button"
          className="firstout-tour-tooltip__ghost firstout-tour-tooltip__skip"
          {...skipProps}
        >
          Skip tour
        </button>
        {index > 0 ? (
          <button type="button" className="firstout-tour-tooltip__ghost" {...backProps}>
            Back
          </button>
        ) : null}
        <button type="button" className="firstout-tour-tooltip__primary" {...primaryProps}>
          {isLastStep ? "Done" : "Next"}
        </button>
      </div>
    </div>
  );
}
