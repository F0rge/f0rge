"use client";

import { Add, Close, Filter } from "@carbon/icons-react";
import { Button, Search, Select, SelectItem, TextInput } from "@carbon/react";
import { useState } from "react";
import { fieldOperators, quickFilterValue, workspaceScalar, workspaceStateForKey } from "@/lib/record-workspace";
import type {
  WorkspaceFilter,
  WorkspaceQuery,
  WorkspaceValue,
} from "@/lib/record-workspace-api";
import type { WorkspaceField } from "./types";
import styles from "./record-workspace.module.css";

function options(field: WorkspaceField) {
  return field.type === "boolean"
    ? [
        { value: "true", label: "Yes" },
        { value: "false", label: "No" },
      ]
    : (field.options ?? []);
}
export function WorkspaceFieldValue({
  field,
  value,
  onChange,
  id,
  disabled = false,
}: {
  field: WorkspaceField;
  value: WorkspaceValue;
  onChange: (value: WorkspaceValue) => void;
  id: string;
  disabled?: boolean;
}) {
  return field.type === "enum" || field.type === "boolean" ? (
    <Select
      id={id}
      labelText={`${field.label} value`}
      hideLabel
      value={String(value ?? "")}
      disabled={disabled}
      onChange={(event) => onChange(workspaceScalar(event.target.value, field.type))}
    >
      <SelectItem value="" text="Choose a value" />
      {options(field).map((item) => (
        <SelectItem key={item.value} value={item.value} text={item.label} />
      ))}
    </Select>
  ) : (
    <TextInput
      id={id}
      labelText={`${field.label} value`}
      hideLabel
      type={
        field.type === "number"
          ? "number"
          : field.type === "date"
            ? "date"
            : "text"
      }
      value={String(value ?? "")}
      disabled={disabled}
      onChange={(event) => onChange(workspaceScalar(event.target.value, field.type))}
    />
  );
}
interface FilterProps {
  resource: string;
  fields: readonly WorkspaceField[];
  query: WorkspaceQuery;
  search: string;
  onSearch: (value: string) => void;
  update: (patch: Partial<WorkspaceQuery>) => void;
}
export function WorkspaceFilters({
  resource,
  fields,
  query,
  search,
  onSearch,
  update,
}: FilterProps) {
  const [open, setOpen] = useState(false);
  const key = JSON.stringify([query.filters, query.match]);
  const [draftState, setDraft] = useState({
    key,
    filters: query.filters,
    match: query.match,
  });
  const draft = workspaceStateForKey(draftState, {
    key,
    filters: query.filters,
    match: query.match,
  });
  if (draftState.key !== key) setDraft(draft);
  const editRule = (index: number, patch: Partial<WorkspaceFilter>) =>
    setDraft({
      ...draft,
      filters: draft.filters.map((rule, at) =>
        at === index ? { ...rule, ...patch } : rule,
      ),
    });
  const quick = (field: WorkspaceField, value: string) => {
    const filters = query.filters.filter((rule) => rule.field !== field.key);
    if (value)
      filters.push({
        field: field.key,
        operator: field.type === "number" && value === "positive" ? "gt" : "eq",
        value: field.type === "number" ? 0 : workspaceScalar(value, field.type),
      });
    update({ filters });
  };
  return (
    <>
      <div className={styles.filters}>
        <div className={styles.search}>
          <Search
            id={`${resource}-search`}
            labelText={`Search ${resource}`}
            placeholder="Search by name or reference"
            value={search}
            onChange={(event) => onSearch(event.target.value)}
          />
        </div>
        {fields
          .filter((field) => field.quick)
          .map((field) => {
            const current = query.filters.find(
              (rule) => rule.field === field.key,
            );
            const value = quickFilterValue(field.type, current);
            return (
              <Select
                key={field.key}
                id={`${resource}-quick-${field.key}`}
                labelText={field.label}
                value={value}
                onChange={(event) => quick(field, event.target.value)}
              >
                <SelectItem
                  value=""
                  text={
                    field.type === "number"
                      ? "Any amount"
                      : (field.allLabel ?? `All ${field.label.toLowerCase()}s`)
                  }
                />
                {field.type === "number" ? (
                  <>
                    <SelectItem value="positive" text="Greater than zero" />
                    <SelectItem value="zero" text="Zero balance" />
                  </>
                ) : (
                  options(field).map((item) => (
                    <SelectItem
                      key={item.value}
                      value={item.value}
                      text={item.label}
                    />
                  ))
                )}
              </Select>
            );
          })}
        {fields.length > 0 && (
          <Button
            kind="ghost"
            renderIcon={Filter}
            aria-expanded={open}
            aria-controls={`${resource}-advanced-filters`}
            onClick={() => setOpen(!open)}
          >
            Advanced filters
            {query.filters.length ? ` (${query.filters.length})` : ""}
          </Button>
        )}
      </div>
      {query.filters.length > 0 && (
        <div className={styles.chips} aria-label="Applied filters">
          <span className={styles.matchLabel}>
            Match {query.match === "any" ? "any condition" : "all conditions"}
          </span>
          {query.filters.map((rule, index) => (
            <button
              key={`${rule.field}-${index}`}
              onClick={() =>
                update({
                  filters: query.filters.filter((_, at) => at !== index),
                })
              }
              aria-label={`Remove ${fields.find((field) => field.key === rule.field)?.label ?? rule.field} filter`}
            >
              {fields.find((field) => field.key === rule.field)?.label ??
                rule.field}{" "}
              {
                fieldOperators(
                  fields.find((field) => field.key === rule.field)?.type ??
                    "text",
                ).find((op) => op.value === rule.operator)?.label
              }{" "}
              {rule.value === null ||
              rule.operator === "empty" ||
              rule.operator === "not_empty"
                ? ""
                : String(rule.value)}
              <Close size={12} aria-hidden="true" />
            </button>
          ))}
          <Button
            kind="ghost"
            size="sm"
            onClick={() => update({ filters: [], q: "", match: "all" })}
          >
            Reset filters
          </Button>
        </div>
      )}
      {open && (
        <section
          className={styles.filterBuilder}
          id={`${resource}-advanced-filters`}
          aria-label="Advanced filters"
        >
          <div className={styles.builderHeading}>
            <h2>Advanced filters</h2>
            <Select
              id={`${resource}-match`}
              labelText="Match"
              inline
              value={draft.match}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  match: event.target.value === "any" ? "any" : "all",
                })
              }
            >
              <SelectItem value="all" text="All conditions" />
              <SelectItem value="any" text="Any condition" />
            </Select>
          </div>
          {draft.filters.map((rule, index) => {
            const field =
              fields.find((item) => item.key === rule.field) ?? fields[0];
            if (!field) return null;
            return (
              <div className={styles.filterRule} key={index}>
                <Select
                  id={`${resource}-field-${index}`}
                  labelText={`Condition ${index + 1} field`}
                  hideLabel
                  value={rule.field}
                  onChange={(event) =>
                    editRule(index, {
                      field: event.target.value,
                      operator: "eq",
                      value: "",
                    })
                  }
                >
                  {fields.map((item) => (
                    <SelectItem
                      key={item.key}
                      value={item.key}
                      text={item.label}
                    />
                  ))}
                </Select>
                <Select
                  id={`${resource}-operator-${index}`}
                  labelText={`Condition ${index + 1} operator`}
                  hideLabel
                  value={rule.operator}
                  onChange={(event) =>
                    editRule(index, {
                      operator: event.target
                        .value as WorkspaceFilter["operator"],
                    })
                  }
                >
                  {fieldOperators(field.type).map((item) => (
                    <SelectItem
                      key={item.value}
                      value={item.value}
                      text={item.label}
                    />
                  ))}
                </Select>
                <WorkspaceFieldValue
                  field={field}
                  value={rule.value}
                  onChange={(value) => editRule(index, { value })}
                  id={`${resource}-value-${index}`}
                  disabled={
                    rule.operator === "empty" || rule.operator === "not_empty"
                  }
                />
                <Button
                  kind="ghost"
                  hasIconOnly
                  renderIcon={Close}
                  iconDescription={`Remove condition ${index + 1}`}
                  onClick={() =>
                    setDraft({
                      ...draft,
                      filters: draft.filters.filter((_, at) => at !== index),
                    })
                  }
                />
              </div>
            );
          })}
          <div className={styles.builderActions}>
            <Button
              kind="ghost"
              renderIcon={Add}
              disabled={!fields.length || draft.filters.length >= 20}
              onClick={() =>
                setDraft({
                  ...draft,
                  filters: [
                    ...draft.filters,
                    { field: fields[0].key, operator: "eq", value: "" },
                  ],
                })
              }
            >
              Add condition
            </Button>
            <div>
              <Button
                kind="ghost"
                onClick={() => {
                  setDraft({ key, filters: [], match: "all" });
                  update({ filters: [], match: "all" });
                }}
              >
                Reset
              </Button>
              <Button
                onClick={() =>
                  update({ filters: draft.filters, match: draft.match })
                }
              >
                Apply filters
              </Button>
            </div>
          </div>
        </section>
      )}
    </>
  );
}
