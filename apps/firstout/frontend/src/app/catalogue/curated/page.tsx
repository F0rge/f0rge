"use client";

import { ArrowLeft } from "@carbon/icons-react";
import {
  Button,
  FileUploader,
  InlineNotification,
  Modal,
  Select,
  SelectItem,
  Stack,
  Tile,
} from "@carbon/react";
import Link from "next/link";
import { useRef, useState } from "react";

import { PageLoading } from "@/components/page-loading";
import {
  canMutateCatalogue,
  uploadCuratedCatalogue,
  type CuratedCatalogueResult,
  type CuratedCatalogueScope,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const MAX_ARCHIVE_BYTES = 40 * 1024 * 1024;

export default function CuratedCataloguePage() {
  const { user, loading } = useAuth();
  const [archive, setArchive] = useState<File | null>(null);
  const [scope, setScope] = useState<CuratedCatalogueScope>("catalogue");
  const [result, setResult] = useState<CuratedCatalogueResult | null>(null);
  const [error, setError] = useState("");
  const [stage, setStage] = useState<"preview" | "apply" | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const pending = useRef(false);
  const singleSku = scope === "sku";
  const applyLabel = singleSku ? "Apply SKU update" : "Apply catalogue";

  function chooseArchive(file: File | null) {
    setResult(null);
    setError("");
    if (file && (!file.name.toLowerCase().endsWith(".zip") || file.size > MAX_ARCHIVE_BYTES || !file.size)) {
      setArchive(null);
      setError("Choose a non-empty ZIP archive up to 40 MiB.");
      return;
    }
    setArchive(file);
  }

  async function upload(dryRun: boolean) {
    if (pending.current || !archive || (!dryRun && (!result || result.applied))) return;
    pending.current = true;
    setStage(dryRun ? "preview" : "apply");
    setError("");
    try {
      const response = await uploadCuratedCatalogue(archive, dryRun, scope);
      if (response.applied === dryRun) throw new Error("Firstout returned an unexpected import result. Check the catalogue before trying again.");
      setResult(response);
      setConfirmOpen(false);
    } catch (reason) {
      setConfirmOpen(false);
      setError(reason instanceof Error ? reason.message : "The catalogue upload could not be completed.");
    } finally {
      pending.current = false;
      setStage(null);
    }
  }

  if (loading) return <PageLoading label="Loading catalogue import…" />;

  return (
    <Stack gap={6}>
      <div>
        <Button as={Link} href="/catalogue" kind="ghost" renderIcon={ArrowLeft}>Back to catalogue</Button>
        <h1 className="cds--type-productive-heading-04">DasKasas catalogue import</h1>
      </div>
      {user?.role !== "owner" || !canMutateCatalogue(user) ? (
        <InlineNotification kind="error" title="Owner access required" hideCloseButton />
      ) : (
        <Tile>
          <Stack gap={5}>
            <Select
              id="curated-catalogue-scope"
              labelText="Import scope"
              helperText={singleSku ? "Update one selected storefront SKU and its gallery." : "Replace the storefront selection with the reviewed catalogue."}
              value={scope}
              disabled={stage !== null}
              onChange={(event) => {
                setScope(event.target.value === "sku" ? "sku" : "catalogue");
                setResult(null);
                setError("");
                setConfirmOpen(false);
              }}
            >
              <SelectItem value="catalogue" text="Entire catalogue" />
              <SelectItem value="sku" text="Single SKU" />
            </Select>
            <FileUploader
              accept={[".zip", "application/zip"]}
              labelTitle={singleSku ? "Approved SKU archive" : "Approved catalogue archive"}
              labelDescription="ZIP up to 40 MiB."
              buttonLabel="Choose ZIP"
              filenameStatus="edit"
              disabled={stage !== null}
              onChange={(event) => {
                if (event.target instanceof HTMLInputElement) chooseArchive(event.target.files?.[0] ?? null);
              }}
              onDelete={() => chooseArchive(null)}
            />
            {error && <InlineNotification kind="error" title="Catalogue upload failed" subtitle={error} hideCloseButton />}
            {result && <InlineNotification
              kind={result.applied ? "success" : "info"}
              title={singleSku
                ? result.applied ? "SKU updated in Firstout" : "SKU update ready to apply"
                : result.applied ? "Catalogue applied in Firstout" : "Catalogue ready to apply"}
              subtitle={singleSku
                ? `One SKU and ${result.gallery_images} gallery photos.`
                : `${result.selected_skus} selected SKUs, ${result.gallery_images} gallery photos and ${result.groups} variant groups.`}
              hideCloseButton
            />}
            {result?.held_without_price.length ? (
              <p>Awaiting a positive retail price: {result.held_without_price.join(", ")}.</p>
            ) : null}
            <div className="firstout-catalogue-actions">
              <Button
                kind="secondary"
                type="button"
                disabled={!archive || stage !== null || result?.applied}
                onClick={() => void upload(true)}
              >
                {stage === "preview" ? "Checking archive…" : "Preview import"}
              </Button>
              <Button
                type="button"
                disabled={!result || result.applied || stage !== null}
                onClick={() => setConfirmOpen(true)}
              >{applyLabel}</Button>
            </div>
          </Stack>
        </Tile>
      )}
      {confirmOpen && result && <Modal
        open
        danger
        modalHeading={singleSku ? "Apply the approved SKU update?" : "Apply the approved catalogue?"}
        primaryButtonText={stage === "apply" ? "Applying…" : applyLabel}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={stage === "apply"}
        preventCloseOnClickOutside
        onRequestClose={() => { if (stage === null) setConfirmOpen(false); }}
        onRequestSubmit={() => void upload(false)}
      >
        <p>{singleSku
          ? "Apply the reviewed details and gallery to one SKU in this workspace. The shop uses them after synchronization."
          : `Apply the reviewed archive for ${result.selected_skus} SKUs to this Firstout workspace. The shop uses the new selection after synchronization.`}</p>
      </Modal>}
    </Stack>
  );
}
