export function createSearchVisitGuard(): {
  shouldCapture(consented: boolean, key: string): boolean;
  release(): void;
} {
  let lastKey = "";
  let clearTimer: ReturnType<typeof setTimeout> | undefined;
  return {
    shouldCapture(consented, key) {
      if (clearTimer) {
        clearTimeout(clearTimer);
        clearTimer = undefined;
      }
      if (!consented) {
        lastKey = "";
        return false;
      }
      if (lastKey === key) return false;
      lastKey = key;
      return true;
    },
    release() {
      if (clearTimer) clearTimeout(clearTimer);
      const capturedKey = lastKey;
      clearTimer = setTimeout(() => {
        if (lastKey === capturedKey) lastKey = "";
        clearTimer = undefined;
      }, 0);
    },
  };
}
