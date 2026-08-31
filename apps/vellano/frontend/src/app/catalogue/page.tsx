"use client";

import {
  Button,
  DataTable,
  FileUploaderDropContainer,
  FileUploaderItem,
  InlineNotification,
  Modal,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  canMutateCatalogue,
  createSku,
  listSkus,
  uploadSkuPhoto,
  type CreateSkuPayload,
  type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "name", header: "Name" },
  { key: "design", header: "Design" },
  { key: "fabric", header: "Fabric" },
  { key: "our_ref", header: "Our ref" },
  { key: "our_barcode", header: "Our barcode" },
  { key: "supplier_ref", header: "Supplier ref" },
  { key: "photo", header: "Photo" },
] as const;

type SkuRow = {
  id: string;
  name: string;
  design: string;
  fabric: string;
  our_ref: string;
  our_barcode: string;
  supplier_ref: string;
  photo: string;
};

const emptyCreateForm: CreateSkuPayload = {
  our_ref: "",
  our_barcode: "",
  name: "",
  design: "",
  fabric: "",
  supplier_ref: "",
};

export default function CataloguePage() {
  const { user } = useAuth();
  const canMutate = canMutateCatalogue(user?.role);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateSkuPayload>(emptyCreateForm);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);

  const loadSkus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listSkus();
      setSkus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load catalogue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadSkus();
    }
  }, [user, loadSkus]);

  const rows: SkuRow[] = skus.map((entry) => ({
    id: entry.id,
    name: entry.name,
    design: entry.design,
    fabric: entry.fabric,
    our_ref: entry.our_ref,
    our_barcode: entry.our_barcode,
    supplier_ref: entry.supplier_ref ?? "—",
    photo: entry.id,
  }));

  function resetForm() {
    setCreateForm(emptyCreateForm);
    setPhotoFile(null);
  }

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      const payload: CreateSkuPayload = {
        our_ref: createForm.our_ref.trim(),
        our_barcode: createForm.our_barcode.trim(),
        name: createForm.name.trim(),
        design: createForm.design.trim(),
        fabric: createForm.fabric.trim(),
      };
      const supplierRef = createForm.supplier_ref?.trim();
      if (supplierRef) {
        payload.supplier_ref = supplierRef;
      }
      const created = await createSku(payload);
      if (photoFile) {
        await uploadSkuPhoto(created.id, photoFile);
      }
      setCreateOpen(false);
      resetForm();
      await loadSkus();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to add SKU.");
      }
    } finally {
      setSaving(false);
    }
  }

  const formValid =
    createForm.our_ref.trim() &&
    createForm.our_barcode.trim() &&
    createForm.name.trim() &&
    createForm.design.trim() &&
    createForm.fabric.trim();

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Catalogue</h1>
          <p className="cds--type-body-01">
            SKU catalogue — our refs and barcodes distinct from supplier references.
          </p>
        </div>
        {canMutate ? <Button onClick={() => setCreateOpen(true)}>Add SKU</Button> : null}
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

      {loading ? (
        <p className="cds--type-body-01">Loading catalogue…</p>
      ) : skus.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No SKUs"
          subtitle="No catalogue items have been added yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Catalogue" description="All Vellano SKUs">
              <Table {...getTableProps()}>
                <TableHead>
                  <TableRow>
                    {headers.map((header) => (
                      <TableHeader {...getHeaderProps({ header })} key={header.key}>
                        {header.header}
                      </TableHeader>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tableRows.map((row) => {
                    const entry = skus.find((sku) => sku.id === row.id);
                    return (
                      <TableRow {...getRowProps({ row })} key={row.id}>
                        {row.cells.map((cell) => {
                          if (cell.info.header === "photo") {
                            if (entry?.photo_storage_key) {
                              return (
                                <TableCell key={cell.id}>
                                  {/* eslint-disable-next-line @next/next/no-img-element */}
                                  <img
                                    src={`/api/v1/skus/${entry.id}/photo`}
                                    alt={entry.name}
                                    style={{ maxHeight: "3rem", maxWidth: "3rem", objectFit: "cover" }}
                                  />
                                </TableCell>
                              );
                            }
                            return <TableCell key={cell.id}>—</TableCell>;
                          }
                          return <TableCell key={cell.id}>{cell.value}</TableCell>;
                        })}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      )}

      <Modal
        open={createOpen}
        modalHeading="Add SKU"
        primaryButtonText={saving ? "Adding…" : "Add"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <TextInput
            id="create-sku-our-ref"
            labelText="Our ref"
            value={createForm.our_ref}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, our_ref: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-sku-our-barcode"
            labelText="Our barcode"
            value={createForm.our_barcode}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, our_barcode: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-sku-name"
            labelText="Name"
            value={createForm.name}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, name: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-sku-design"
            labelText="Design"
            value={createForm.design}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, design: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-sku-fabric"
            labelText="Fabric"
            value={createForm.fabric}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, fabric: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-sku-supplier-ref"
            labelText="Supplier ref"
            helperText="Supplier's reference — not our barcode"
            value={createForm.supplier_ref ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, supplier_ref: event.target.value }))
            }
          />
          <div>
            <p className="cds--label">Photo (optional)</p>
            <FileUploaderDropContainer
              accept={["image/*"]}
              labelText="Drag and drop an image here or click to upload"
              multiple={false}
              onAddFiles={(_, { addedFiles }) => {
                const file = addedFiles[0];
                if (file && !file.invalidFileType) {
                  setPhotoFile(file);
                }
              }}
            />
            {photoFile ? (
              <FileUploaderItem
                name={photoFile.name}
                status="complete"
                onDelete={() => setPhotoFile(null)}
              />
            ) : null}
          </div>
        </Stack>
      </Modal>
    </Stack>
  );
}
