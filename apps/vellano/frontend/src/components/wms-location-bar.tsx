"use client";

import { ContentSwitcher, Switch } from "@carbon/react";

import type { WmsFloorLocations } from "@/lib/wms-location";

type WmsLocationBarProps = {
  floor: WmsFloorLocations;
  locationId: string;
  onChange: (locationId: string) => void;
};

export function WmsLocationBar({ floor, locationId, onChange }: WmsLocationBarProps) {
  const selectedIndex = locationId === floor.bedfordview.id ? 1 : 0;

  return (
    <div className="vellano-wms-location" role="region" aria-label="Where you are standing">
      <p className="vellano-wms-location__label cds--type-label-01">Where am I standing?</p>
      <ContentSwitcher
        selectedIndex={selectedIndex}
        size="lg"
        onChange={(event) => {
          const index = event.index ?? 0;
          onChange(index === 1 ? floor.bedfordview.id : floor.kramerville.id);
        }}
      >
        <Switch name="kramerville" text={floor.kramerville.name} />
        <Switch name="bedfordview" text={floor.bedfordview.name} />
      </ContentSwitcher>
    </div>
  );
}
