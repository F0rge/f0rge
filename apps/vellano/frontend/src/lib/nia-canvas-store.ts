"use client";

import { useEffect, useState } from "react";

import { parseCanvasSpec, type CanvasSpec } from "@/lib/nia-canvas-types";

const STORAGE_KEY = "vellano-nia-canvas-spec";

type Listener = () => void;
const listeners = new Set<Listener>();

function emit(): void {
  listeners.forEach((listener) => listener());
}

export function readCanvasSpec(): CanvasSpec | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    return parseCanvasSpec(JSON.parse(raw) as unknown);
  } catch {
    return null;
  }
}

export function writeCanvasSpec(spec: CanvasSpec): void {
  if (typeof window === "undefined") {
    return;
  }
  const parsed = parseCanvasSpec(spec);
  if (!parsed) {
    return;
  }
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(parsed));
  emit();
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
