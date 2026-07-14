'use client';

import { Settings2 } from 'lucide-react';
import SheetPreview from '@/components/SheetPreview';

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

interface ConfigPanelProps {
  config: TagConfig;
  onConfigChange: (config: TagConfig) => void;
}

const inputClass =
  'h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50';
const labelClass = 'text-sm font-medium';
const helperClass = 'mt-1 text-xs text-muted-foreground';

export default function ConfigPanel({ config, onConfigChange }: ConfigPanelProps) {
  const updateConfig = (field: keyof TagConfig, value: string | number | boolean) => {
    const newConfig = { ...config, [field]: value };

    // Auto-calculate max characters if enabled (width/font only).
    if (field === 'auto_max_characters' && value) {
      newConfig.max_characters = Math.floor(newConfig.tag_width / (newConfig.font_size * 0.2));
    } else if ((field === 'tag_width' || field === 'font_size') && config.auto_max_characters) {
      newConfig.max_characters = Math.floor(newConfig.tag_width / (newConfig.font_size * 0.2));
    }

    onConfigChange(newConfig);
  };

  const numberValue = (v: string) => {
    const n = parseFloat(v);
    return Number.isNaN(n) ? 0 : n;
  };

  return (
    <div data-tour="config" className="rounded-xl border border-border bg-card p-5 space-y-6">
      <div className="flex items-center gap-2">
        <Settings2 className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-base font-medium">Tag Configuration</h2>
      </div>

      {/* Section 1: Tag size & text */}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold">Tag size &amp; text</h3>

        <div>
          <span className={labelClass}>Orientation</span>
          <div className="mt-2 flex gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                value="P"
                checked={config.portrait_landscape === 'P'}
                onChange={(e) => updateConfig('portrait_landscape', e.target.value)}
              />
              Portrait
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                value="L"
                checked={config.portrait_landscape === 'L'}
                onChange={(e) => updateConfig('portrait_landscape', e.target.value)}
              />
              Landscape
            </label>
          </div>
        </div>

        <div>
          <label className={labelClass} htmlFor="tag_width">
            Tag Width (mm)
          </label>
          <input
            id="tag_width"
            type="number"
            step="0.5"
            min="0"
            max="200"
            value={config.tag_width}
            onChange={(e) => updateConfig('tag_width', numberValue(e.target.value))}
            className={`mt-1 ${inputClass}`}
          />
        </div>

        <div>
          <label className={labelClass} htmlFor="tag_height">
            Tag Height (mm)
          </label>
          <input
            id="tag_height"
            type="number"
            step="0.5"
            min="0"
            max="200"
            value={config.tag_height}
            onChange={(e) => updateConfig('tag_height', numberValue(e.target.value))}
            className={`mt-1 ${inputClass}`}
          />
        </div>

        <div>
          <label className={labelClass} htmlFor="font_size">
            Font Size
          </label>
          <input
            id="font_size"
            type="number"
            min="6"
            max="100"
            value={config.font_size}
            onChange={(e) => updateConfig('font_size', numberValue(e.target.value))}
            className={`mt-1 ${inputClass}`}
          />
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={config.auto_max_characters}
            onChange={(e) => updateConfig('auto_max_characters', e.target.checked)}
          />
          Auto Max Characters
        </label>

        {!config.auto_max_characters && (
          <div>
            <label className={labelClass} htmlFor="max_characters">
              Max Characters
            </label>
            <input
              id="max_characters"
              type="number"
              min="1"
              max="120"
              value={config.max_characters}
              onChange={(e) => updateConfig('max_characters', numberValue(e.target.value))}
              className={`mt-1 ${inputClass}`}
            />
          </div>
        )}
      </section>

      {/* Section 2: Sticker-sheet alignment */}
      <section data-tour="alignment" className="space-y-4 border-t border-border pt-5">
        <div>
          <h3 className="text-sm font-semibold">Sticker-sheet alignment</h3>
          <p className={helperClass}>
            Defaults match a 65 × 39.5 mm, 3-column A4 sticker sheet. Nudge these until the preview
            lines up with your sheet.
          </p>
        </div>

        <div>
          <label className={labelClass} htmlFor="left_margin">
            Left margin (mm)
          </label>
          <input
            id="left_margin"
            type="number"
            step="0.5"
            min="0"
            value={config.left_margin}
            onChange={(e) => updateConfig('left_margin', numberValue(e.target.value))}
            className={`mt-1 ${inputClass}`}
          />
          <p className={helperClass}>Gap from the page&apos;s left edge to the first tag.</p>
        </div>

        <div>
          <label className={labelClass} htmlFor="top_margin">
            Top margin (mm)
          </label>
          <input
            id="top_margin"
            type="number"
            step="0.5"
            min="0"
            value={config.top_margin}
            onChange={(e) => updateConfig('top_margin', numberValue(e.target.value))}
            className={`mt-1 ${inputClass}`}
          />
          <p className={helperClass}>Gap from the page&apos;s top edge to the first row.</p>
        </div>

        <div>
          <label className={labelClass} htmlFor="inner_padding">
            Inner padding (mm)
          </label>
          <input
            id="inner_padding"
            type="number"
            step="0.5"
            min="0"
            value={config.inner_padding}
            onChange={(e) => updateConfig('inner_padding', numberValue(e.target.value))}
            className={`mt-1 ${inputClass}`}
          />
          <p className={helperClass}>
            Breathing room inside each tag so the P-reference isn&apos;t cropped when peeling.
          </p>
        </div>
      </section>

      {/* Live preview */}
      <section data-tour="preview" className="space-y-3 border-t border-border pt-5">
        <h3 className="text-sm font-semibold">Preview</h3>
        <SheetPreview
          leftMargin={config.left_margin}
          topMargin={config.top_margin}
          tagWidth={config.tag_width}
          tagHeight={config.tag_height}
          innerPadding={config.inner_padding}
          orientation={config.portrait_landscape === 'L' ? 'L' : 'P'}
        />
      </section>
    </div>
  );
}
