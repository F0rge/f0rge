import { replayConfigAllowsCapture, type ReplayDecision, type ReplayVendorConfig } from "./replay";

export type ReplayFrame = { kind: "input"; masked: "*" };

export type MaskedReplayHandle = {
  recording: boolean;
  frames(): readonly ReplayFrame[];
  stop(): void;
};

/** Test double or the document element. The recorder never reads node text or input values. */
export type ReplayRoot = {
  subscribe(listener: () => void): () => void;
  setAttribute?(name: string, value: string): void;
  removeAttribute?(name: string): void;
};

function idleHandle(): MaskedReplayHandle {
  return { recording: false, frames: () => [], stop() {} };
}

function browserReplayRoot(): ReplayRoot | null {
  if (typeof document === "undefined") return null;
  const element = document.documentElement;
  return {
    subscribe(listener) {
      const observer = new MutationObserver((records) => {
        const visible = records.some((record) => {
          const node = record.target;
          const host = node instanceof Element ? node : node.parentElement;
          return !host?.closest("[data-storefront-no-capture]");
        });
        if (visible) listener();
      });
      observer.observe(element, { subtree: true, childList: true, characterData: true });
      const onInput = () => listener();
      element.addEventListener("input", onInput, true);
      return () => {
        observer.disconnect();
        element.removeEventListener("input", onInput, true);
      };
    },
    setAttribute(name, value) { element.setAttribute(name, value); },
    removeAttribute(name) { element.removeAttribute(name); },
  };
}

/** Starts a masked recorder only when the vendor config keeps capture channels off. */
export function startMaskedReplay(config: ReplayVendorConfig, root?: ReplayRoot | null): MaskedReplayHandle {
  if (!replayConfigAllowsCapture(config)) return idleHandle();
  const target = root === undefined ? browserReplayRoot() : root;
  if (!target) return idleHandle();
  const frames: ReplayFrame[] = [];
  const handle: MaskedReplayHandle = {
    recording: true,
    frames: () => frames,
    stop() {
      if (!handle.recording) return;
      handle.recording = false;
      unsubscribe();
      frames.length = 0;
      target.removeAttribute?.("data-storefront-replay");
    },
  };
  const unsubscribe = target.subscribe(() => {
    if (!handle.recording) return;
    frames.push({ kind: "input", masked: "*" });
  });
  target.setAttribute?.("data-storefront-replay", "on");
  return handle;
}

/** Start only for a record decision. Stop as soon as the decision says no. */
export function applyReplayDecision(
  current: MaskedReplayHandle | null,
  decision: ReplayDecision,
  root?: ReplayRoot | null,
): MaskedReplayHandle | null {
  if (!decision.record || !decision.config || !replayConfigAllowsCapture(decision.config)) {
    current?.stop();
    return null;
  }
  if (current?.recording) return current;
  const next = startMaskedReplay(decision.config, root);
  return next.recording ? next : null;
}
