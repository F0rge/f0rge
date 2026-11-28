import { ChevronDown } from "lucide-react";
import { useEffect, useState } from "react";
import { fitPhoto, type FitPhoto } from "@/lib/fit-photos";
import type { Measurement } from "@/lib/product-dimensions";
import styles from "./dimensions-fit.module.css";

const axisLabel = { diameter: "Diameter", width: "Width", height: "Height", depth: "Depth", length: "Length" };
const axisSummary = { diameter: "diameter", width: "wide", height: "high", depth: "deep", length: "long" };
const amount = (measurement: Measurement) => `${measurement.value} ${measurement.unit}`;

function AnnotatedPhoto({ photo, title, horizontal, height, circumference, onError }: {
  photo: FitPhoto;
  title: string;
  horizontal?: Measurement;
  height?: Measurement;
  circumference?: string;
  onError: (url: string) => void;
}) {
  // SVG images lack HTMLImageElement.complete. Replay the image lookup after hydration so
  // a failure before React attached the SVG error handler also switches to text measurements.
  useEffect(() => {
    const probe = new Image();
    probe.onerror = () => onError(photo.url);
    probe.src = photo.url;
    return () => { probe.onerror = null; };
  }, [photo.url, onError]);

  // Fit a crop around the furniture; the annotation ticks use the same transform as the photograph.
  const [imageWidth, imageHeight] = photo.size;
  const [left, top, right, bottom] = photo.bounds;
  const cropX = Math.max(0, left - 20);
  const cropY = Math.max(0, top - 15);
  const cropWidth = Math.min(imageWidth, right + 20) - cropX;
  const cropHeight = Math.min(imageHeight, bottom + 13) - cropY;
  const gutter = height ? 68 : 0;
  const scale = Math.min((388 - gutter) / cropWidth, 245 / cropHeight);
  const width = cropWidth * scale;
  const pictureHeight = cropHeight * scale;
  const x = (400 - gutter - width) / 2;
  const rim = circumference && photo.rim ? photo.rim : undefined;
  const y = rim ? 40 : 5;
  const xOnPhoto = (point: number) => x + (point - cropX) * scale;
  const yOnPhoto = (point: number) => y + (point - cropY) * scale;
  const baseline = y + pictureHeight + 20;
  const side = x + width + 10;
  const middle = (yOnPhoto(top) + yOnPhoto(bottom)) / 2;
  const horizontalText = horizontal && `${axisLabel[horizontal.axis]} ${amount(horizontal)}`;
  const legend = [title, horizontalText, height && `Height ${amount(height)}`, rim && `Circumference ${circumference}`].filter(Boolean).join(", ");
  const rimX = rim && xOnPhoto(rim.cx + rim.rx * Math.SQRT1_2);
  const rimY = rim && yOnPhoto(rim.cy - rim.ry * Math.SQRT1_2);
  const rimLeader = rimX !== undefined && rimY !== undefined ? `M${rimX} ${rimY} L${rimX + 16} 18 H258` : undefined;
  // A circular top can be inset from its supporting legs. Its ruler spans the rim.
  const leftTick = xOnPhoto(rim ? rim.cx - rim.rx : left);
  const rightTick = xOnPhoto(rim ? rim.cx + rim.rx : right);
  const horizontalCentre = (leftTick + rightTick) / 2;

  return <figure className={styles.figure}>
    <svg className={styles.picture} viewBox={`0 0 400 ${horizontal ? baseline + 15 : y + pictureHeight + 5}`} role="img" aria-label={legend}>
      <svg x={x} y={y} width={width} height={pictureHeight} viewBox={`${cropX} ${cropY} ${cropWidth} ${cropHeight}`} overflow="hidden">
        <image href={photo.url} width={imageWidth} height={imageHeight} onError={() => onError(photo.url)} />
      </svg>
      {rim && <g>
        <ellipse cx={xOnPhoto(rim.cx)} cy={yOnPhoto(rim.cy)} rx={rim.rx * scale} ry={rim.ry * scale} fill="none" className={styles.rimUnderlay} />
        <ellipse cx={xOnPhoto(rim.cx)} cy={yOnPhoto(rim.cy)} rx={rim.rx * scale} ry={rim.ry * scale} fill="none" stroke="currentColor" strokeWidth="1.4" strokeDasharray="5 2" />
        <path d={rimLeader} fill="none" className={styles.rimUnderlay} />
        <path d={rimLeader} className={styles.line} />
        <circle cx={rimX} cy={rimY} r="2.5" fill="currentColor" />
        <text x="250" y="18" dominantBaseline="central" textAnchor="end" className={styles.label}>Circumference {circumference}</text>
      </g>}
      {horizontalText && <g>
        <path d={`M${leftTick} ${baseline} H${rightTick} M${leftTick} ${baseline - 4.4} v8.8 M${rightTick} ${baseline - 4.4} v8.8`} className={styles.line} />
        <text x={horizontalCentre} y={baseline} textAnchor="middle" dominantBaseline="central" className={styles.horizontalLabel}>{horizontalText}</text>
      </g>}
      {height && <g>
        <path d={`M${side} ${yOnPhoto(top)} V${yOnPhoto(bottom)} M${side - 4} ${yOnPhoto(top)} h8 M${side - 4} ${yOnPhoto(bottom)} h8`} className={styles.line} />
        <text x={side + 10} y={middle - 3} className={styles.axisName}>Height</text>
        <text x={side + 10} y={middle + 15} className={styles.label}>{amount(height)}</text>
      </g>}
    </svg>
  </figure>;
}

function FitMeasurements({ measurements, circumference }: { measurements: Measurement[]; circumference?: string }) {
  const legacy = measurements.some(({ axis }) => axis === "length");
  return <dl className={styles.measurements}>
    {legacy
      ? <div><dt>Size (L × W × H)</dt><dd>{measurements.map(({ value }) => value).join(" × ")} {measurements[0].unit}</dd></div>
      : measurements.map((measurement) => <div key={measurement.axis}><dt>{axisLabel[measurement.axis]}</dt><dd>{amount(measurement)}</dd></div>)}
    {circumference && <div><dt>Circumference</dt><dd>{circumference}</dd></div>}
  </dl>;
}

export function DimensionsFit({ title, sku, gallery, measurements }: {
  title: string;
  sku?: string | null;
  gallery: string[];
  measurements: Measurement[];
}) {
  const [failedPhoto, setFailedPhoto] = useState<string>();
  if (!measurements.length) return null;
  const diameter = measurements.find(({ axis }) => axis === "diameter");
  const width = measurements.find(({ axis }) => axis === "width");
  const height = measurements.find(({ axis }) => axis === "height");
  const horizontal = diameter ?? width;
  const summary = horizontal ?? height ?? measurements[0];
  const circumference = diameter && `≈ ${(Math.PI * diameter.value).toFixed(1)} ${diameter.unit}`;
  const photo = fitPhoto(sku, gallery);
  const annotate = photo && photo.url !== failedPhoto && (horizontal || height) && !measurements.some(({ axis }) => axis === "length");
  const listed = annotate ? measurements.filter((measurement) => measurement !== horizontal && measurement !== height) : measurements;
  const listedCircumference = annotate && photo.rim ? undefined : circumference;

  return <details open data-dimensions-fit className={styles.panel}>
    <summary>
      <span>Dimensions &amp; fit</span>
      <span className={styles.summaryValue}>{amount(summary)} {axisSummary[summary.axis]}</span>
      <ChevronDown aria-hidden="true" size={16} className={styles.chevron} />
    </summary>
    {annotate && <AnnotatedPhoto photo={photo} title={title} horizontal={horizontal} height={height} circumference={circumference} onError={setFailedPhoto} />}
    {(listed.length > 0 || listedCircumference) && <FitMeasurements measurements={listed} circumference={listedCircumference} />}
  </details>;
}
