'use client';

import axios from 'axios';
import { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { getApiBase } from '@/lib/api';

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

interface PDFGeneratorProps {
  sessionId: string | null;
  csvData: Record<string, unknown>[];
  selectedProducts: string[];
  priceColumn: string;
  config: TagConfig;
}

export default function PDFGenerator({
  sessionId,
  csvData,
  selectedProducts,
  priceColumn,
  config,
}: PDFGeneratorProps) {
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerate = async () => {
    if (selectedProducts.length === 0) {
      toast.error('Please select at least one product');
      return;
    }

    setIsGenerating(true);

    try {
      const apiUrl = getApiBase();
      const response = await axios.post(
        `${apiUrl}/api/generate-pdf`,
        {
          session_id: sessionId,
          csv_data: csvData,
          selected_products: selectedProducts,
          price_column: priceColumn,
          config: config,
        },
        {
          responseType: 'blob',
        }
      );

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'PriceTags.pdf');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('PDF downloaded');
    } catch (err: unknown) {
      console.error('Error generating PDF:', err);
      const detail =
        axios.isAxiosError(err) && err.response?.data && typeof err.response.data === 'object'
          ? (err.response.data as { detail?: string }).detail
          : undefined;
      toast.error(detail || 'Failed to generate PDF. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <button
        onClick={handleGenerate}
        disabled={isGenerating || selectedProducts.length === 0}
        className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50"
      >
        {isGenerating ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Generating PDF…
          </>
        ) : (
          <>
            <Download className="h-4 w-4" />
            Generate &amp; Download PDF
          </>
        )}
      </button>
    </div>
  );
}
