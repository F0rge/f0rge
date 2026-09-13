"use client";

import {
  Accordion,
  AccordionItem,
  Button,
  DataTable,
  InlineNotification,
  Link,
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
import NextLink from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CostAuditPanel } from "@/components/cost-audit-panel";
import {
  canViewCostAudit,
  formatZarAmount,
  listInventory,
  listLocations,
  type InventorySku,
  type Location,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  activeLocations,
  formatStockQty,
  matchesPipelineChips,
  matchesStockSearch,
  showroomAvailable,
  showroomLocation,
  type StockPipelineChip,
  visibleBins,
} from "@/lib/stock-table";

type StockRow = {
  id: string;
  our_ref: string;
  name: string;
  on_water: string;
  showroom_available: string;
  unit_cost_zar: string;
};

function pipelineChipLabel(chip: StockPipelineChip, locations: Location[]): string {
  if (chip === "on_water") {
    return "On water";
  }
  if (chip === "at_warehouse") {
    const warehouse = activeLocations(locations).find((location) => location.type === "warehouse");
    return warehouse ? `At ${warehouse.name}` : "At warehouse";
  }
  const showroom = showroomLocation(locations);
  return showroom ? `At ${showroom.name}` : "At showroom";
}

export default function StockPage() {
  const router = useRouter();
  const { user } = useAuth();
  const canViewCost = canViewCostAudit(user);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState("");
  const [pipelineChips, setPipelineChips] = useState<StockPipelineChip[]>([]);
  const [selectedSkuId, setSelectedSkuId] = useState<string | null>(null);
  const [auditExpanded, setAuditExpanded] = useState(false);

  const loadInventory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [inventoryData, locationData] = await Promise.all([
        listInventory(),
        listLocations(),
      ]);
      setInventory(inventoryData);
      setLocations(locationData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inventory.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadInventory();
    }
  }, [user, loadInventory]);

  const activeLocationList = useMemo(() => activeLocations(locations), [locations]);
  const showroom = useMemo(() => showroomLocation(locations), [locations]);

  const filteredInventory = useMemo(() => {
    return inventory.filter((entry) => {
      if (!matchesStockSearch(entry, searchFilter)) {
        return false;
      }
      return matchesPipelineChips(entry, pipelineChips, locations);
    });
  }, [inventory, locations, pipelineChips, searchFilter]);

  const tableHeaders = useMemo(() => {
    const headers = [
      { key: "our_ref", header: "Our ref" },
      { key: "name", header: "Name" },
      { key: "on_water", header: "On water" },
      ...activeLocationList.map((location) => ({
        key: `location_${location.id}`,
        header: location.name,
      })),
      { key: "showroom_available", header: "Showroom avail." },
    ];
    if (canViewCost) {
      headers.push({ key: "unit_cost_zar", header: "Unit cost" });
    }
    return headers;
  }, [activeLocationList, canViewCost]);

  const rows: StockRow[] = filteredInventory.map((entry) => ({
    id: entry.sku_id,
    our_ref: entry.our_ref,
    name: entry.name,
    on_water: formatStockQty(entry.on_order),
    showroom_available: formatStockQty(showroomAvailable(entry, showroom)),
    unit_cost_zar: canViewCost ? formatZarAmount(entry.unit_cost_zar) : "—",
  }));

  const togglePipelineChip = (chip: StockPipelineChip) => {
    setPipelineChips((current) =>
      current.includes(chip) ? current.filter((value) => value !== chip) : [...current, chip],
    );
  };

  const handleRowSelect = (skuId: string) => {
    setSelectedSkuId(skuId);
    if (canViewCost) {
      setAuditExpanded(true);
    }
  };

  const skuOptions = useMemo(
    () =>
      inventory.map((entry) => ({
        id: entry.sku_id,
        label: `${entry.our_ref} — ${entry.name}`,
      })),
    [inventory],
  );

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Stock</h1>
        <p className="cds--type-body-01">
          Where stock sits across warehouse and showroom, and what is still on the water. On-water
          units are not sellable until received.
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

      {loading ? (
        <p className="cds--type-body-01">Loading stock…</p>
      ) : inventory.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No stock"
          subtitle="No inventory records yet. Raise a PO and mark on water to see on-order quantities."
          hideCloseButton
          lowContrast
        />
      ) : (
        <div className="vellano-catalogue-panel">
          <div className="vellano-catalogue-toolbar">
            <div className="vellano-catalogue-toolbar__left">
              <TextInput
                id="stock-search"
                labelText="Filter stock"
                hideLabel
                placeholder="Filter by our ref or name…"
                value={searchFilter}
                onChange={(event) => setSearchFilter(event.target.value)}
                size="md"
              />
              <span className="vellano-catalogue-toolbar__divider" aria-hidden />
              <div className="vellano-catalogue-chips" role="group" aria-label="Stock pipeline filter">
                <Button
                  kind={pipelineChips.length === 0 ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => setPipelineChips([])}
                >
                  All
                </Button>
                {(["on_water", "at_warehouse", "at_showroom"] as StockPipelineChip[]).map((chip) => (
                  <Button
                    key={chip}
                    kind={pipelineChips.includes(chip) ? "primary" : "ghost"}
                    size="sm"
                    onClick={() => togglePipelineChip(chip)}
                  >
                    {pipelineChipLabel(chip, locations)}
                  </Button>
                ))}
              </div>
            </div>
          </div>

          <DataTable rows={rows} headers={tableHeaders}>
            {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
              <TableContainer>
                <Table {...getTableProps()} size="sm">
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
                    {tableRows.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={headers.length}>
                          No SKUs match the current filters.
                        </TableCell>
                      </TableRow>
                    ) : (
                      tableRows.map((row) => {
                        const entry = inventory.find((item) => item.sku_id === row.id);
                        const isSelected = selectedSkuId === row.id;
                        return (
                          <TableRow
                            {...getRowProps({ row })}
                            key={row.id}
                            onClick={() => handleRowSelect(row.id)}
                            style={{
                              cursor: "pointer",
                              fontWeight: isSelected ? 600 : undefined,
                            }}
                          >
                            {row.cells.map((cell) => {
                              if (!entry) {
                                return <TableCell key={cell.id}>{cell.value}</TableCell>;
                              }

                              if (cell.info.header === "our_ref") {
                                return (
                                  <TableCell key={cell.id}>
                                    <Link
                                      as={NextLink}
                                      href={`/catalogue?q=${encodeURIComponent(entry.our_ref)}`}
                                      onClick={(event) => event.stopPropagation()}
                                    >
                                      {entry.our_ref}
                                    </Link>
                                  </TableCell>
                                );
                              }

                              if (cell.info.header === "on_water" && entry.on_order > 0) {
                                return (
                                  <TableCell key={cell.id}>
                                    <Link
                                      href="/transit"
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        router.push("/transit");
                                      }}
                                    >
                                      {formatStockQty(entry.on_order)}
                                    </Link>
                                  </TableCell>
                                );
                              }

                              if (cell.info.header.startsWith("location_")) {
                                const locationId = cell.info.header.replace("location_", "");
                                const locationEntry = entry.locations.find(
                                  (location) => location.location_id === locationId,
                                );
                                const qty = locationEntry?.on_hand ?? 0;
                                const bins = visibleBins(locationEntry?.bins);
                                return (
                                  <TableCell key={cell.id}>
                                    <div>{formatStockQty(qty)}</div>
                                    {bins.length > 0 ? (
                                      <div className="cds--type-label-01 vellano-muted-text">
                                        {bins.map((bin) => `${bin.code}: ${bin.on_hand}`).join(" · ")}
                                      </div>
                                    ) : null}
                                  </TableCell>
                                );
                              }

                              return <TableCell key={cell.id}>{cell.value}</TableCell>;
                            })}
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </DataTable>
        </div>
      )}

      {canViewCost ? (
        <Accordion>
          <AccordionItem
            title="Unit cost history"
            open={auditExpanded}
            onHeadingClick={() => setAuditExpanded((current) => !current)}
          >
            <CostAuditPanel skuOptions={skuOptions} selectedSkuId={selectedSkuId} />
          </AccordionItem>
        </Accordion>
      ) : null}
    </Stack>
  );
}
