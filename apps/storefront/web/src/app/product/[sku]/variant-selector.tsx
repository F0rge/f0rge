"use client";

import { Button, cn } from "@f0rge/ui";
import { Check, X } from "lucide-react";
import Image from "next/image";
import { useId, useRef, useState, type KeyboardEvent } from "react";
import type { MedusaVariant, StoreProduct } from "@/lib/medusa";
import { materialSample, type MaterialSample } from "@/lib/material-samples";
import { formatCustomerPrice } from "@/lib/order-money";
import { pickVariant, productVariantOptions, variantChoices } from "@/lib/product-variants";
import styles from "./variant-selector.module.css";

type SelectVariant = (optionId: string, index: number, variant: MedusaVariant) => void;
type Choice = { value: string; label: string; index: number; variant: MedusaVariant; sample?: MaterialSample; hex?: string | null };
type PhotoChoice = Choice & { sample: MaterialSample };

const colourAxis = /\bcolou?r\b/i;
const finishAxis = /\bfinish\b/i;

function sharedText(values: (string | undefined)[]): string | undefined {
  return values.every((value) => value === values[0]) ? values[0] : undefined;
}

function selectAtBoundary(event: KeyboardEvent<HTMLInputElement>) {
  if (event.key !== "Home" && event.key !== "End") return;
  const input = event.currentTarget;
  const radios = input.ownerDocument.getElementsByName(input.name);
  const target = event.key === "Home" ? radios[0] : radios[radios.length - 1];
  if (target instanceof HTMLInputElement) {
    event.preventDefault();
    target.focus();
    target.click();
  }
}

function SampleImage({ src, className, width, height, detail = false }: {
  src: string; className: string; width: number; height: number; detail?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  if (failed) return detail ? <span className={styles.unavailable}>Photo unavailable</span> : null;
  return <Image unoptimized loading="eager" src={src} alt="" width={width} height={height} className={className}
    style={{ maxWidth: width, maxHeight: height }}
    ref={(img) => { if (img?.complete && img.naturalWidth === 0) setFailed(true); }}
    onError={() => setFailed(true)} />;
}

function OptionGroup({ id, title, choices, selected, onSelect }: {
  id: string; title: string; choices: Choice[]; selected?: string; onSelect: SelectVariant;
}) {
  const groupId = useId();
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const legend = sharedText(choices.map(({ sample }) => sample?.groupTitle)) ?? title;
  const note = sharedText(choices.map(({ sample }) => sample?.optionNote));
  const photos = choices.filter((item): item is PhotoChoice => !!item.sample);
  const visual = photos.length > 0 || choices.some((item) => item.hex);
  const fabric = photos.length > 0 && photos.every(({ sample }) => sample.kind === "fabric");
  const colourSamples = photos.length > 0 && photos.every(({ sample }) => sample.kind === "colour");
  const round = colourAxis.test(legend) || finishAxis.test(legend) || (photos.length === choices.length && colourSamples);
  const comparison = finishAxis.test(legend) ? "finishes" : colourAxis.test(legend) || colourSamples ? "colours" : "materials";
  const single = { finishes: "finish", colours: "colour", materials: "material" }[comparison];
  const action = fabric ? "See fabric close-up" : photos.length > 1 ? `Compare ${comparison}` : `View ${single}`;
  const heading = fabric ? "Fabric close-ups" : colourSamples && !colourAxis.test(legend) ? "Colour samples" : round ? legend : "Material samples";
  const source = sharedText(photos.map(({ sample }) => sample.sourceLabel));

  function label(item: Choice) {
    if (!item.sample) return item.label;
    // If the note does not apply to every option, show it only on the finishes it describes.
    return item.sample.optionNote && !note ? `${item.sample.label} · ${item.sample.optionNote}` : item.sample.label;
  }
  function select(item: Choice) { onSelect(id, item.index, item.variant); }
  function close() {
    setOpen(false);
    trigger.current?.focus({ preventScroll: true });
  }
  function radio(item: Choice, name: string) {
    return <input className={styles.radio} type="radio" name={name} value={item.value} checked={item.value === selected}
      aria-label={label(item)} onChange={() => select(item)} onKeyDown={selectAtBoundary} />;
  }

  return <fieldset className="min-w-0" data-variant-option={title} onKeyDown={(event) => {
    if (open && event.key === "Escape") { event.preventDefault(); close(); }
  }}>
    <legend className="text-sm font-medium">{legend}</legend>
    {visual ? <div className={cn(styles.choices, round && styles.rounds)}>
      {choices.map((item) => <label key={item.value} className={styles.choice}>
        {radio(item, groupId)}
        {item.sample ? <SampleImage key={item.sample.swatch} src={item.sample.swatch} className={styles.thumb} width={item.sample.width} height={item.sample.height} />
          : item.hex && <span aria-hidden="true" className={styles.thumb} style={{ backgroundColor: item.hex }} />}
        <span className={styles.name}>{label(item)}</span>
        <Check aria-hidden="true" className={styles.check} />
      </label>)}
    </div> : <div className="mt-2 flex flex-wrap gap-2">
      {choices.map((item) => <Button key={item.value} type="button" variant={selected === item.value ? "default" : "outline"}
        aria-pressed={selected === item.value} className="h-auto min-h-11 max-w-full whitespace-normal text-start" onClick={() => select(item)}>
        {label(item)}
      </Button>)}
    </div>}

    {photos.length > 0 && <div>
      <div className={styles.links}>
        <Button ref={trigger} type="button" variant="link" className={styles.disclosure}
          aria-expanded={open} aria-controls={`${groupId}-panel`} onClick={() => setOpen(!open)}>{action}</Button>
        {note && <span className={styles.note}>{note}</span>}
      </div>
      <div id={`${groupId}-panel`} hidden={!open} role="region" aria-labelledby={`${groupId}-heading`} className={styles.panel}>
        {open && <>
          <div className={styles.panelHead}>
            <h2 id={`${groupId}-heading`}>{heading}</h2>
            <Button type="button" variant="ghost" size="icon-sm" aria-label={`Close ${heading.toLowerCase()}`} onClick={close}><X aria-hidden="true" /></Button>
          </div>
          <div role="radiogroup" aria-labelledby={`${groupId}-heading`} className={cn(styles.samples, comparison === "finishes" && styles.roundSamples)}>
            {photos.map((item) => <label key={item.value} className={styles.sample}>
              {radio(item, `${groupId}-compare`)}
              <span className={styles.picture} style={{ maxWidth: item.sample.width }}>
                <SampleImage key={item.sample.detail} src={item.sample.detail} detail className={styles.detail}
                  width={item.sample.width} height={item.sample.height} />
                <Check aria-hidden="true" className={styles.check} />
              </span>
              <span className={styles.name}>{label(item)}</span>
              {round && item.variant.calculated_price && <span className={styles.note}>
                {formatCustomerPrice(item.variant.calculated_price.calculated_amount, item.variant.calculated_price.currency_code)}
              </span>}
              {!source && <span className={styles.note}>{item.sample.sourceLabel}</span>}
            </label>)}
          </div>
          {source && <p className={cn(styles.note, styles.caption)}>{source}</p>}
        </>}
      </div>
    </div>}
  </fieldset>;
}

export function VariantSelector({ product, active, onSelect }: {
  product: StoreProduct; active?: MedusaVariant; onSelect: SelectVariant;
}) {
  const options = productVariantOptions(product, "source");
  if (!options.length) return null;
  const selected = variantChoices(active, "source");
  // swatch_hex describes the SKU. Attribute it to an axis only when its meaning is unambiguous.
  const colourOptions = options.filter(({ title }) => colourAxis.test(title) || finishAxis.test(title));
  return <div className="space-y-4 border-t pt-6">{options.map(({ id, title, availableValues }) => {
    const choices = availableValues.flatMap((value, index): Choice[] => {
      const variant = selected[id] === value ? active : pickVariant(product.variants, active, id, value);
      if (!variant) return [];
      const sample = materialSample(variant.sku, title, value);
      const hex = colourOptions.length === 1 && colourOptions[0].id === id ? variant.metadata?.swatch_hex : null;
      return [{ value, label: variantChoices(variant)[id] ?? value, index, variant, sample, hex }];
    });
    return <OptionGroup key={id} id={id} title={title} choices={choices} selected={selected[id]} onSelect={onSelect} />;
  })}</div>;
}
