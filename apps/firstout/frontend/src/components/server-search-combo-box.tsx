"use client";

import { ComboBox } from "@carbon/react";
import { useState } from "react";

export type SearchOption = { id: string; label: string };

/**
 * The selected option, even when the latest server search no longer returns it: the
 * current result for that id, else the option staff picked.
 */
export function selectedSearchOption<T extends SearchOption>(items: T[], selectedId: string, picked: T | null): T | null {
  if (!selectedId) return null;
  return items.find((item) => item.id === selectedId) ?? (picked?.id === selectedId ? picked : null);
}

/** The server results with the selected option kept in the list, so the combo box can show it. */
export function itemsWithSelection<T extends SearchOption>(items: T[], selected: T | null): T[] {
  return selected && !items.some((item) => item.id === selected.id) ? [selected, ...items] : items;
}

/**
 * The search to send for what is in the input, or null to keep the current search. Selecting
 * writes the option's label into the input; that label is not a search.
 */
export function searchForInput(input: string, selected: SearchOption | null): string | null {
  return selected && input === selected.label ? null : input;
}

/**
 * A Carbon combo box over server search results. The page owns the selected id and the
 * search text; this keeps the selection showing whatever the search returns.
 */
export function ServerSearchComboBox<T extends SearchOption>({
  id,
  titleText,
  placeholder,
  items,
  selectedId,
  onSelect,
  onSearch,
  helperText,
}: {
  id: string;
  titleText: string;
  placeholder: string;
  items: T[];
  selectedId: string;
  onSelect: (option: T | null) => void;
  onSearch: (query: string) => void;
  helperText?: string;
}) {
  const [picked, setPicked] = useState<T | null>(null);
  const selected = selectedSearchOption(items, selectedId, picked);
  // A prefilled id has no pick yet: remember it once a search returns it.
  if (selected && selected.id !== picked?.id) setPicked(selected);
  return (
    <ComboBox
      id={id}
      titleText={titleText}
      placeholder={placeholder}
      helperText={helperText}
      items={itemsWithSelection(items, selected)}
      itemToString={(item) => item?.label ?? ""}
      selectedItem={selected}
      shouldFilterItem={() => true}
      onInputChange={(value) => {
        const query = searchForInput(value, selected);
        if (query !== null) onSearch(query);
      }}
      onChange={({ selectedItem }) => {
        setPicked(selectedItem ?? null);
        onSelect(selectedItem ?? null);
      }}
    />
  );
}
