'use client';

import { useState } from 'react';
import axios from 'axios';
import { FileText, Moon, Sun } from 'lucide-react';
import { toast } from 'sonner';
import { getApiBase } from '@/lib/api';
import CSVUploader from '@/components/CSVUploader';
import ConfigPanel from '@/components/ConfigPanel';
import ProductSelector from '@/components/ProductSelector';
import PDFGenerator from '@/components/PDFGenerator';
import Tour from '@/components/Tour';

interface TagConfig {
  portrait_landscape: string;
  tag_height: number;
  tag_width: number;
  font_size: number;
  max_characters: number;
  auto_max_characters: boolean;
  left_margin: number;
  top_margin: number;
  inner_padding: number;
}

function ThemeToggle() {
  const [dark, setDark] = useState(() => {
    if (typeof window === 'undefined') return false;
    const isDark = localStorage.getItem('theme') === 'dark';
    document.documentElement.classList.toggle('dark', isDark);
    return isDark;
  });

  const toggle = () => {
    const next = !dark;
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem('theme', next ? 'dark' : 'light');
    setDark(next);
  };

  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-input bg-transparent transition-colors hover:bg-accent"
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

type CsvRow = Record<string, unknown>;

export default function Home() {
  const [isUploading, setIsUploading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [csvData, setCsvData] = useState<CsvRow[]>([]);
  const [priceColumns, setPriceColumns] = useState<string[]>([]);
  const [productCodes, setProductCodes] = useState<string[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [selectedPriceColumn, setSelectedPriceColumn] = useState<string>('');

  const [config, setConfig] = useState<TagConfig>({
    portrait_landscape: 'P',
    tag_height: 39.5,
    tag_width: 65,
    font_size: 8,
    max_characters: 40,
    auto_max_characters: false,
    left_margin: 7.5,
    top_margin: 10,
    inner_padding: 2,
  });

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const apiUrl = getApiBase();
      const response = await axios.post(`${apiUrl}/api/upload-csv`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setCsvData(response.data.data);
      setSessionId(response.data.session_id);
      setPriceColumns(response.data.price_columns);
      setProductCodes(response.data.product_codes);
      setSelectedPriceColumn(response.data.price_columns[0] || '');
      setSelectedProducts([]);
    } catch (error) {
      console.error('Error uploading CSV:', error);
      toast.error('Error uploading CSV file. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <main className="mx-auto w-full max-w-7xl p-4 lg:px-8">
      <header className="relative mb-8 pt-4 text-center">
        <div className="absolute right-0 top-4 flex items-center gap-2">
          <Tour />
          <ThemeToggle />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">DasKasas Tag Tool</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Generate custom price tags from DEAR Inventory CSV exports
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1 lg:sticky lg:top-6 self-start">
          <ConfigPanel config={config} onConfigChange={setConfig} />
        </div>

        <div className="space-y-6 lg:col-span-2">
          <CSVUploader onFileUpload={handleFileUpload} isLoading={isUploading} />

          {csvData.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border p-10 text-center">
              <FileText className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
              <p className="text-sm font-medium">No file yet</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Upload a DEAR Inventory CSV export to pick products and generate tags.
              </p>
            </div>
          ) : (
            <>
              <ProductSelector
                data={csvData}
                productCodes={productCodes}
                selectedProducts={selectedProducts}
                onSelectionChange={setSelectedProducts}
                priceColumns={priceColumns}
                selectedPriceColumn={selectedPriceColumn}
                onPriceColumnChange={setSelectedPriceColumn}
              />

              {selectedProducts.length > 0 && (
                <PDFGenerator
                  sessionId={sessionId}
                  csvData={csvData}
                  selectedProducts={selectedProducts}
                  priceColumn={selectedPriceColumn}
                  config={config}
                />
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
