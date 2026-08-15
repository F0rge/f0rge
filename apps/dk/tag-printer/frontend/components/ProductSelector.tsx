'use client';

import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { Button, Card, CardContent, CardHeader, CardTitle, cn } from '@f0rge/ui';
import { Checkbox, Select, TextInput } from '@f0rge/ui/forms';

interface ProductSelectorProps {
  data: Record<string, unknown>[];
  productCodes: string[];
  selectedProducts: string[];
  onSelectionChange: (selected: string[]) => void;
  priceColumns: string[];
  selectedPriceColumn: string;
  onPriceColumnChange: (column: string) => void;
}

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
      <Card className="p-0">
        <CardHeader>
          <CardTitle className="text-sm">Price Column</CardTitle>
        </CardHeader>
        <CardContent>
          <Select
            data={priceColumns.map((col) => ({ value: col, label: col }))}
            value={selectedPriceColumn}
            onChange={(value) => onPriceColumnChange(value ?? '')}
          />
        </CardContent>
      </Card>

      <Card className="p-0">
        <CardHeader>
          <div className="flex w-full items-center justify-between gap-2">
            <CardTitle className="text-sm">Select Products</CardTitle>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleSelectAll}
              disabled={filteredCodes.length === 0}
            >
              {allFilteredSelected ? 'Deselect All' : 'Select All'}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <TextInput
            value={query}
            onChange={(event) => setQuery(event.currentTarget.value)}
            placeholder="Search product codes…"
            leftSection={<Search className="h-4 w-4 text-muted-foreground" />}
          />

          <div className="max-h-64 space-y-1 overflow-y-auto">
            {filteredCodes.length === 0 ? (
              <p className="px-2 py-4 text-center text-sm text-muted-foreground">No matches</p>
            ) : (
              filteredCodes.map((code) => (
                <Checkbox
                  key={code}
                  label={code}
                  checked={selectedProducts.includes(code)}
                  onChange={() => handleProductToggle(code)}
                  className="rounded-md p-2 hover:bg-muted/50"
                />
              ))
            )}
          </div>

          <p className="text-sm text-muted-foreground">
            {selectedProducts.length} of {productCodes.length} products selected
          </p>
        </CardContent>
      </Card>

      {filteredData.length > 0 && (
        <Card className="p-0">
          <CardHeader>
            <CardTitle className="text-sm">Selected Products Preview</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>
      )}
    </div>
  );
}
