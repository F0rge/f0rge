"use client";

import {
  SkeletonPlaceholder,
  SkeletonText,
  Stack,
  TableContainer,
  Tag,
  Tile,
} from "@carbon/react";
import { Building, UserMultiple } from "@carbon/icons-react";
import { LoadingField, LoadingRegion, LoadingTableRows } from "@/components/page-loading";
import styles from "./organisation.module.css";

export function OrganisationLoading() {
  return (
    <LoadingRegion label="Loading organisation settings…">
      <Stack gap={7}>
        <div className={`${styles.intro} firstout-tone-info firstout-section-accent`}>
          <Building size={32} aria-hidden="true" />
          <div>
            <h2 className="cds--type-heading-03">Your business, connected.</h2>
            <p className="cds--type-body-01">Keep your identity, places and people together.</p>
          </div>
        </div>
        <div className={styles.profileGrid}>
          <Tile>
            <Stack gap={5}>
              <div className={styles.headingRow}>
                <h2 className="cds--type-heading-03">Business details</h2>
                <Tag type="gray">Identity</Tag>
              </div>
              <div className={styles.businessGrid}>
                <LoadingField label="Legal business name" />
                <LoadingField label="Trading name (optional)" />
              </div>
              <LoadingField label="Business address" height="6rem" />
              <LoadingField label="VAT number (optional)" />
              <SkeletonPlaceholder aria-hidden="true" style={{ width: "12rem", height: "3rem" }} />
            </Stack>
          </Tile>
          <Stack gap={6}>
            <Tile>
              <Stack gap={5}>
                <div className={styles.headingRow}>
                  <Building size={32} aria-hidden="true" />
                  <SkeletonPlaceholder aria-hidden="true" style={{ width: "5rem", height: "1.5rem" }} />
                </div>
                <SkeletonText aria-hidden="true" heading width="75%" />
                <div>
                  <span className="cds--label">Organisation slug</span>
                  <SkeletonText aria-hidden="true" width="45%" />
                </div>
                <div>
                  <span className="cds--label">Staff places allocated</span>
                  <SkeletonPlaceholder aria-hidden="true" style={{ width: "100%", height: "0.5rem" }} />
                </div>
                <p className="cds--type-helper-text-01">
                  Only the organisation owner can change these details. Pending invitations reserve a staff place.
                </p>
              </Stack>
            </Tile>
            <Tile>
              <Stack gap={5}>
                <div className={styles.headingRow}>
                  <h2 className="cds--type-heading-03">Branding</h2>
                  <Tag type="gray">Documents</Tag>
                </div>
                <div className={`${styles.branding} firstout-tone-info`} aria-hidden="true">
                  <SkeletonPlaceholder style={{ width: "3rem", height: "3rem" }} />
                  <SkeletonText paragraph lineCount={2} width="60%" />
                </div>
                <SkeletonPlaceholder aria-hidden="true" style={{ width: "11rem", height: "2.5rem" }} />
                <p className="cds--type-helper-text-01">PNG, JPEG or WebP. Uploading replaces the existing logo.</p>
              </Stack>
            </Tile>
          </Stack>
        </div>
        <Stack gap={5}>
          <div>
            <h2 className="cds--type-heading-03">Locations</h2>
            <p className="cds--type-body-01 firstout-muted-text">
              Warehouses and showrooms where your team receives, stores and sells stock.
            </p>
          </div>
          <TableContainer description="Manage locations to add, rename, archive or restore places and configure bins and labels.">
            <div className={styles.tableScroll}>
              <LoadingTableRows columns={["Location", "Type", "Status"]} rows={2} />
            </div>
          </TableContainer>
        </Stack>
        <Tile>
          <div className={styles.entry}>
            <UserMultiple size={32} aria-hidden="true" />
            <div>
              <h2 className="cds--type-heading-03">Existing staff</h2>
              <p className="cds--type-body-01 firstout-muted-text">
                Review roles, default locations and enabled access.
              </p>
            </div>
          </div>
        </Tile>
        <Stack gap={5}>
          <Tile>
            <Stack gap={5}>
              <div className={styles.headingRow}>
                <h2 className="cds--type-heading-03">Invite your team</h2>
                <SkeletonPlaceholder aria-hidden="true" style={{ width: "6rem", height: "1.5rem" }} />
              </div>
              <div aria-hidden="true"><SkeletonText width="75%" /></div>
              <div className={styles.businessGrid}>
                <LoadingField label="Staff email" />
                <LoadingField label="Role in this organisation" />
              </div>
              <SkeletonPlaceholder aria-hidden="true" style={{ width: "10rem", height: "3rem" }} />
            </Stack>
          </Tile>
          <TableContainer title="Staff invitations" description="Review pending invitations and revoke access before an invitation is accepted.">
            <div className={styles.tableScroll}>
              <LoadingTableRows columns={["Email", "Role", "Status", "Action"]} rows={2} />
            </div>
          </TableContainer>
        </Stack>
      </Stack>
    </LoadingRegion>
  );
}
