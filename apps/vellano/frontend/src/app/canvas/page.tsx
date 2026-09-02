"use client";

import { InlineNotification, Stack } from "@carbon/react";

import { CanvasSurface } from "@/components/nia/canvas-surface";
import { useAuth } from "@/lib/auth";
import { useCanvasSpec } from "@/lib/nia-canvas-store";
import { canUseNia } from "@/lib/permissions";

export default function CanvasPage() {
  const { user } = useAuth();
  const spec = useCanvasSpec();

  if (!user || !canUseNia(user)) {
    return (
      <section className="vellano-forbidden">
        <InlineNotification
          kind="error"
          title="Not authorized"
          subtitle="You do not have permission to use Nia Canvas."
          hideCloseButton
        />
      </section>
    );
  }

  return (
    <Stack gap={6} className="vellano-page">
      <div>
        <h1 className="cds--type-productive-heading-04">Canvas</h1>
        {spec ? (
          <p className="vellano-muted-text cds--type-body-01">{spec.title}</p>
        ) : (
          <p className="vellano-muted-text cds--type-body-01">
            Ask Nia to chart something — try dining vs sofas this month.
          </p>
        )}
      </div>
      {spec ? <CanvasSurface spec={spec} /> : null}
    </Stack>
  );
}
