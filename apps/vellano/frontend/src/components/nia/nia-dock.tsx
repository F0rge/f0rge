"use client";

import {
  Button,
  HeaderGlobalAction,
  IconButton,
  InlineNotification,
  Loading,
  Modal,
  TextArea,
  TextInput,
} from "@carbon/react";
import {
  Add,
  Archive,
  Close,
  Edit,
  FitToScreen,
  Microphone,
  RecentlyViewed,
  Send,
  SidePanelClose,
} from "@carbon/icons-react";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { NiaMark } from "@/components/nia/nia-mark";
import { NiaMarkdown } from "@/components/nia/nia-markdown";
import { NiaStructuredCard } from "@/components/nia/nia-structured-card";
import { NiaThinking } from "@/components/nia/nia-thinking";
import {
  ApiError,
  archiveNiaThread,
  createNiaThread,
  getNiaThread,
  getNiaUsageMeOptional,
  isCanvasClearedPayload,
  isCanvasSpecPayload,
  listNiaThreads,
  patchNiaThread,
  runNiaThread,
  type NiaMessage,
  type NiaThread,
  type NiaThreadSummary,
  type NiaUsageMe,
} from "@/lib/api";
import { clearCanvasSpec, writeCanvasSpec } from "@/lib/nia-canvas-store";
import {
  optimisticUserMessage,
  planComposerSend,
  withOptimisticUserMessage,
} from "@/lib/nia-composer";
import {
  getDockOpenServerSnapshot,
  getDockOpenSnapshot,
  readDockThreadId,
  setDockOpen,
  subscribeDockOpen,
  toggleDockOpen,
  writeDockThreadId,
} from "@/lib/nia-dock-session";
import {
  NIA_NEAR_BOTTOM_PX,
  isNearBottom,
  readScrollMetrics,
  scrollElementToBottom,
} from "@/lib/nia-stick-to-bottom";
import { appendToolLine } from "@/lib/nia-thinking";
import {
  formatRelativeThreadTime,
  latestNeedsOkToolCallId,
  messageHasStructuredCard,
  messageNeedsOkIsActionable,
  messageShowsDockProse,
  syncCanvasSpecFromThread,
} from "@/lib/nia-thread-utils";

const WIDTH_STORAGE_KEY = "vellano-nia-dock-width";
const MIN_WIDTH_PX = 320;
const DEFAULT_WIDTH_PX = 384;
const MAX_WIDTH_RATIO = 0.8;

const SUGGESTIONS = [
  "Create a SKU",
  "List overdue invoices",
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

function applyPostRunNavigation(thread: NiaThread, router: ReturnType<typeof useRouter>): void {
  const lastMessage = thread.messages[thread.messages.length - 1];
  if (!lastMessage || lastMessage.role !== "assistant") {
    return;
  }
  const payload = lastMessage.structured_payload;
  if (!payload || typeof payload !== "object" || !("kind" in payload)) {
    return;
  }
  if (payload.kind === "opened_page" && typeof payload.path === "string") {
    router.push(payload.path);
    return;
  }
  if (isCanvasSpecPayload(payload)) {
    writeCanvasSpec(payload);
    router.push("/canvas");
    return;
  }
  if (isCanvasClearedPayload(payload)) {
    clearCanvasSpec();
    router.push("/canvas");
  }
}

type NiaConversationProps = {
  messages: NiaMessage[];
  activeThreadId: string | undefined;
  streaming: boolean;
  streamingText: string;
  thinkingText: string;
  toolNames: string[];
  milestones: string[];
  loadingThread: boolean;
  showSuggestions: boolean;
  composer: string;
  composerDisabled: boolean;
  speechSupported: boolean;
  onComposerChange: (value: string) => void;
  onSend: (messageText?: string) => void;
  onToggleDictate: () => void;
  onResumeComplete: () => void;
  onResumeError: (message: string) => void;
};

function NiaConversation({
  messages,
  activeThreadId,
  streaming,
  streamingText,
  thinkingText,
  toolNames,
  milestones,
  loadingThread,
  showSuggestions,
  composer,
  composerDisabled,
  speechSupported,
  onComposerChange,
  onSend,
  onToggleDictate,
  onResumeComplete,
  onResumeError,
}: NiaConversationProps) {
  const hasUserMessage = messages.some((message) => message.role === "user");
  const latestApprovalToolCallId = latestNeedsOkToolCallId(messages);
  const messagesRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  const pinToBottom = useCallback((force = false) => {
    const el = messagesRef.current;
    if (!el) {
      return;
    }
    if (force || stickToBottomRef.current) {
      stickToBottomRef.current = true;
      scrollElementToBottom(el);
    }
  }, []);

  const handleMessagesScroll = useCallback(() => {
    const el = messagesRef.current;
    if (!el) {
      return;
    }
    stickToBottomRef.current = isNearBottom(readScrollMetrics(el), NIA_NEAR_BOTTOM_PX);
  }, []);

  // New thread / open history: always land on latest.
  useEffect(() => {
    stickToBottomRef.current = true;
    pinToBottom(true);
  }, [activeThreadId, pinToBottom]);

  // Follow streaming + new messages only while the user is near the bottom.
  useEffect(() => {
    pinToBottom();
  }, [messages, streamingText, streaming, pinToBottom]);

  const handleSend = useCallback(
    (messageText?: string) => {
      stickToBottomRef.current = true;
      pinToBottom(true);
      void onSend(messageText);
    },
    [onSend, pinToBottom],
  );

  return (
    <>
      <div
        className="vellano-nia-dock__messages"
        ref={messagesRef}
        onScroll={handleMessagesScroll}
      >
        {loadingThread ? (
          <Loading withOverlay={false} description="Loading conversation…" />
        ) : messages.length === 0 && !streaming ? (
          <p className="vellano-nia-dock__empty cds--type-body-01">
            Ask Nia to create a SKU, check stock, or open a page.
          </p>
        ) : (
          <>
            {messages.map((message) => {
              const hasCard =
                message.role === "assistant" && messageHasStructuredCard(message);
              return (
                <div
                  key={message.id}
                  className={`vellano-nia-dock__message vellano-nia-dock__message--${message.role}`}
                >
                  {messageShowsDockProse(message) ? (
                    message.role === "assistant" ? (
                      <div className="vellano-nia-dock__bubble">
                        <NiaMarkdown text={message.content} />
                      </div>
                    ) : (
                      <p className="vellano-nia-dock__bubble">{message.content}</p>
                    )
                  ) : null}
                  {hasCard ? (
                    <NiaStructuredCard
                      message={message}
                      threadId={activeThreadId ?? ""}
                      streaming={streaming}
                      onResumeComplete={onResumeComplete}
                      onResumeError={onResumeError}
                      actionable={messageNeedsOkIsActionable(message, latestApprovalToolCallId)}
                    />
                  ) : null}
                </div>
              );
            })}
            {streaming ? (
              <div className="vellano-nia-dock__message vellano-nia-dock__message--assistant">
                <NiaThinking
                  streaming={streaming}
                  streamingText={streamingText}
                  thinkingText={thinkingText}
                  toolNames={toolNames}
                  milestones={milestones}
                />
                {streamingText ? (
                  <div className="vellano-nia-dock__bubble">
                    <NiaMarkdown text={streamingText} />
                  </div>
                ) : null}
              </div>
            ) : null}
          </>
        )}
      </div>

      {showSuggestions && !hasUserMessage ? (
        <div className="vellano-nia-dock__suggestions">
          {SUGGESTIONS.map((label) => (
            <Button
              key={label}
              kind="ghost"
              size="sm"
              disabled={streaming}
              onClick={() => void handleSend(label)}
            >
              {label}
            </Button>
          ))}
        </div>
      ) : null}

      <div className="vellano-nia-dock__composer">
        {/* Never disabled while streaming — a disabled field loses focus and eats keystrokes (#618). */}
        <TextArea
          id="nia-composer"
          labelText="Message Nia"
          hideLabel
          placeholder="Message Nia…"
          rows={1}
          value={composer}
          disabled={composerDisabled}
          onChange={(event) => onComposerChange(event.target.value)}
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
            align="left"
            autoAlign
            disabled={!speechSupported || streaming}
            title={
              speechSupported
                ? "Dictate"
                : "Speech recognition is not supported in this browser"
            }
            onClick={onToggleDictate}
          >
            <Microphone />
          </IconButton>
          <Button
            kind="primary"
            size="md"
            renderIcon={Send}
            disabled={streaming || !composer.trim() || composerDisabled}
            onClick={() => void handleSend()}
          >
            Send
          </Button>
        </div>
      </div>
    </>
  );
}

type NiaDockProviderProps = {
  children: ReactNode;
  enabled?: boolean;
};

export function NiaDockProvider({ children, enabled = true }: NiaDockProviderProps) {
  const open = useSyncExternalStore(
    subscribeDockOpen,
    getDockOpenSnapshot,
    getDockOpenServerSnapshot,
  );

  const toggle = useCallback(() => {
    toggleDockOpen();
  }, []);
  const openDock = useCallback(() => {
    setDockOpen(true);
  }, []);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key === ".") {
        event.preventDefault();
        toggle();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [enabled, toggle]);

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
      aria-label="Nia (⌘/Ctrl+.)"
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
  const router = useRouter();
  const { open, toggle } = useNiaDock();

  const [width, setWidth] = useState(DEFAULT_WIDTH_PX);
  const [modalOpen, setModalOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameThreadId, setRenameThreadId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [threads, setThreads] = useState<NiaThreadSummary[]>([]);
  const [activeThread, setActiveThread] = useState<NiaThread | null>(null);
  const [composer, setComposer] = useState("");
  const [pendingUserMessage, setPendingUserMessage] = useState<NiaMessage | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [thinkingText, setThinkingText] = useState("");
  const [toolNames, setToolNames] = useState<string[]>([]);
  const [milestones, setMilestones] = useState<string[]>([]);
  const [loadingThreads, setLoadingThreads] = useState(false);
  const [loadingThread, setLoadingThread] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usageMe, setUsageMe] = useState<NiaUsageMe | null | undefined>(undefined);
  const [dictating, setDictating] = useState(false);

  const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const persistThread = useRef(false);
  const hydratedThread = useRef(false);

  const speechSupported =
    typeof window !== "undefined" &&
    Boolean(window.SpeechRecognition ?? window.webkitSpeechRecognition);

  const composerBlocked = usageMe?.cap === 0;

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
    if (!enabled || !open || hydratedThread.current) {
      return;
    }
    const storedId = readDockThreadId();
    if (!storedId) {
      return;
    }
    // Hydrate once per mount: a late GET must not overwrite the thread a
    // finished run just wrote (that hid pending HITL cards until reopen).
    hydratedThread.current = true;
    void loadThread(storedId);
  }, [enabled, open, loadThread]);

  useEffect(() => {
    if (!persistThread.current) {
      persistThread.current = true;
      return;
    }
    writeDockThreadId(activeThread?.id ?? null);
  }, [activeThread?.id]);

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
      shell.style.setProperty("--vellano-nia-dock-width", `${width}px`);
    } else {
      shell.removeAttribute("data-nia-dock-open");
      shell.style.removeProperty("--vellano-nia-dock-width");
    }
    return () => {
      shell.removeAttribute("data-nia-dock-open");
      shell.style.removeProperty("--vellano-nia-dock-width");
    };
  }, [enabled, open, width]);

  useEffect(() => {
    sessionStorage.setItem(WIDTH_STORAGE_KEY, String(width));
  }, [width]);

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

  function resetStreamState() {
    setStreaming(false);
    setPendingUserMessage(null);
    setStreamingText("");
    setThinkingText("");
    setToolNames([]);
    setMilestones([]);
  }

  async function handleSend(messageText?: string) {
    const plan = planComposerSend({
      composer,
      override: messageText,
      streaming,
      blocked: composerBlocked,
    });
    if (!plan.send) {
      return;
    }
    setError(null);
    setComposer(plan.nextComposer);
    setPendingUserMessage(optimisticUserMessage(plan.text, new Date().toISOString()));
    setStreaming(true);
    setStreamingText("");
    setThinkingText("");
    setToolNames([]);
    setMilestones([]);
    const thread = await ensureThread();
    if (!thread) {
      resetStreamState();
      return;
    }
    let streamed = false;
    try {
      await runNiaThread(thread.id, plan.text, pathname, {
        onToken: (delta) => {
          setStreamingText((current) => current + delta);
        },
        onThinking: (delta) => {
          setThinkingText((current) => current + delta);
        },
        onTool: (name, phase) => {
          if (name === "report_milestone") {
            return;
          }
          setToolNames((current) => (current[current.length - 1] === name ? current : [...current, name]));
          setThinkingText((current) => appendToolLine(current, name, phase));
        },
        onMilestone: (label) => {
          setMilestones((current) => [...current, label]);
        },
      });
      streamed = true;
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to send message");
    }
    // Refresh even when the stream failed: a pending Accept card is persisted
    // when the run ends, and it has to show in the open thread (#608).
    try {
      const fresh = await getNiaThread(thread.id);
      syncCanvasSpecFromThread(fresh);
      setActiveThread(fresh);
      if (streamed) {
        applyPostRunNavigation(fresh, router);
      }
      await loadThreads();
      getNiaUsageMeOptional().then(setUsageMe).catch(() => undefined);
    } catch {
      // Keep the run error already shown in the banner.
    }
    resetStreamState();
  }

  async function handleNewThread() {
    setError(null);
    setActiveThread(null);
    setComposer("");
    setPendingUserMessage(null);
    setStreamingText("");
    setThinkingText("");
    setToolNames([]);
    try {
      const created = await createNiaThread();
      setActiveThread(created);
      setThreads((current) => [created, ...current]);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to create thread");
    }
  }

  async function handleArchive(threadId: string) {
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

  function openRename(thread: NiaThreadSummary) {
    setRenameThreadId(thread.id);
    setRenameTitle(thread.title);
    setRenameOpen(true);
  }

  async function handleRenameSubmit() {
    if (!renameThreadId) {
      return;
    }
    const trimmed = renameTitle.trim();
    if (!trimmed) {
      setError("Title cannot be empty");
      return;
    }
    setRenaming(true);
    try {
      const updated = await patchNiaThread(renameThreadId, trimmed);
      setThreads((current) =>
        current.map((row) => (row.id === updated.id ? { ...row, title: updated.title } : row)),
      );
      if (activeThread?.id === updated.id) {
        setActiveThread({ ...activeThread, title: updated.title });
      }
      setRenameOpen(false);
      setRenameThreadId(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to rename thread");
    } finally {
      setRenaming(false);
    }
  }

  function handleResizePointerDown(event: React.PointerEvent<HTMLDivElement>) {
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

  const messages: NiaMessage[] = withOptimisticUserMessage(
    activeThread?.messages ?? [],
    pendingUserMessage,
  );

  const conversationProps: NiaConversationProps = {
    messages,
    activeThreadId: activeThread?.id,
    streaming,
    streamingText,
    thinkingText,
    toolNames,
    milestones,
    loadingThread,
    showSuggestions: true,
    composer,
    composerDisabled: composerBlocked,
    speechSupported,
    onComposerChange: setComposer,
    onSend: handleSend,
    onToggleDictate: toggleDictate,
    onResumeComplete: () => {
      if (activeThread) {
        void loadThread(activeThread.id);
      }
    },
    onResumeError: setError,
  };

  return (
    <>
      <aside
        className={`vellano-nia-dock${open ? " vellano-nia-dock--open" : ""}`}
        style={{ width: open ? width : 0 }}
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
                label="New conversation"
                align="bottom-end"
                autoAlign
                onClick={() => void handleNewThread()}
              >
                <Add />
              </IconButton>
              <IconButton
                kind="ghost"
                size="sm"
                label="History"
                align="bottom-end"
                autoAlign
                onClick={() => {
                  void loadThreads();
                  setHistoryOpen(true);
                }}
              >
                <RecentlyViewed />
              </IconButton>
              <IconButton
                kind="ghost"
                size="sm"
                label="Expand"
                align="bottom-end"
                autoAlign
                onClick={() => setModalOpen(true)}
              >
                <FitToScreen />
              </IconButton>
              <IconButton
                kind="ghost"
                size="sm"
                label="Close Nia"
                align="bottom-end"
                autoAlign
                onClick={toggle}
              >
                <Close />
              </IconButton>
            </div>
          </header>

          {error && !modalOpen ? (
            <InlineNotification
              kind="error"
              title="Nia"
              subtitle={error}
              lowContrast
              onClose={() => setError(null)}
            />
          ) : null}

          {!modalOpen ? <NiaConversation {...conversationProps} /> : (
            <p className="vellano-nia-dock__expanded-hint cds--type-helper-text-01">
              Conversation expanded — use Dock to return.
            </p>
          )}
        </div>
      </aside>

      <Modal
        open={modalOpen}
        modalHeading="Nia"
        passiveModal
        size="lg"
        className="vellano-nia-modal"
        onRequestClose={() => setModalOpen(false)}
      >
        <div className="vellano-nia-modal__body">
          {error ? (
            <InlineNotification
              kind="error"
              title="Nia"
              subtitle={error}
              lowContrast
              onClose={() => setError(null)}
            />
          ) : null}
          <NiaConversation {...conversationProps} />
        </div>
        <div className="vellano-nia-modal__footer">
          <Button kind="secondary" size="sm" renderIcon={SidePanelClose} onClick={() => setModalOpen(false)}>
            Dock
          </Button>
        </div>
      </Modal>

      <Modal
        open={historyOpen}
        modalHeading="Conversation history"
        passiveModal
        size="sm"
        onRequestClose={() => setHistoryOpen(false)}
      >
        {loadingThreads ? (
          <Loading withOverlay={false} description="Loading threads…" small />
        ) : threads.length === 0 ? (
          <p className="cds--type-body-01">No threads yet.</p>
        ) : (
          <ul className="vellano-nia-history-list">
            {threads.map((thread) => (
              <li key={thread.id} className="vellano-nia-history-list__item">
                <button
                  type="button"
                  className="vellano-nia-history-list__select"
                  onClick={() => {
                    void loadThread(thread.id);
                    setHistoryOpen(false);
                  }}
                >
                  <span className="vellano-nia-history-list__title">{thread.title}</span>
                  <span className="vellano-nia-history-list__time">
                    {formatRelativeThreadTime(thread.updated_at)}
                  </span>
                </button>
                <div className="vellano-nia-history-list__actions">
                  <IconButton
                    kind="ghost"
                    size="sm"
                    label={`Rename ${thread.title}`}
                    align="left"
                    autoAlign
                    onClick={() => openRename(thread)}
                  >
                    <Edit />
                  </IconButton>
                  <IconButton
                    kind="ghost"
                    size="sm"
                    label={`Archive ${thread.title}`}
                    align="left"
                    autoAlign
                    onClick={() => void handleArchive(thread.id)}
                  >
                    <Archive />
                  </IconButton>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Modal>

      <Modal
        open={renameOpen}
        modalHeading="Rename conversation"
        primaryButtonText={renaming ? "Saving…" : "Save"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={renaming || !renameTitle.trim()}
        onRequestClose={() => setRenameOpen(false)}
        onRequestSubmit={() => void handleRenameSubmit()}
      >
        <TextInput
          id="nia-rename-title"
          labelText="Title"
          value={renameTitle}
          onChange={(event) => setRenameTitle(event.target.value)}
          invalid={!renameTitle.trim()}
          invalidText="Title cannot be empty"
        />
      </Modal>
    </>
  );
}
