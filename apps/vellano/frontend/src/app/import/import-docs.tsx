"use client";

import { Column, Grid, Tile } from "@carbon/react";

export function ImportDocs() {
  return (
    <Tile>
      <h2 className="cds--type-productive-heading-02">Required columns</h2>
      <Grid condensed fullWidth>
        <Column lg={8} md={4} sm={4}>
          <h3 className="cds--type-productive-heading-01">Inventory List</h3>
          <ul className="cds--type-body-01">
            <li>
              <strong>SKU</strong> — unique identifier (required)
            </li>
            <li>
              <strong>Name</strong> — product name (required)
            </li>
            <li>
              <strong>Category</strong> — required (Cin7-compatible inventory list)
            </li>
            <li>
              <strong>Retail Price</strong> — ZAR including VAT (required)
            </li>
            <li>
              <strong>Barcode</strong> — optional
            </li>
            <li>
              <strong>Cost Price</strong> — optional
            </li>
          </ul>
        </Column>
        <Column lg={8} md={4} sm={4}>
          <h3 className="cds--type-productive-heading-01">Stock on Hand</h3>
          <ul className="cds--type-body-01">
            <li>
              <strong>SKU</strong> — must match catalogue (required)
            </li>
            <li>
              <strong>Location</strong> — location name (required)
            </li>
            <li>
              <strong>Qty</strong> — sets on-hand, does not add (required)
            </li>
            <li>
              <strong>Unit Cost</strong> — optional
            </li>
          </ul>
        </Column>
      </Grid>
    </Tile>
  );
}
