"use client";

import { useEffect, useId, useRef } from "react";
import styles from "./workspace-loader.module.css";

function easeBetween(time: number, start: number, end: number) {
  const progress = Math.min(1, Math.max(0, (time - start) / (end - start)));
  return progress * progress * (3 - 2 * progress);
}

/** Ease into a pose, hold it, then ease back to neutral. Times are in milliseconds. */
function heldPose(time: number, start: number, arrive: number, leave: number, end: number) {
  return easeBetween(time, start, arrive) - easeBetween(time, leave, end);
}

export function WorkspaceLoader({ loop = true }: { loop?: boolean }) {
  const id = useId();
  const bodyRef = useRef<SVGGElement>(null);
  const apertureRef = useRef<SVGGElement>(null);
  const rimRef = useRef<SVGPathElement>(null);
  const openingRef = useRef<SVGPathElement>(null);
  const shadowRef = useRef<SVGEllipseElement>(null);

  useEffect(() => {
    const body = bodyRef.current;
    const aperture = apertureRef.current;
    const rim = rimRef.current;
    const opening = openingRef.current;
    const shadow = shadowRef.current;
    if (!body || !aperture || !rim || !opening || !shadow) return;

    const draw = (time: number) => {
      const left = heldPose(time, 100, 245, 545, 710);
      const upRight = heldPose(time, 545, 710, 1870, 2140);
      const squint = heldPose(time, 790, 1010, 1210, 1330);
      const blink = heldPose(time, 1200, 1330, 1400, 1560);
      const reopen = heldPose(time, 1400, 1570, 1630, 1800);

      // The cube follows the gaze a beat later, like a small head tilt.
      const followLeft = heldPose(time, 205, 420, 635, 900);
      const followRight = heldPose(time, 635, 900, 2000, 2300);
      const lift = -1.1 * followRight + 2.3 * blink - 2.8 * reopen;
      const tilt = -1.9 * followLeft + 2.9 * followRight - 1.2 * reopen;
      const squash = .052 * blink - .027 * reopen;
      body.setAttribute("transform", `translate(100 ${140 + lift}) rotate(${tilt}) scale(${1 + squash} ${1 - squash}) translate(-100 -140)`);

      const gazeX = -7.4 * left + 7.5 * upRight;
      const windowX = 78 + gazeX;
      const windowY = 112.7 + gazeX / Math.sqrt(3) + 6.3 * left - 9.3 * upRight + 3.6 * blink;
      const height = 1 - .26 * squint - .93 * blink + .12 * reopen;
      const width = 1 + .05 * squint + .065 * blink - .025 * reopen;
      aperture.setAttribute("transform", `translate(${windowX} ${windowY}) skewY(30) scale(${width} ${height})`);
      rim.setAttribute("d", `M-9.2 ${-10.6 + 5 * squint} L9.2 -10.6 V10.6 H-9.2Z`);
      opening.setAttribute("d", `M-7.8 ${-9.3 + 4.6 * squint} L9.2 -9.3 V10.6 H-7.8Z`);
      shadow.setAttribute("rx", String(23 + 2 * blink - 1.5 * reopen));
      shadow.setAttribute("opacity", String(.17 + .03 * blink - .025 * reopen));
    };

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    const syncMotion = () => {
      cancelAnimationFrame(frame);
      draw(0);
      if (reducedMotion.matches) return;
      const start = performance.now();
      const tick = (now: number) => {
        const elapsed = Math.max(0, now - start);
        if (!loop && elapsed >= 3000) {
          draw(0);
          return;
        }
        draw(elapsed % 3000);
        frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    };
    syncMotion();
    reducedMotion.addEventListener("change", syncMotion);
    return () => {
      cancelAnimationFrame(frame);
      reducedMotion.removeEventListener("change", syncMotion);
    };
  }, [loop]);

  return (
    <div className={styles.stage} role="status">
      <span className="firstout-sr-only">Loading your workspace…</span>
      <svg className={styles.mark} viewBox="16 16 168 168" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id={`${id}-top`} x1="0%" y1="0%" x2="65%" y2="100%">
            <stop stopColor="#d9d9dc" />
            <stop offset="1" stopColor="#a9a9ae" />
          </linearGradient>
          <linearGradient id={`${id}-side`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop stopColor="#939397" />
            <stop offset="1" stopColor="#626267" />
          </linearGradient>
          <linearGradient id={`${id}-front`} x1="0%" y1="0%" x2="82%" y2="100%">
            <stop stopColor="#303035" />
            <stop offset="1" stopColor="#111113" />
          </linearGradient>
          <filter id={`${id}-shadow`} x="-30%" y="-180%" width="160%" height="460%">
            <feGaussianBlur stdDeviation="2.7" />
          </filter>
        </defs>
        <ellipse ref={shadowRef} cx="100" cy="157" rx="23" ry="3.2" fill="#202027" opacity=".17" filter={`url(#${id}-shadow)`} />
        <g ref={bodyRef}>
          <path d="M100 100 144 74.6 144 125.4 100 150.8Z" fill={`url(#${id}-side)`} />
          <path d="M56 74.6 100 100 100 150.8 56 125.4Z" fill={`url(#${id}-front)`} />
          <path d="M100 49.2 144 74.6 100 100 56 74.6Z" fill={`url(#${id}-top)`} />
          <g ref={apertureRef} transform="translate(78 112.7) skewY(30)">
            <path ref={rimRef} d="M-9.2 -10.6 H9.2 V10.6 H-9.2Z" fill="#99999e" />
            <path ref={openingRef} d="M-7.8 -9.3 H9.2 V10.6 H-7.8Z" fill="var(--cds-background, #f4f4f4)" />
          </g>
        </g>
      </svg>
    </div>
  );
}
