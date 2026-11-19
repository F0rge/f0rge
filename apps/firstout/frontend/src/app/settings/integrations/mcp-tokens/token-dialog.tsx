"use client";

import { CodeSnippet, InlineNotification, Modal, Select, SelectItem, Stack, TextInput } from "@carbon/react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  generateMcpToken, MCP_TOKEN_EXPIRY_DAYS, MCP_TOKEN_NAME_LIMIT, revokeMcpToken, rotateMcpToken,
  type McpToken, type McpTokenExpiryDays,
} from "@/lib/mcp-tokens";
import { adminError } from "@/lib/staff-administration";

export type TokenAction =
  | { kind: "generate" }
  | { kind: "rotate" | "revoke"; token: McpToken };

const labels = {
  generate: { title: "Generate a token", submit: "Generate token" },
  rotate: { title: "Replace this token?", submit: "Replace token" },
  revoke: { title: "Turn off this token?", submit: "Turn off token" },
};

export function McpTokenDialog({
  action, tokens, stale, onClose, onRefresh, onChanged,
}: {
  action: TokenAction;
  tokens: readonly McpToken[];
  stale: boolean;
  onClose: () => void;
  onRefresh: () => void;
  onChanged: (message: string) => void;
}) {
  const [label, setLabel] = useState("");
  const [days, setDays] = useState<McpTokenExpiryDays>(30);
  const [revealed, setRevealed] = useState<{ name: string; secret: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const busyRef = useRef(false);
  const revealIntro = useRef<HTMLParagraphElement>(null);
  const close = useCallback(() => {
    if (!busyRef.current) onClose();
  }, [onClose]);

  useEffect(() => {
    if (revealed) revealIntro.current?.focus();
  }, [revealed]);

  const name = label.trim();
  const duplicateName = action.kind === "generate" && tokens.some((item) =>
    item.status === "active" && item.name.toLowerCase() === name.toLowerCase(),
  );
  const invalid = action.kind === "generate" && (!name || name.length > MCP_TOKEN_NAME_LIMIT || duplicateName);

  async function submit() {
    if (revealed) {
      close();
      return;
    }
    if (busyRef.current || invalid || stale) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      if (action.kind === "revoke") {
        await revokeMcpToken(action.token.id);
        onChanged(action.token.name + " has been turned off.");
        onClose();
        return;
      }
      const issued = await (action.kind === "generate" ? generateMcpToken(name, days) : rotateMcpToken(action.token));
      // The plaintext exists only in this dialog until it closes.
      setRevealed({ name: issued.token.name, secret: issued.secret });
      onChanged(action.kind === "generate" ? "Token generated." : "Token replaced.");
    } catch (reason) {
      setError(adminError(reason, "Could not change the token."));
      onRefresh();
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit();
  }

  return (
    <div onKeyDownCapture={(event) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      close();
    }}>
      <Modal
        open size="sm" modalLabel="Personal MCP tokens"
        modalHeading={revealed ? "Your token is ready" : labels[action.kind].title}
        primaryButtonText={revealed ? "Done" : busy ? "Saving…" : labels[action.kind].submit}
        secondaryButtonText={revealed ? undefined : "Cancel"}
        selectorPrimaryFocus={action.kind === "generate" ? "#mcp-token-name" : ".cds--btn--secondary"}
        primaryButtonDisabled={busy || (!revealed && (invalid || stale))}
        danger={!revealed && action.kind !== "generate"}
        preventCloseOnClickOutside
        onRequestClose={close}
        onSecondarySubmit={close}
        onRequestSubmit={() => void submit()}
      >
        <Stack gap={5}>
          {revealed ? (
            <>
              <p ref={revealIntro} tabIndex={-1}>Copy this token now. Firstout shows the full token only here.</p>
              <div>
                <p className="cds--type-label-01" id="mcp-issued-token">{revealed.name}</p>
                <CodeSnippet type="single" aria-labelledby="mcp-issued-token" copyText={revealed.secret} copyButtonDescription="Copy token" feedback="Copied">
                  {revealed.secret}
                </CodeSnippet>
              </div>
              <p>Keep it private like a password. If you lose it, replace the token and update your MCP connection.</p>
            </>
          ) : (
            <>
              {error && <InlineNotification lowContrast kind="error" title="Token change failed" subtitle={error} hideCloseButton />}
              {stale && !error && <InlineNotification lowContrast kind="info" title="This token has changed" subtitle="Close this dialog and check the latest token before replacing it." hideCloseButton />}
              {action.kind === "generate" ? (
                <form onSubmit={submitForm}>
                  <Stack gap={5}>
                    <TextInput
                      id="mcp-token-name" labelText="Token name" helperText="Use a name you’ll recognise, such as Shop laptop."
                      value={label} maxLength={MCP_TOKEN_NAME_LIMIT} disabled={busy}
                      invalid={duplicateName} invalidText="An active token already has this name."
                      onChange={(event) => { setLabel(event.target.value); setError(""); }}
                    />
                    <Select id="mcp-token-expiry" labelText="Expires after" value={String(days)} disabled={busy}
                      onChange={(event) => {
                        const selected = MCP_TOKEN_EXPIRY_DAYS.find((choice) => String(choice) === event.target.value);
                        if (selected) setDays(selected);
                      }}>
                      {MCP_TOKEN_EXPIRY_DAYS.map((choice) => <SelectItem key={choice} value={String(choice)} text={choice + " days"} />)}
                    </Select>
                  </Stack>
                </form>
              ) : action.kind === "rotate" ? (
                <p>Replace <strong>{action.token.name}</strong>. The current token stops working immediately. Update your MCP connection with the new token.</p>
              ) : (
                <p>Turn off <strong>{action.token.name}</strong>. Any MCP connection using this token loses access immediately.</p>
              )}
            </>
          )}
        </Stack>
      </Modal>
    </div>
  );
}
