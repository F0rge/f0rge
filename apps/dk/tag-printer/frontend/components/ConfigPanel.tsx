'use client';

import { Settings2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@f0rge/ui';
import {
  Checkbox,
  NumberInput,
  Radio,
  RadioGroup,
  useForm,
} from '@f0rge/ui/forms';
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

export default function ConfigPanel({ config, onConfigChange }: ConfigPanelProps) {
  const form = useForm({ initialValues: config });

  const updateConfig = (field: keyof TagConfig, value: string | number | boolean) => {
    const newConfig = { ...form.values, [field]: value };

    if (field === 'auto_max_characters' && value) {
      newConfig.max_characters = Math.floor(newConfig.tag_width / (newConfig.font_size * 0.2));
    } else if ((field === 'tag_width' || field === 'font_size') && newConfig.auto_max_characters) {
      newConfig.max_characters = Math.floor(newConfig.tag_width / (newConfig.font_size * 0.2));
    }

    form.setValues(newConfig);
    onConfigChange(newConfig);
  };

  return (
    <Card data-tour="config" className="p-0">
      <CardHeader className="border-b border-border pb-4">
        <div className="flex items-center gap-2">
          <Settings2 className="h-4 w-4 text-muted-foreground" />
          <CardTitle>Tag Configuration</CardTitle>
        </div>
      </CardHeader>

      <CardContent className="space-y-6 pt-4">
        <section className="space-y-4">
          <h3 className="text-sm font-semibold">Tag size &amp; text</h3>

          <RadioGroup
            label="Orientation"
            value={form.values.portrait_landscape}
            onChange={(value) => updateConfig('portrait_landscape', value)}
          >
            <div className="mt-2 flex gap-4">
              <Radio value="P" label="Portrait" />
              <Radio value="L" label="Landscape" />
            </div>
          </RadioGroup>

          <NumberInput
            label="Tag Width (mm)"
            value={form.values.tag_width}
            onChange={(value) => updateConfig('tag_width', value ?? 0)}
            min={0}
            max={200}
            step={0.5}
            decimalScale={1}
          />

          <NumberInput
            label="Tag Height (mm)"
            value={form.values.tag_height}
            onChange={(value) => updateConfig('tag_height', value ?? 0)}
            min={0}
            max={200}
            step={0.5}
            decimalScale={1}
          />

          <NumberInput
            label="Font Size"
            value={form.values.font_size}
            onChange={(value) => updateConfig('font_size', value ?? 0)}
            min={6}
            max={100}
          />

          <Checkbox
            label="Auto Max Characters"
            checked={form.values.auto_max_characters}
            onChange={(event) => updateConfig('auto_max_characters', event.currentTarget.checked)}
          />

          {!form.values.auto_max_characters && (
            <NumberInput
              label="Max Characters"
              value={form.values.max_characters}
              onChange={(value) => updateConfig('max_characters', value ?? 0)}
              min={1}
              max={120}
            />
          )}
        </section>

        <section data-tour="alignment" className="space-y-4 border-t border-border pt-5">
          <div>
            <h3 className="text-sm font-semibold">Sticker-sheet alignment</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Defaults match a 65 × 39.5 mm, 3-column A4 sticker sheet. Nudge these until the preview
              lines up with your sheet.
            </p>
          </div>

          <NumberInput
            label="Left margin (mm)"
            description="Gap from the page's left edge to the first tag."
            value={form.values.left_margin}
            onChange={(value) => updateConfig('left_margin', value ?? 0)}
            min={0}
            step={0.5}
            decimalScale={1}
          />

          <NumberInput
            label="Top margin (mm)"
            description="Gap from the page's top edge to the first row."
            value={form.values.top_margin}
            onChange={(value) => updateConfig('top_margin', value ?? 0)}
            min={0}
            step={0.5}
            decimalScale={1}
          />

          <NumberInput
            label="Inner padding (mm)"
            description="Breathing room inside each tag so the P-reference isn't cropped when peeling."
            value={form.values.inner_padding}
            onChange={(value) => updateConfig('inner_padding', value ?? 0)}
            min={0}
            step={0.5}
            decimalScale={1}
          />
        </section>

        <section data-tour="preview" className="space-y-3 border-t border-border pt-5">
          <h3 className="text-sm font-semibold">Preview</h3>
          <SheetPreview
            leftMargin={form.values.left_margin}
            topMargin={form.values.top_margin}
            tagWidth={form.values.tag_width}
            tagHeight={form.values.tag_height}
            innerPadding={form.values.inner_padding}
            orientation={form.values.portrait_landscape === 'L' ? 'L' : 'P'}
          />
        </section>
      </CardContent>
    </Card>
  );
}
