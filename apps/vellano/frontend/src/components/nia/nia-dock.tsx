"use client";

import {
  Button,
  HeaderGlobalAction,
  IconButton,
  InlineNotification,
  Loading,
  TextArea,
} from "@carbon/react";
import {
  Archive,
  Close,
  FitToScreen,
  Microphone,
  Renew,
  Send,
  SidePanelClose,
} from "@carbon/icons-react";
import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { NiaMark } from "@/components/nia/nia-mark";
import { NiaStructuredCard } from "@/components/nia/nia-structured-card";
import {
  ApiError,
  archiveNiaThread,
  createNiaThread,
  getNiaThread,
  getNiaUsageMeOptional,
  listNiaThreads,
  runNiaThread,
  type NiaMessage,
  type NiaThread,
  type NiaThreadSummary,
  type NiaUsageMe,
} from "@/lib/api";

const WIDTH_STORAGE_KEY = "vellano-nia-dock-width";
const MIN_WIDTH_PX = 320;
const DEFAULT_WIDTH_PX = 384;
const MAX_WIDTH_RATIO = 0.8;
const EXPANDED_WIDTH_RATIO = 0.92;

const SUGGESTIONS = [
  "List overdue invoices",
  "Show open invoices",
  "What stock is on hand?",
] as const;

type NiaDockContextValue = {
  open: boolean;
  toggle: () => void;
  openDock: () => void;
};

const NiaDockContext = createContext<NiaDockContextValue | null>(null);

export function useNiaDock(): NiaDockContextValue {
  const ctx = useContext(NiaDockContext);
  if (!ctx) {
    throw new Error("useNiaDock must be used within NiaDockProvider");
  }
  return ctx;
}

function formatTokenCount(value: number): string {
  return value.toLocaleString("en-ZA");
}

function readStoredWidth(): number {
  if (typeof window === "undefined") {
    return DEFAULT_WIDTH_PX;
  }
  const raw = sessionStorage.getItem(WIDTH_STORAGE_KEY);
  const parsed = raw ? Number(raw) : NaN;
  if (!Number.isFinite(parsed)) {
    return DEFAULT_WIDTH_PX;
  }
  return Math.max(MIN_WIDTH_PX, parsed);
}

type NiaDockProviderProps = {
  children: ReactNode;
};

export function NiaDockProvider({ children }: NiaDockProviderProps) {
  const [open, setOpen] = useState(false);

  const toggle = useCallback(() => setOpen((current) => !current), []);
  const openDock = useCallback(() => setOpen(true), []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "j") {
        event.preventDefault();
        toggle();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [toggle]);

  return (
    <NiaDockContext.Provider value={{ open, toggle, openDock }}>
      {children}
    </NiaDockContext.Provider>
  );
}

export function NiaHeaderAction() {
  const { toggle } = useNiaDock();
  return (
    <HeaderGlobalAction
      aria-label="Nia"
      tooltipAlignment="end"
      onClick={toggle}
    >
      <NiaMark size={20} />
    </HeaderGlobalAction>
  );
}

type NiaDockPanelProps = {
  enabled: boolean;
};

export function NiaDockPanel({ enabled }: NiaDockPanelProps) {
  const pathname = usePathname();
  const { open, toggle } = useNiaDock();

  const [width, setWidth] = useState(DEFAULT_WIDTH_PX);
  const [expanded, setExpanded] = useState(false);
  const [preExpandWidth, setPreExpandWidth] = useState(DEFAULT_WIDTH_PX);
  const [threads, setThreads] = useState<NiaThreadSummary[]>([]);
  const [activeThread, setActiveThread] = useState<NiaThread | null>(null);
  const [composer, setComposer] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [loadingThreads, setLoadingThreads] = useState(false);
  const [loadingThread, setLoadingThread] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usageMe, setUsageMe] = useState<NiaUsageMe | null | undefined>(undefined);
  const [dictating, setDictating] = useState(false);

  const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const speechSupported =
    typeof window !== "undefined" &&
    Boolean(window.SpeechRecognition ?? window.webkitSpeechRecognition);

  const effectiveWidth = expanded
    ? Math.floor(window.innerWidth * EXPANDED_WIDTH_RATIO)
    : width;

  const loadThreads = useCallback(async () => {
    setLoadingThreads(true);
    try {
      const rows = await listNiaThreads();
      setThreads(rows);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to load threads");
    } finally {
      setLoadingThreads(false);
    }
  }, []);

  const loadThread = useCallback(async (threadId: string) => {
    setLoadingThread(true);
    setError(null);
    try {
      const thread = await getNiaThread(threadId);
      setActiveThread(thread);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to load thread");
    } finally {
      setLoadingThread(false);
    }
  }, []);

  useEffect(() => {
    setWidth(readStoredWidth());
  }, []);

  useEffect(() => {
    if (!enabled || !open) {
      return;
    }
    void loadThreads();
    getNiaUsageMeOptional()
      .then(setUsageMe)
      .catch(() => setUsageMe(null));
  }, [enabled, open, loadThreads]);

  useEffect(() => {
    const shell = document.querySelector(".vellano-shell") as HTMLElement | null;
    if (!shell) {
      return;
    }
    if (enabled && open) {
      shell.setAttribute("data-nia-dock-open", "true");
      shell.style.setProperty("--vellano-nia-dock-width", `${effectiveWidth}px`);
    } else {
      shell.removeAttribute("data-nia-dock-open");
      shell.style.removeProperty("--vellano-nia-dock-width");
    }
    return () => {
      shell.removeAttribute("data-nia-dock-open");
      shell.style.removeProperty("--vellano-nia-dock-width");
    };
  }, [enabled, open, effectiveWidth]);

  useEffect(() => {
    if (!expanded) {
      sessionStorage.setItem(WIDTH_STORAGE_KEY, String(width));
    }
  }, [width, expanded]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeThread?.messages, streamingText]);

  if (!enabled) {
    return null;
  }

  async function ensureThread(): Promise<NiaThread | null> {
    if (activeThread) {
      return activeThread;
    }
    try {
      const created = await createNiaThread();
      setActiveThread(created);
      setThreads((current) => [created, ...current]);
      return created;
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to create thread");
      return null;
    }
  }

  async function handleSend(messageText?: string) {
    const text = (messageText ?? composer).trim();
    if (!text || streaming) {
      return;
    }
    setError(null);
    setStreaming(true);
    setStreamingText("");
    const thread = await ensureThread();
    if (!thread) {
      setStreaming(false);
      return;
    }
    try {
      await runNiaThread(thread.id, text, pathname, (delta) => {
        setStreamingText((current) => current + delta);
      });
      await loadThread(thread.id);
      await loadThreads();
      getNiaUsageMeOptional().then(setUsageMe).catch(() => undefined);
      setComposer("");
      setStreamingText("");
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to send message");
    } finally {
      setStreaming(false);
    }
  }

  async function handleNewThread() {
    setError(null);
    setActiveThread(null);
    setComposer("");
    setStreamingText("");
    try {
      const created = await createNiaThread();
      setActiveThread(created);
      setThreads((current) => [created, ...current]);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to create thread");
    }
  }

  async function handleArchive(threadId: string, event: React.MouseEvent) {
    event.stopPropagation();
    try {
      await archiveNiaThread(threadId);
      setThreads((current) => current.filter((row) => row.id !== threadId));
      if (activeThread?.id === threadId) {
        setActiveThread(null);
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to archive thread");
    }
  }

  function handleResizePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (expanded) {
      return;
    }
    event.preventDefault();
    resizeRef.current = { startX: event.clientX, startWidth: width };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handleResizePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const state = resizeRef.current;
    if (!state) {
      return;
    }
    const maxWidth = Math.floor(window.innerWidth * MAX_WIDTH_RATIO);
    const next = Math.min(
      maxWidth,
      Math.max(MIN_WIDTH_PX, state.startWidth - (event.clientX - state.startX)),
    );
    setWidth(next);
  }

  function handleResizePointerUp(event: React.PointerEvent<HTMLDivElement>) {
    if (resizeRef.current) {
      resizeRef.current = null;
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function toggleExpanded() {
    if (expanded) {
      setExpanded(false);
      setWidth(preExpandWidth);
      return;
    }
    setPreExpandWidth(width);
    setExpanded(true);
  }

  function toggleDictate() {
    if (!speechSupported) {
      return;
    }
    if (dictating && recognitionRef.current) {
      recognitionRef.current.stop();
      setDictating(false);
      return;
    }
    const Ctor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Ctor) {
      return;
    }
    const recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-ZA";
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0]?.transcript ?? "";
      }
      if (transcript) {
        setComposer((current) => (current ? `${current} ${transcript}` : transcript));
      }
    };
    recognition.onerror = () => setDictating(false);
    recognition.onend = () => setDictating(false);
    recognitionRef.current = recognition;
    recognition.start();
    setDictating(true);
  }

  const usagePercent =
    usageMe && usageMe.cap > 0 ? Math.min(100, (usageMe.used / usageMe.cap) * 100) : 0;

  const messages: NiaMessage[] = activeThread?.messages ?? [];

  return (
    <aside
      className={`vellano-nia-dock${open ? " vellano-nia-dock--open" : ""}${expanded ? " vellano-nia-dock--expanded" : ""}`}
      style={{ width: open ? effectiveWidth : 0 }}
      aria-hidden={!open}
    >
      <div
        className="vellano-nia-dock__resize"
        onPointerDown={handleResizePointerDown}
        onPointerMove={handleResizePointerMove}
        onPointerUp={handleResizePointerUp}
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize Nia panel"
      />
      <div className="vellano-nia-dock__inner">
        <header className="vellano-nia-dock__header">
          <div className="vellano-nia-dock__title">
            <NiaMark size={22} />
            <span className="cds--type-productive-heading-02">Nia</span>
          </div>
          <div className="vellano-nia-dock__header-actions">
            <IconButton
              kind="ghost"
              size="sm"
              label={expanded ? "Dock" : "Expand"}
              onClick={toggleExpanded}
            >
              {expanded ? <SidePanelClose /> : <FitToScreen />}
            </IconButton>
            <IconButton kind="ghost" size="sm" label="Close Nia" onClick={toggle}>
              <Close />
            </IconButton>
          </div>
        </header>

        {usageMe !== undefined && usageMe !== null ? (
          <div className="vellano-nia-dock__meter">
            <p className="cds--type-helper-text-01">
              {formatTokenCount(usageMe.used)} / {formatTokenCount(usageMe.cap)} tokens
              {usageMe.cap === 0 ? " — blocked" : ""}
            </p>
            {usageMe.cap > 0 ? (
              <div
                className="vellano-nia-usage-meter"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={usageMe.cap}
                aria-valuenow={usageMe.used}
                aria-label="Nia token usage this month"
              >
                <div
                  className="vellano-nia-usage-meter__bar"
                  style={{ width: `${usagePercent}%` }}
                />
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="vellano-nia-dock__threads">
          <div className="vellano-nia-dock__threads-toolbar">
            <p className="cds--type-label-01">Threads</p>
            <Button kind="ghost" size="sm" renderIcon={Renew} onClick={() => void handleNewThread()}>
              New
            </Button>
          </div>
          {loadingThreads ? (
            <Loading withOverlay={false} description="Loading threads…" small />
          ) : threads.length === 0 ? (
            <p className="cds--type-helper-text-01">No threads yet.</p>
          ) : (
            <ul className="vellano-nia-dock__thread-list">
              {threads.map((thread) => (
                <li
                  key={thread.id}
                  className={`vellano-nia-dock__thread${activeThread?.id === thread.id ? " vellano-nia-dock__thread--active" : ""}`}
                >
                  <button
                    type="button"
                    className="vellano-nia-dock__thread-select"
                    onClick={() => void loadThread(thread.id)}
                  >
                    <span className="vellano-nia-dock__thread-title">{thread.title}</span>
                  </button>
                  <IconButton
                    kind="ghost"
                    size="sm"
                    label={`Archive ${thread.title}`}
                    onClick={(event: React.MouseEvent) => void handleArchive(thread.id, event)}
                  >
                    <Archive />
                  </IconButton>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="vellano-nia-dock__messages">
          {loadingThread ? (
            <Loading withOverlay={false} description="Loading conversation…" />
          ) : messages.length === 0 && !streamingText ? (
            <p className="vellano-nia-dock__empty cds--type-body-01">
              Ask Nia about invoices, stock, or navigation.
            </p>
          ) : (
            <>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`vellano-nia-dock__message vellano-nia-dock__message--${message.role}`}
                >
                  {message.role === "assistant" && message.structured_payload ? (
                    <NiaStructuredCard
                      message={message}
                      threadId={activeThread?.id ?? ""}
                      streaming={streaming}
                      onResumeComplete={() => {
                        if (activeThread) {
                          void loadThread(activeThread.id);
                        }
                      }}
                      onResumeError={setError}
                    />
                  ) : null}
                  {message.content ? (
                    <p className="vellano-nia-dock__bubble">{message.content}</p>
                  ) : null}
                </div>
              ))}
              {streamingText ? (
                <div className="vellano-nia-dock__message vellano-nia-dock__message--assistant">
                  <p className="vellano-nia-dock__bubble">{streamingText}</p>
                </div>
              ) : null}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        {error ? (
          <InlineNotification
            kind="error"
            title="Nia"
            subtitle={error}
            lowContrast
            onClose={() => setError(null)}
          />
        ) : null}

        <div className="vellano-nia-dock__suggestions">
          {SUGGESTIONS.map((label) => (
            <Button
              key={label}
              kind="ghost"
              size="sm"
              disabled={streaming}
              onClick={() => {
                setComposer(label);
                void handleSend(label);
              }}
            >
              {label}
            </Button>
          ))}
        </div>

        <div className="vellano-nia-dock__composer">
          <TextArea
            id="nia-composer"
            labelText="Message Nia"
            hideLabel
            placeholder="Message Nia…"
            rows={3}
            value={composer}
            disabled={streaming || usageMe?.cap === 0}
            onChange={(event) => setComposer(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void handleSend();
              }
            }}
          />
          <div className="vellano-nia-dock__composer-actions">
            <IconButton
              kind="ghost"
              size="md"
              label="Dictate"
              aria-label="Dictate"
              disabled={!speechSupported || streaming}
              title={
                speechSupported
                  ? "Dictate"
                  : "Speech recognition is not supported in this browser"
              }
              onClick={toggleDictate}
            >
              <Microphone />
            </IconButton>
            <Button
              kind="primary"
              size="md"
              renderIcon={Send}
              disabled={streaming || !composer.trim() || usageMe?.cap === 0}
              onClick={() => void handleSend()}
            >
              Send
            </Button>
          </div>
        </div>
      </div>
    </aside>
  );
}
