"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import type { SettingsSection } from "@/lib/admin-navigation";
import type { AppSettings, DocumentSequenceUpdate } from "@/lib/api";

export type SettingsDraft = { fields: Partial<AppSettings>; sequence?: DocumentSequenceUpdate };

function createDraftStore() {
  const drafts = new Map<SettingsSection, SettingsDraft>();
  return {
    get: (section: SettingsSection) => drafts.get(section),
    set(section: SettingsSection, draft?: SettingsDraft) {
      if (!draft) drafts.delete(section);
      else if (JSON.stringify(drafts.get(section)) !== JSON.stringify(draft)) drafts.set(section, draft);
    },
  };
}

const Context = createContext<ReturnType<typeof createDraftStore> | null>(null);

export function SettingsDraftsProvider({ children }: { children: ReactNode }) {
  // A new staff session or active organisation remounts the provider.
  // Keep company and bank edits in memory for same-document navigation only.
  const [drafts] = useState(createDraftStore);
  return <Context.Provider value={drafts}>{children}</Context.Provider>;
}

export function useSettingsDrafts() {
  const drafts = useContext(Context);
  if (!drafts) throw new Error("Settings drafts require a staff session.");
  return drafts;
}

export function changedSettingsFields<T extends object>(saved: T, fields: Partial<T>): Partial<T> {
  return Object.fromEntries(Object.entries(fields).filter(([key, value]) =>
    JSON.stringify(value) !== JSON.stringify(saved[key as keyof T]),
  )) as Partial<T>;
}
