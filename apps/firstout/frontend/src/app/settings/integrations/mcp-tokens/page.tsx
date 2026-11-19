"use client";

import { Add, Password, Renew } from "@carbon/icons-react";
import {
  Accordion, AccordionItem, Button, CodeSnippet, InlineNotification, Layer,
  OverflowMenu, OverflowMenuItem, Stack, Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow, DataTableSkeleton, Tag,
} from "@carbon/react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { AdminPageHeader } from "@/components/administration";
import { PageLoading } from "@/components/page-loading";
import { useAuth } from "@/lib/auth";
import { listMcpTokens, type McpToken, type McpTokenActivity } from "@/lib/mcp-tokens";
import { workspaceIdentity } from "@/lib/record-workspace";
import { adminError } from "@/lib/staff-administration";
import { McpTokenDialog, type TokenAction } from "./token-dialog";
import styles from "./mcp-tokens.module.css";

const activityLabels: Record<McpTokenActivity["action"], string> = {
  generated: "Generated token",
  rotated: "Replaced token",
  revoked: "Turned off token",
  catalogue_searched: "Searched catalogue",
};
const statusLabels = {
  active: { text: "Active", type: "green" },
  expired: { text: "Expired", type: "warm-gray" },
  revoked: { text: "Revoked", type: "gray" },
} as const;
const dateFormat = new Intl.DateTimeFormat("en-ZA", { dateStyle: "medium" });
const dateTimeFormat = new Intl.DateTimeFormat("en-ZA", { dateStyle: "medium", timeStyle: "short" });

function TokenDate({ value, showTime = false }: { value: string | null; showTime?: boolean }) {
  if (!value) return <>Never</>;
  const date = new Date(value);
  return <time dateTime={value} title={dateTimeFormat.format(date)}>{(showTime ? dateTimeFormat : dateFormat).format(date)}</time>;
}

function TokenDirectory({ organisation }: { organisation: string }) {
  const directory = useQuery({ queryKey: ["personal-mcp-tokens"], queryFn: listMcpTokens });
  const [action, setAction] = useState<TokenAction | null>(null);
  const [notice, setNotice] = useState("");
  const trigger = useRef<HTMLElement | null>(null);
  const generate = useRef<HTMLButtonElement>(null);
  const rows = directory.data?.tokens ?? [];

  function open(next: TokenAction, from: HTMLElement | null) {
    setNotice("");
    trigger.current = from;
    setAction(next);
  }

  function close() {
    setAction(null);
    requestAnimationFrame(() => {
      if (trigger.current?.isConnected) trigger.current.focus();
      else generate.current?.focus();
    });
  }

  function reload() {
    void directory.refetch();
  }

  return (
    <Stack gap={5} className={styles.page}>
      <AdminPageHeader title="MCP tokens" description={"Each token uses your current Firstout permissions in " + organisation + "."} />
      {notice && <InlineNotification kind="success" title={notice} lowContrast onCloseButtonClick={() => setNotice("")} />}
      <Layer>
        <section className={styles.tokenList} aria-labelledby="personal-tokens-title">
          <header className={styles.listHeader}>
            <div className={styles.headerText}>
              <h2 id="personal-tokens-title">Your tokens</h2>
              <p>Give each token a name you’ll recognise.</p>
            </div>
            <div className={styles.actions}>
              <Button
                kind="ghost" size="md" renderIcon={Renew} hasIconOnly iconDescription="Reload tokens"
                disabled={directory.isFetching} onClick={reload}
              />
              <Button
                ref={generate} size="md" renderIcon={Add}
                disabled={!directory.data} onClick={(event) => open({ kind: "generate" }, event.currentTarget)}
              >
                Generate token
              </Button>
            </div>
          </header>
          {directory.error && (
            <div className={styles.error}>
              <InlineNotification kind="error" title="Could not load MCP tokens"
                subtitle={adminError(directory.error, "Token information is unavailable.")} hideCloseButton lowContrast />
              <Button kind="tertiary" size="sm" disabled={directory.isFetching} onClick={reload}>Retry</Button>
            </div>
          )}
          {directory.isPending ? (
            <DataTableSkeleton aria-label="Loading MCP tokens" columnCount={5} rowCount={3} showToolbar={false} showHeader={false} />
          ) : rows.length > 0 ? (
            <Table size="lg" aria-label="Your MCP tokens" aria-busy={directory.isFetching} className={styles.table}>
              <TableHead>
                <TableRow>
                  <TableHeader>Token</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader className={styles.dateCell}>Last used</TableHeader>
                  <TableHeader className={styles.dateCell}>Expires</TableHeader>
                  <TableHeader><span className="firstout-sr-only">Manage token</span></TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((item) => (
                  <TokenRow key={item.id} token={item} open={open} />
                ))}
              </TableBody>
            </Table>
          ) : directory.data && <p className={styles.empty} role="status">You have no MCP tokens yet.</p>}
        </section>
      </Layer>
      {directory.data && (
        <>
          <div className={styles.endpoint}>
            <p className="cds--type-label-01" id="mcp-server-url">MCP server URL</p>
            <CodeSnippet type="single" aria-labelledby="mcp-server-url" copyButtonDescription="Copy server URL"
              copyText={directory.data.endpoint} feedback="Copied">{directory.data.endpoint}</CodeSnippet>
          </div>
          <Accordion>
            <AccordionItem title="Recent activity">
              {directory.data.activity.length ? (
                <ul className={styles.activity}>
                  {directory.data.activity.map((item) => (
                    <li key={item.id}>
                      <strong>{activityLabels[item.action]}</strong>
                      <span>{item.token_name} · {item.source === "mcp" ? "MCP" : "Firstout"} · <TokenDate value={item.occurred_at} showTime /></span>
                      {item.result === "denied" && <Tag size="sm" type="red">Denied</Tag>}
                    </li>
                  ))}
                </ul>
              ) : <p>No recent activity.</p>}
            </AccordionItem>
          </Accordion>
        </>
      )}
      {action && (
        <McpTokenDialog
          action={action}
          tokens={rows}
          stale={action.kind === "rotate" && !rows.some((row) => row.id === action.token.id && row.version === action.token.version && row.status === "active")}
          onClose={close}
          onRefresh={reload}
          onChanged={(message) => {
            setNotice(message);
            reload();
          }}
        />
      )}
    </Stack>
  );
}

function TokenRow({
  token, open,
}: {
  token: McpToken;
  open: (action: TokenAction, from: HTMLElement | null) => void;
}) {
  const menuTrigger = useRef<HTMLSpanElement>(null);
  const status = statusLabels[token.status];
  return (
    <TableRow>
      <TableCell>
        <div className={styles.tokenName}>
          <Password size={16} aria-hidden="true" />
          <div>
            <strong>{token.name}</strong>
            <span>Ending in <code>{token.suffix}</code></span>
            <span className={styles.mobileDates}>
              Last used <TokenDate value={token.last_used_at} showTime />
              <br />
              Expires <TokenDate value={token.expires_at} />
            </span>
          </div>
        </div>
      </TableCell>
      <TableCell><Tag size="sm" type={status.type}>{status.text}</Tag></TableCell>
      <TableCell className={styles.dateCell}><TokenDate value={token.last_used_at} showTime /></TableCell>
      <TableCell className={styles.dateCell}><TokenDate value={token.expires_at} /></TableCell>
      <TableCell className={styles.menu}>
        {token.status === "active" && (
          <span ref={menuTrigger}>
            <OverflowMenu flipped size="sm" aria-label={"Manage " + token.name} iconDescription={"Manage " + token.name}
          >
            <OverflowMenuItem itemText="Replace token" onClick={() => open({ kind: "rotate", token }, menuTrigger.current?.querySelector("button") ?? null)} />
            <OverflowMenuItem itemText="Turn off token" isDelete onClick={() => open({ kind: "revoke", token }, menuTrigger.current?.querySelector("button") ?? null)} />
            </OverflowMenu>
          </span>
        )}
      </TableCell>
    </TableRow>
  );
}

function ScopedTokenDirectory({ organisation }: { organisation: string }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  }));
  return <QueryClientProvider client={client}><TokenDirectory organisation={organisation} /></QueryClientProvider>;
}

export default function McpTokensPage() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoading label="Loading MCP tokens…" />;
  if (!user) {
    return <InlineNotification kind="error" title="Sign in required" subtitle="Sign in to manage your personal MCP tokens." hideCloseButton />;
  }
  return <ScopedTokenDirectory key={workspaceIdentity(user)} organisation={user.team.name} />;
}
