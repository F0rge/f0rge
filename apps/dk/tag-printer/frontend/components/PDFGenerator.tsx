'use client';

import axios from 'axios';
import { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button, Card, CardContent } from '@f0rge/ui';
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
    <Card className="p-0">
      <CardContent className="pt-4">
        <Button
          type="button"
          className="w-full"
          size="lg"
          onClick={handleGenerate}
          disabled={isGenerating || selectedProducts.length === 0}
        >
          {isGenerating ? (
            <>
              <Loader2 className="animate-spin" />
              Generating PDF…
            </>
          ) : (
            <>
              <Download />
              Generate &amp; Download PDF
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
