"use client";

import {
  Button,
  InlineNotification,
  Modal,
  Select,
  SelectItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createBankRule,
  deleteBankRule,
  listBankRules,
  type Account,
  type BankRule,
} from "@/lib/api";

function accountLabel(account: Pick<Account, "code" | "name">): string {
  return `${account.code} ${account.name}`;
}

type BankRulesModalProps = {
  open: boolean;
  canMutate: boolean;
  bankAccountId: string;
  accounts: Account[];
  onClose: () => void;
  onChanged: () => void;
};

export function BankRulesModal({
  open,
  canMutate,
  bankAccountId,
  accounts,
  onClose,
  onChanged,
}: BankRulesModalProps) {
  const [rules, setRules] = useState<BankRule[]>([]);
  const [pattern, setPattern] = useState("");
  const [targetAccountId, setTargetAccountId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const targetAccounts = useMemo(
    () =>
      accounts
        .filter((account) => !account.is_archived && account.id !== bankAccountId)
        .sort((left, right) => left.code.localeCompare(right.code)),
    [accounts, bankAccountId],
  );

  const accountById = useMemo(
    () => new Map(accounts.map((account) => [account.id, account])),
    [accounts],
  );

  const loadRules = useCallback(async () => {
    if (!bankAccountId) {
      setRules([]);
      return;
    }
    setError(null);
    try {
      setRules(await listBankRules(bankAccountId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bank rules.");
    }
  }, [bankAccountId]);

  useEffect(() => {
    if (open) {
      void loadRules();
    }
  }, [open, loadRules]);

  async function handleCreate() {
    const trimmed = pattern.trim();
    if (!trimmed || !targetAccountId || !bankAccountId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await createBankRule({
        bank_account_id: bankAccountId,
        pattern: trimmed,
        target_account_id: targetAccountId,
      });
      setPattern("");
      await loadRules();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create rule.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(ruleId: string) {
    setBusy(true);
    setError(null);
    try {
      await deleteBankRule(ruleId);
      await loadRules();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete rule.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      size="md"
      modalHeading="Bank rules"
      passiveModal
      onRequestClose={onClose}
    >
      <Stack gap={4}>
        <p className="cds--helper-text">
          Rules suggest a posting account on unmatched lines. Apply is a separate confirm on the
          queue — they do not post automatically.
        </p>
        {error ? (
          <InlineNotification
            kind="error"
            title="Error"
            subtitle={error}
            onCloseButtonClick={() => setError(null)}
            lowContrast
          />
        ) : null}
        {canMutate ? (
          <Stack gap={3}>
            <TextInput
              id="bank-rule-pattern"
              labelText="Pattern"
              placeholder="TELEPHONE"
              value={pattern}
              maxLength={128}
              onChange={(event) => setPattern(event.target.value)}
            />
            <Select
              id="bank-rule-target"
              labelText="Target account"
              value={targetAccountId}
              onChange={(event) => setTargetAccountId(event.target.value)}
            >
              <SelectItem value="" text="Select account" />
              {targetAccounts.map((account) => (
                <SelectItem
                  key={account.id}
                  value={account.id}
                  text={accountLabel(account)}
                />
              ))}
            </Select>
            <Button
              kind="secondary"
              size="sm"
              disabled={busy || !pattern.trim() || !targetAccountId}
              onClick={() => void handleCreate()}
            >
              Add rule
            </Button>
          </Stack>
        ) : null}
        {rules.length === 0 ? (
          <p className="cds--type-body-01">No rules for this recon account.</p>
        ) : (
          <Table size="sm">
            <TableHead>
              <TableRow>
                <TableHeader>Pattern</TableHeader>
                <TableHeader>Target</TableHeader>
                {canMutate ? <TableHeader /> : null}
              </TableRow>
            </TableHead>
            <TableBody>
              {rules.map((rule) => {
                const target = accountById.get(rule.target_account_id);
                return (
                  <TableRow key={rule.id}>
                    <TableCell>{rule.pattern}</TableCell>
                    <TableCell>{target ? accountLabel(target) : rule.target_account_id}</TableCell>
                    {canMutate ? (
                      <TableCell>
                        <Button
                          kind="danger--ghost"
                          size="sm"
                          disabled={busy}
                          onClick={() => void handleDelete(rule.id)}
                        >
                          Delete
                        </Button>
                      </TableCell>
                    ) : null}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Stack>
    </Modal>
  );
}
