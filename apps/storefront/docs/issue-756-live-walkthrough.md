# Issue #756 live walkthrough

Verified against the production build on 2026-09-28 with Playwright Chromium 153.0.8010.12. The local storefront used a disposable read-only Medusa stub that returned a ZAR region and an empty product list; no commerce credentials or real customer data were used.

The desktop run used a 1440 × 900 viewport. The Sola study remained below the fold until scroll, accepted Enter on the material control, and the page continued scrolling over the study. Pause switched to the static illustration. The mobile run used a 390 × 844 viewport, found no horizontal overflow, kept navigation visible, scrolled through the study, and reached `/shop` through its collection link. These are browser viewport checks, not tests on physical devices.

With reduced motion emulated, the study stayed static, exposed the reduced-motion status, and kept its range and palette controls keyboard-operable. A forced WebGL context failure displayed the illustration and preserved the heading, collection link and bag navigation. A constrained-device run set `navigator.deviceMemory` to 1; it kept the illustrated fallback and made no request for the Three.js chunk.

The provider-neutral `storefront:study` hook emitted one entry, progress milestones 25/50/75/100 and one finish event while the test scrolled away and returned to the end. The event payload contained only the event type, study ID and optional progress milestone.

The Next route bundle report measured the homepage's first-load JavaScript at 462,640 bytes before this change and 471,909 bytes after it (+9,269 bytes uncompressed). The initial homepage chunk list excludes the procedural scene. Its separate Three.js chunk is 551,699 bytes (136,254 bytes gzip). The browser network test observed no Three.js response while the study was more than 200 pixels below the fold; it loaded after scrolling near the section. The constrained-device test observed no request at all.

Validation:

- `npx nx run storefront-web:typecheck` — passed.
- `npx nx run storefront-web:lint` — passed with four existing `<img>` optimization warnings in bag, product-card and product-detail files.
- `npx nx run storefront-web:build` — passed.
- `npx nx run storefront-web:e2e-ci--e2e/study.spec.ts` — all 7 study checks passed against the live local production server.
- `npx nx run storefront-web:e2e` — 10 passed and 14 commerce/data-dependent checks skipped with database, publishable-key and product-fixture environment variables unset.

The atomized `storefront-web:e2e-ci` target requires Nx Cloud in this environment; the complete non-atomized Nx `e2e` target ran instead.
