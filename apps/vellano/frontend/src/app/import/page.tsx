"use client";

import { Button, Column, Grid, InlineNotification, Stack } from "@carbon/react";
import { useRef, useState } from "react";

import {
  ApiError,
  canMutateCatalogue,
  commitCatalogueImport,
  previewCatalogueImport,
  type CatalogueImportCommit,
  type CatalogueImportPreview,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import { ColumnMapTable } from "./column-map-table";
import { ImportDocs } from "./import-docs";
import { ImportErrors } from "./import-errors";
import {
  appendColumnMap,
  assignHeaderField,
  downloadCsvTemplate,
  INVENTORY_FIELDS,
  INVENTORY_TEMPLATE,
  invertAppliedMap,
  SOH_FIELDS,
  SOH_TEMPLATE,
} from "./import-maps";
import { UploadZone } from "./upload-zone";

function buildFormData(
  inventory: File,
  soh: File | null,
  inventoryMap: Record<string, string>,
  sohMap: Record<string, string>,
  sendMaps: boolean,
): FormData {
  const formData = new FormData();
  formData.append("inventory", inventory);
  if (soh) {
    formData.append("soh", soh);
  }
  if (sendMaps) {
    appendColumnMap(formData, "inventory_map", inventoryMap);
    if (soh) {
      appendColumnMap(formData, "soh_map", sohMap);
    }
  }
  return formData;
}

export default function ImportPage() {
  const { user } = useAuth();
  const canMutate = canMutateCatalogue(user);
  const [inventoryFile, setInventoryFile] = useState<File | null>(null);
  const [sohFile, setSohFile] = useState<File | null>(null);
  const [inventoryMap, setInventoryMap] = useState<Record<string, string>>({});
  const [sohMap, setSohMap] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<CatalogueImportPreview | null>(null);
  const [mapsDirty, setMapsDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CatalogueImportCommit | null>(null);
  const previewRequest = useRef(0);

  async function runPreview(
    inventory: File,
    soh: File | null,
    nextInventoryMap: Record<string, string>,
    nextSohMap: Record<string, string>,
    sendMaps: boolean,
  ) {
    const requestId = ++previewRequest.current;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const data = await previewCatalogueImport(
        buildFormData(inventory, soh, nextInventoryMap, nextSohMap, sendMaps),
      );
      if (requestId !== previewRequest.current) {
        return;
      }
      setPreview(data);
      setInventoryMap(
        invertAppliedMap(data.inventory.applied_map, data.inventory.suggested_map, data.inventory.headers),
      );
      setSohMap(
        data.soh
          ? invertAppliedMap(data.soh.applied_map, data.soh.suggested_map, data.soh.headers)
          : {},
      );
      setMapsDirty(false);
    } catch (err) {
      if (requestId !== previewRequest.current) {
        return;
      }
      setPreview(null);
      setError(err instanceof ApiError ? err.message : "Preview failed.");
    } finally {
      if (requestId === previewRequest.current) {
        setBusy(false);
      }
    }
  }

  function handleInventoryFile(file: File | null) {
    setInventoryFile(file);
    setInventoryMap({});
    setPreview(null);
    setResult(null);
    setMapsDirty(false);
    if (file && canMutate) {
      void runPreview(file, sohFile, {}, sohMap, false);
    }
  }

  function handleSohFile(file: File | null) {
    setSohFile(file);
    setSohMap({});
    setResult(null);
    if (!inventoryFile) {
      setPreview(null);
      return;
    }
    if (canMutate) {
      void runPreview(inventoryFile, file, inventoryMap, {}, true);
    }
  }

  async function handleCommit() {
    if (!inventoryFile || !preview?.ok || mapsDirty) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const data = await commitCatalogueImport(
        buildFormData(inventoryFile, sohFile, inventoryMap, sohMap, true),
      );
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Import failed.");
    } finally {
      setBusy(false);
    }
  }

  const canStart = Boolean(canMutate && inventoryFile && preview?.ok && !mapsDirty && !busy);

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Import CSV</h1>
          <p className="cds--type-body-01">
            Bulk import products and stock on hand (SOH). Required format based on Cin7 standards.
            Accepts `.csv` only.
          </p>
        </div>
        {inventoryFile || sohFile || preview || result ? (
          <Button
            kind="secondary"
            disabled={busy}
            onClick={() => {
              setInventoryFile(null);
              setSohFile(null);
              setInventoryMap({});
              setSohMap({});
              setPreview(null);
              setMapsDirty(false);
              setError(null);
              setResult(null);
            }}
          >
            Cancel
          </Button>
        ) : null}
      </div>

      {!canMutate ? (
        <InlineNotification
          kind="info"
          title="Read only"
          subtitle="Only owner and buyer can import catalogue CSVs."
          hideCloseButton
          lowContrast
        />
      ) : null}
      {error ? (
        <InlineNotification
          kind="error"
          title="Import"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}
      {result ? (
        <InlineNotification
          kind="success"
          title="Import complete"
          subtitle={`Created ${result.created_skus} SKUs, updated ${result.updated_skus} SKUs, ${result.soh_rows} SOH rows.`}
          onCloseButtonClick={() => setResult(null)}
          lowContrast
        />
      ) : null}

      <Grid condensed fullWidth>
        <Column lg={8} md={4} sm={4}>
          <UploadZone
            title="1. Inventory List CSV"
            description="Create or update products. Required."
            file={inventoryFile}
            disabled={!canMutate || busy}
            templateLabel="Download inventory template"
            onFile={handleInventoryFile}
            onDownloadTemplate={() => downloadCsvTemplate("inventory-template.csv", INVENTORY_TEMPLATE)}
          />
        </Column>
        <Column lg={8} md={4} sm={4}>
          <UploadZone
            title="2. Stock on Hand CSV (optional)"
            description="Set on-hand quantities per location."
            file={sohFile}
            disabled={!canMutate || busy}
            templateLabel="Download SOH template"
            onFile={handleSohFile}
            onDownloadTemplate={() => downloadCsvTemplate("soh-template.csv", SOH_TEMPLATE)}
          />
        </Column>
      </Grid>

      <ImportDocs />

      {preview ? (
        <Stack gap={5}>
          <ColumnMapTable
            idPrefix="inventory"
            title="Preview & Column Mapping — Inventory"
            description={`${preview.inventory.row_count} rows · ${preview.inventory.create_count} create · ${preview.inventory.update_count} update`}
            headers={preview.inventory.headers}
            sampleRow={preview.inventory.sample_row}
            headerToField={inventoryMap}
            fields={INVENTORY_FIELDS}
            disabled={!canMutate || busy}
            onChange={(header, field) => {
              setInventoryMap((prev) => assignHeaderField(prev, header, field));
              setMapsDirty(true);
            }}
          />
          {preview.soh ? (
            <ColumnMapTable
              idPrefix="soh"
              title="Preview & Column Mapping — Stock on Hand"
              description={`${preview.soh.row_count} rows`}
              headers={preview.soh.headers}
              sampleRow={preview.soh.sample_row}
              headerToField={sohMap}
              fields={SOH_FIELDS}
              disabled={!canMutate || busy}
              onChange={(header, field) => {
                setSohMap((prev) => assignHeaderField(prev, header, field));
                setMapsDirty(true);
              }}
            />
          ) : null}
          {preview.errors.length > 0 ? <ImportErrors errors={preview.errors} /> : null}
          {canMutate ? (
            <Stack gap={4}>
              <Button
                kind="secondary"
                disabled={busy || !inventoryFile}
                onClick={() => {
                  if (inventoryFile) {
                    void runPreview(inventoryFile, sohFile, inventoryMap, sohMap, true);
                  }
                }}
              >
                {busy ? "Working…" : "Re-preview"}
              </Button>
              <Button kind="primary" disabled={!canStart} onClick={() => void handleCommit()}>
                {busy ? "Working…" : "Start Import"}
              </Button>
            </Stack>
          ) : null}
        </Stack>
      ) : null}
    </Stack>
  );
}
