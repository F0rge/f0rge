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
  const openingRef = useRef<SVGPathElement>(null);
  const shadowRef = useRef<SVGEllipseElement>(null);

  useEffect(() => {
    const body = bodyRef.current;
    const aperture = apertureRef.current;
    const opening = openingRef.current;
    const shadow = shadowRef.current;
    if (!body || !aperture || !opening || !shadow) return;

    const draw = (time: number) => {
      // Catch sight of something, look away, then give it a longer second look.
      const notice = heldPose(time, 70, 200, 415, 525);
      const away = heldPose(time, 415, 525, 690, 930);
      const secondLook = heldPose(time, 690, 930, 2110, 2480);
      const brow = heldPose(time, 910, 1190, 1360, 1490);
      const blink = heldPose(time, 1380, 1490, 1540, 1700);
      const peek = heldPose(time, 1550, 1750, 1910, 2110);
      const halfBlink = heldPose(time, 1910, 2010, 2045, 2190);

      // The eye moves first. The cube catches up, holds its tilt, then settles.
      const chinTurn = heldPose(time, 490, 690, 835, 1040);
      const lean = heldPose(time, 810, 1180, 2110, 2470);
      const settle = heldPose(time, 2240, 2470, 2480, 2700);
      const lift = -1.9 * notice - 1.6 * lean + 3.2 * blink - 5.4 * peek + settle;
      const tilt = 2.4 * notice - 4.2 * chinTurn + 8 * lean - 2.2 * peek - 1.6 * settle;
      const squash = -.025 * notice + .067 * blink - .047 * peek + .015 * settle;
      body.setAttribute("transform", `translate(100 ${140 + lift}) rotate(${tilt}) scale(${1 + squash} ${1 - squash}) translate(-100 -140)`);

      const gazeX = 6.5 * notice - 8.1 * away + 8.4 * secondLook;
      const windowX = 78 + gazeX;
      const windowY = 112.7 + gazeX / Math.sqrt(3) - 6 * notice + 7.4 * away - 7.7 * secondLook + 3.6 * blink;
      const height = 1 + .17 * notice - .22 * brow - .93 * blink + .21 * peek - .52 * halfBlink;
      const width = 1 - .045 * notice + .045 * brow + .09 * blink - .04 * peek;
      aperture.setAttribute("transform", `translate(${windowX} ${windowY}) skewY(30) scale(${width} ${height})`);
      opening.setAttribute("d", `M-9.2 ${-10.6 + 7 * brow} L9.2 ${-10.6 - 2.5 * brow} V10.6 H-9.2Z`);
      shadow.setAttribute("rx", String(23 + 2.4 * blink - 3 * peek));
      shadow.setAttribute("opacity", String(.17 + .036 * blink - .045 * peek));
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
          <filter id={`${id}-shadow`} x="-30%" y="-180%" width="160%" height="460%">
            <feGaussianBlur stdDeviation="2.7" />
          </filter>
        </defs>
        <ellipse ref={shadowRef} cx="100" cy="157" rx="23" ry="3.2" fill="#161616" opacity=".17" filter={`url(#${id}-shadow)`} />
        <g ref={bodyRef}>
          {/* Header mark colors. Its pale front needs an edge on the matching workspace background. */}
          <path d="M100 100 144 74.6 144 125.4 100 150.8Z" fill="#6f6f6f" />
          <path d="M56 74.6 100 100 100 150.8 56 125.4Z" fill="#f4f4f4" />
          <path d="M56 74.6 V125.4 L100 150.8" fill="none" stroke="#c6c6c6" strokeWidth="1" />
          <path d="M100 49.2 144 74.6 100 100 56 74.6Z" fill="#c6c6c6" />
          <g ref={apertureRef} transform="translate(78 112.7) skewY(30)">
            <path ref={openingRef} d="M-9.2 -10.6 H9.2 V10.6 H-9.2Z" fill="#161616" />
          </g>
        </g>
      </svg>
    </div>
  );
}
