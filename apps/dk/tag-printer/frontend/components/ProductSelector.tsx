'use client';

import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ProductSelectorProps {
  data: Record<string, unknown>[];
  productCodes: string[];
  selectedProducts: string[];
  onSelectionChange: (selected: string[]) => void;
  priceColumns: string[];
  selectedPriceColumn: string;
  onPriceColumnChange: (column: string) => void;
}

const inputClass =
  'h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50';

export default function ProductSelector({
  data,
  productCodes,
  selectedProducts,
  onSelectionChange,
  priceColumns,
  selectedPriceColumn,
  onPriceColumnChange,
}: ProductSelectorProps) {
  const [query, setQuery] = useState('');

  const filteredCodes = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return productCodes;
    return productCodes.filter((code) => code.toLowerCase().includes(q));
  }, [productCodes, query]);

  const handleProductToggle = (code: string) => {
    if (selectedProducts.includes(code)) {
      onSelectionChange(selectedProducts.filter((p) => p !== code));
    } else {
      onSelectionChange([...selectedProducts, code]);
    }
  };

  // Select All acts on the currently filtered set.
  const allFilteredSelected =
    filteredCodes.length > 0 && filteredCodes.every((code) => selectedProducts.includes(code));

  const handleSelectAll = () => {
    if (allFilteredSelected) {
      onSelectionChange(selectedProducts.filter((code) => !filteredCodes.includes(code)));
    } else {
      onSelectionChange(Array.from(new Set([...selectedProducts, ...filteredCodes])));
    }
  };

  const filteredData = data.filter((row) =>
    selectedProducts.includes(String(row.ProductCode ?? '')),
  );

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-card p-4">
        <h3 className="mb-3 text-sm font-semibold">Price Column</h3>
        <select
          value={selectedPriceColumn}
          onChange={(e) => onPriceColumnChange(e.target.value)}
          className={inputClass}
        >
          {priceColumns.map((col) => (
            <option key={col} value={col}>
              {col}
            </option>
          ))}
        </select>
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Select Products</h3>
          <button
            onClick={handleSelectAll}
            disabled={filteredCodes.length === 0}
            className="h-8 rounded-lg border border-input bg-transparent px-3 text-sm font-medium transition-colors hover:bg-accent disabled:pointer-events-none disabled:opacity-50"
          >
            {allFilteredSelected ? 'Deselect All' : 'Select All'}
          </button>
        </div>

        <div className="relative mb-3">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search product codes…"
            className={`${inputClass} pl-9`}
          />
        </div>

        <div className="max-h-64 space-y-1 overflow-y-auto">
          {filteredCodes.length === 0 ? (
            <p className="px-2 py-4 text-center text-sm text-muted-foreground">No matches</p>
          ) : (
            filteredCodes.map((code) => (
              <label
                key={code}
                className="flex cursor-pointer items-center gap-3 rounded-md p-2 hover:bg-muted/50"
              >
                <input
                  type="checkbox"
                  checked={selectedProducts.includes(code)}
                  onChange={() => handleProductToggle(code)}
                />
                <span className="text-sm">{code}</span>
              </label>
            ))
          )}
        </div>

        <div className="mt-3 text-sm text-muted-foreground">
          {selectedProducts.length} of {productCodes.length} products selected
        </div>
      </div>

      {filteredData.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold">Selected Products Preview</h3>
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {Object.keys(filteredData[0])
                    .slice(0, 5)
                    .map((key) => (
                      <th
                        key={key}
                        className="px-4 py-2 text-left text-xs font-medium uppercase text-muted-foreground"
                      >
                        {key}
                      </th>
                    ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredData.map((row, idx) => (
                  <tr key={idx} className={cn('hover:bg-muted/50')}>
                    {Object.values(row)
                      .slice(0, 5)
                      .map((value, colIdx) => (
                        <td key={colIdx} className="px-4 py-2">
                          {String(value)}
                        </td>
                      ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
