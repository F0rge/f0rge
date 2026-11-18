"use client";

import {
  Button,
  NumberInput,
  RadioButton,
  RadioButtonGroup,
  SkeletonPlaceholder,
  SkeletonText,
  Stack,
  TextInput,
  Tile,
} from "@carbon/react";
import { Scan, UserFollow } from "@carbon/icons-react";
import { LoadingField, LoadingRegion } from "@/components/page-loading";
import styles from "./page.module.css";

export function TillLoading({
  mobileScan = false,
  paymentOptions,
  tender,
}: {
  mobileScan?: boolean;
  paymentOptions: readonly { value: string; label: string }[];
  tender: string;
}) {
  return (
    <LoadingRegion label="Loading your till">
      <div className={styles.layout}>
        <div className={`firstout-section-accent firstout-tone-info ${styles.productBrowser}`}>
        <Stack gap={5}>
          <Tile>
            <Stack gap={5}>
              <div className={styles.sectionHeading}>
                <div>
                  <p className="cds--type-label-01">SHOWROOM PRODUCTS</p>
                  <h2 className="cds--type-heading-03">Find a product</h2>
                </div>
                <SkeletonPlaceholder aria-hidden="true" style={{ width: "6rem", height: "1.5rem" }} />
              </div>
              <LoadingField label="Showroom" />
              <div className="firstout-till-scan-row">
                <TextInput id="loading-till-scan" labelText="Scan or type a barcode" placeholder="Scan or type our barcode" disabled />
                {mobileScan && <Button kind="secondary" renderIcon={Scan} disabled>Scan</Button>}
              </div>
              <div className="firstout-till-picker-row">
                <TextInput id="loading-till-sku" labelText="Find by product, SKU or barcode" placeholder="Search by SKU, barcode, or name..." disabled />
                <Button kind="tertiary" disabled>Browse Catalogue</Button>
              </div>
              <NumberInput id="loading-till-qty" label="Quantity" min={1} value={1} disabled />
              <Button kind="secondary" disabled>Add to cart</Button>
              <div className={styles.productGrid} aria-hidden="true">
                {Array.from({ length: 4 }, (_, index) => (
                  <Tile key={index}>
                    <div className={styles.productCard}>
                      <SkeletonPlaceholder style={{ width: "100%", height: "8rem" }} />
                      <SkeletonText width="65%" />
                      <SkeletonText width="25%" />
                      <SkeletonText width="35%" />
                      <SkeletonText width="50%" />
                    </div>
                  </Tile>
                ))}
              </div>
              <SkeletonPlaceholder aria-hidden="true" style={{ width: "100%", height: "3rem" }} />
            </Stack>
          </Tile>
        </Stack>
      </div>
      <div className={`firstout-section-accent firstout-tone-info ${styles.sale}`}>
        <Tile>
          <Stack gap={5}>
            <div className={styles.sectionHeading}>
              <h2 className="cds--type-heading-03">Current sale</h2>
              <SkeletonPlaceholder aria-hidden="true" style={{ width: "6rem", height: "1.5rem" }} />
            </div>
            <div className="firstout-till-picker-row">
              <LoadingField label="Customer (optional)" />
              <Button kind="ghost" hasIconOnly renderIcon={UserFollow} iconDescription="Add customer" disabled />
            </div>
            <div className={styles.empty} aria-hidden="true">
              <SkeletonText width="50%" />
              <SkeletonText width="70%" />
            </div>
            <h3 className="cds--type-heading-compact-01">Sale summary</h3>
            <dl className="firstout-sale-summary">
              {["Subtotal", "Line discounts", "VAT", "Total incl. VAT"].map((label) => (
                <div key={label} className={`firstout-sale-summary__row${label === "Total incl. VAT" ? " firstout-sale-summary__row--total" : ""}`}>
                  <dt>{label}</dt>
                  <dd aria-hidden="true"><SkeletonText width="5rem" /></dd>
                </div>
              ))}
            </dl>
            <RadioButtonGroup legendText="Payment method" name="loading-till-tender" orientation="horizontal" valueSelected={tender} disabled>
              {paymentOptions.map(({ value, label }) => (
                <RadioButton key={value} id={`loading-till-tender-${value}`} value={value} labelText={label} />
              ))}
            </RadioButtonGroup>
            <TextInput id="loading-till-tendered" labelText="Amount Tendered" disabled />
            <Button disabled>Complete sale</Button>
          </Stack>
        </Tile>
        </div>
      </div>
    </LoadingRegion>
  );
}
