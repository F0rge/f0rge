"use client";

import { Button, InlineNotification, Stack, TextArea, TextInput, Toggle } from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  canManageUsers,
  getPaymentReminderSettings,
  updatePaymentReminderSettings,
  type PaymentReminderStep,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { REMINDER_PLACEHOLDER_HELP, reminderOffsetLabel } from "@/lib/payment-reminders";

export function PaymentRemindersSettings() {
  const { user } = useAuth();
  const canConfigure = canManageUsers(user);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [steps, setSteps] = useState<PaymentReminderStep[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPaymentReminderSettings();
      setEnabled(data.enabled);
      setSteps(data.steps);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load payment reminders.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canConfigure) {
      void load();
    } else {
      setLoading(false);
    }
  }, [canConfigure, load]);

  function updateStep(index: number, patch: Partial<PaymentReminderStep>) {
    setSteps((current) => current.map((step, i) => (i === index ? { ...step, ...patch } : step)));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await updatePaymentReminderSettings({ enabled, steps });
      setEnabled(saved.enabled);
      setSteps(saved.steps);
      setNotice(saved.enabled ? "Payment reminders are on." : "Payment reminders are off.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save payment reminders.");
    } finally {
      setSaving(false);
    }
  }

  if (!canConfigure) {
    return <p className="cds--type-body-01">Only an owner can change payment reminders.</p>;
  }

  return (
    <Stack gap={5}>
      <div>
        <h2 className="cds--type-productive-heading-03">Payment reminders</h2>
        <p className="cds--type-body-01 firstout-muted-text">
          Off until you turn them on. Firstout emails one reminder per invoice each day the job
          runs, using the outstanding balance, and stops when the invoice is paid.
        </p>
      </div>
      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}
      {notice ? (
        <InlineNotification
          kind="success"
          title="Saved"
          subtitle={notice}
          onCloseButtonClick={() => setNotice(null)}
          lowContrast
        />
      ) : null}
      <Toggle
        id="payment-reminders-enabled"
        labelText="Send payment reminders"
        labelA="Off"
        labelB="On"
        toggled={enabled}
        onToggle={setEnabled}
        disabled={loading || saving}
      />
      <p className="cds--type-helper-text-01">{REMINDER_PLACEHOLDER_HELP}</p>
      {steps.map((step, index) => (
        <Stack gap={3} key={`${step.offset_days}-${index}`}>
          <TextInput
            id={`reminder-offset-${index}`}
            labelText={`Step ${index + 1} — day offset (${reminderOffsetLabel(Number(step.offset_days) || 0)})`}
            type="number"
            value={String(step.offset_days)}
            onChange={(event) =>
              updateStep(index, { offset_days: Number(event.target.value) })
            }
            disabled={loading || saving}
          />
          <TextInput
            id={`reminder-subject-${index}`}
            labelText="Subject"
            value={step.subject}
            onChange={(event) => updateStep(index, { subject: event.target.value })}
            disabled={loading || saving}
          />
          <TextArea
            id={`reminder-body-${index}`}
            labelText="Email"
            value={step.body}
            onChange={(event) => updateStep(index, { body: event.target.value })}
            disabled={loading || saving}
            rows={6}
          />
          <Button
            kind="danger--ghost"
            size="sm"
            disabled={loading || saving}
            onClick={() => setSteps((current) => current.filter((_, i) => i !== index))}
          >
            Remove step
          </Button>
        </Stack>
      ))}
      <Stack gap={3} orientation="horizontal">
        <Button
          kind="tertiary"
          disabled={loading || saving || steps.length >= 12}
          onClick={() =>
            setSteps((current) => [
              ...current,
              {
                offset_days: 0,
                subject: "Invoice {invoice_number}",
                body: "Hi {customer_name},\n\nInvoice {invoice_number} for {amount_owing} is due on {due_date}.\n\n{invoice_pdf}\n\nThank you.",
              },
            ])
          }
        >
          Add step
        </Button>
        <Button disabled={loading || saving} onClick={() => void handleSave()}>
          {saving ? "Saving…" : "Save reminders"}
        </Button>
      </Stack>
    </Stack>
  );
}
