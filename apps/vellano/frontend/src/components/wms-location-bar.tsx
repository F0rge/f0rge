"use client";

import { ContentSwitcher, Switch } from "@carbon/react";

import type { WmsFloorLocations } from "@/lib/wms-location";

type WmsLocationBarProps = {
  floor: WmsFloorLocations;
  locationId: string;
  onChange: (locationId: string) => void;
};

export function WmsLocationBar({ floor, locationId, onChange }: WmsLocationBarProps) {
  const selectedIndex = Math.max(
    0,
    floor.findIndex((location) => location.id === locationId),
  );

  return (
    <div className="vellano-wms-location" role="region" aria-label="Where you are standing">
      <p className="vellano-wms-location__label cds--type-label-01">Where am I standing?</p>
      <ContentSwitcher
        selectedIndex={selectedIndex}
        size="lg"
        onChange={(event) => {
          const index = event.index ?? 0;
          const location = floor[index];
          if (location) {
            onChange(location.id);
          }
        }}
      >
        {floor.map((location) => (
          <Switch key={location.id} name={location.id} text={location.name} />
        ))}
      </ContentSwitcher>
    </div>
  );
}
