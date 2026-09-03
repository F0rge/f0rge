"use client";

import { useEffect, useState } from "react";

import { parseCanvasSpec, type CanvasSpec } from "@/lib/nia-canvas-types";

const LEGACY_SESSION_KEY = "vellano-nia-canvas-spec";
const STATE_KEY = "vellano-nia-canvas-state";

type CanvasState = {
  userId: string | null;
  spec: CanvasSpec | null;
  clearedAt: string | null;
};

type Listener = () => void;
const listeners = new Set<Listener>();

function emit(): void {
  listeners.forEach((listener) => listener());
}

function emptyState(): CanvasState {
  return { userId: null, spec: null, clearedAt: null };
}

function persistableStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage;
}

function readRawState(): CanvasState {
  const store = persistableStorage();
  if (!store) {
    return emptyState();
  }
  try {
    const raw = store.getItem(STATE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<CanvasState>;
      const spec = parsed.spec ? parseCanvasSpec(parsed.spec) : null;
      return {
        userId: typeof parsed.userId === "string" ? parsed.userId : null,
        spec,
        clearedAt: typeof parsed.clearedAt === "string" ? parsed.clearedAt : null,
      };
    }
  } catch {
    // Fall through to legacy sessionStorage.
  }

  try {
    if (typeof window === "undefined") {
      return emptyState();
    }
    const legacy = window.sessionStorage.getItem(LEGACY_SESSION_KEY);
    if (!legacy) {
      return emptyState();
    }
    const spec = parseCanvasSpec(JSON.parse(legacy) as unknown);
    if (!spec) {
      return emptyState();
    }
    const migrated: CanvasState = { userId: null, spec, clearedAt: null };
    writeRawState(migrated);
    window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
    return migrated;
  } catch {
    return emptyState();
  }
}

function writeRawState(state: CanvasState): void {
  const store = persistableStorage();
  if (!store) {
    return;
  }
  store.setItem(STATE_KEY, JSON.stringify(state));
  if (typeof window !== "undefined") {
    window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
  }
}

export function bindCanvasUser(userId: string): void {
  const current = readRawState();
  if (current.userId === userId) {
    return;
  }
  if (current.userId && current.userId !== userId) {
    writeRawState({ userId, spec: null, clearedAt: null });
    emit();
    return;
  }
  writeRawState({ ...current, userId });
}

export function readCanvasSpec(): CanvasSpec | null {
  return readRawState().spec;
}

export function writeCanvasSpec(spec: CanvasSpec): void {
  const parsed = parseCanvasSpec(spec);
  if (!parsed) {
    return;
  }
  const current = readRawState();
  writeRawState({ userId: current.userId, spec: parsed, clearedAt: null });
  emit();
}

/** `clearedAt` accepts the server instant of a `canvas_cleared` message so a
 * later chart from the same thread can still win (see nia-thread-utils). */
export function clearCanvasSpec(clearedAt?: string): void {
  const current = readRawState();
  writeRawState({
    userId: current.userId,
    spec: null,
    clearedAt: clearedAt ?? new Date().toISOString(),
  });
  emit();
}

export function isCanvasCleared(): boolean {
  const current = readRawState();
  return current.clearedAt !== null && current.spec === null;
}

export function canvasClearedAt(): string | null {
  return readRawState().clearedAt;
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useCanvasSpec(): CanvasSpec | null {
  const [spec, setSpec] = useState<CanvasSpec | null>(() => readCanvasSpec());

  useEffect(() => {
    return subscribe(() => {
      setSpec(readCanvasSpec());
    });
  }, []);

  return spec;
}
