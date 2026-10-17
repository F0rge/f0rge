"use client";

import { Select, SelectItem, Stack } from "@carbon/react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { RecordsTable, type RecordsColumn } from "@/components/records/records-table";
import {
  listLocations,
  listStockByBin,
  type ListParams,
  type Location,
  type StockByBinRow,
} from "@/lib/api";

const COLUMNS: RecordsColumn<StockByBinRow>[] = [
  { key: "location_name", header: "Location", render: (row) => row.location_name },
  { key: "bin_code", header: "Bin", render: (row) => row.bin_code },
  {
    key: "our_ref",
    header: "SKU",
    render: (row) => <Link href={`/catalogue/${row.sku_id}`}>{row.our_ref}</Link>,
  },
  { key: "sku_name", header: "Product", render: (row) => row.sku_name },
  { key: "on_hand", header: "On hand", render: (row) => row.on_hand },
];

export default function StockByBinPage() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState("");

  useEffect(() => {
    void listLocations()
      .then(setLocations)
      .catch(() => setLocations([]));
  }, []);

  const load = useCallback(
    (params: ListParams) => listStockByBin(params, { location_id: locationId || undefined }),
    [locationId],
  );

  return (
    <Stack gap={6}>
      <h1 className="cds--type-productive-heading-04">Stock by bin</h1>
      <Select
        id="stock-by-bin-location"
        labelText="Location"
        value={locationId}
        onChange={(event) => setLocationId(event.target.value)}
      >
        <SelectItem value="" text="All locations" />
        {locations.map((location) => (
          <SelectItem key={location.id} value={location.id} text={location.name} />
        ))}
      </Select>
      <RecordsTable
        key={locationId}
        title="On hand by bin"
        columns={COLUMNS}
        load={load}
        rowId={(row) => `${row.bin_id}-${row.sku_id}`}
        searchPlaceholder="Search SKU or product"
      />
    </Stack>
  );
}
