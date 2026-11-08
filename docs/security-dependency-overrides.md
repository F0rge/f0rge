# CI security dependency overrides

The root production audit gate remains `npm audit --omit=dev --audit-level=high`.
The October 2026 dependency refresh fixes four upstream advisories without
changing Medusa 2.21.1 or application behavior. Next stayed at 16.3.8 in that
refresh and moves to 16.4.3 in the later audit repair below.

| Package | Previous version | Fixed official release | Advisory |
| --- | --- | --- | --- |
| `@graphql-tools/utils` | 10.11.0 (also nested 12.0.1) | 12.0.3 | [mergeDeep prototype pollution](https://github.com/advisories/GHSA-7mx3-vvmw-hjmv) |
| `proxy-addr` | 2.0.7 | 2.0.8 | [IPv4-mapped IPv6 trust subnet spoofing](https://github.com/advisories/GHSA-jqcg-44mw-7w3h) |
| `sharp` | 0.35.4 | 0.35.5 | [librsvg memory vulnerability](https://github.com/advisories/GHSA-wq5f-xc86-pv6w) |
| `source-map-js` | 1.2.1 | 1.2.2 | [indexed section offset denial of service](https://github.com/advisories/GHSA-68fv-2mgg-jv7q) |

The three patch upgrades retain their public APIs. Sharp's prebuilt binary
packages and libvips dependencies move together to include fixed librsvg 2.63.2.
All lockfile entries retain their official npm URLs and integrity hashes.

GraphQL utilities have no fixed v10 release. The override selects official v12.0.3,
which includes the v12.0.1 merge fix and the subsequent incremental result merge
hardening. Its GraphQL 14–17 peer range covers Medusa's GraphQL 16. Although the
utils package itself declares Node >=16, its `@whatwg-node/promise-helpers@2.0.0`
dependency requires Node >=22.15.0. Commerce's declared Node engine therefore
moves from Node 20.19 / 22.12 to >=22.15.0. CI and Vellano Docker images already
use Node 22; verification uses Node 22.22.0. Local commerce development must also
use Node >=22.15.0. The [upstream changelog](https://github.com/ardatan/graphql-tools/blob/master/packages/utils/CHANGELOG.md)
identifies changes to schemas without operation roots in v11 and variable-value
arguments to field collection helpers in v12. Medusa's Codegen 4 consumers use
schema/AST helpers and do not call those changed field collection helpers. The
security guard exercises the actual Medusa schema-to-TypeScript generator and
installed GraphQL schema/merge consumers, in addition to adversarial merge tests.
Commerce's native integration tests and admin build cover the runtime boundary.

Run after a complete clean install:

```sh
npm ci --no-audit --no-fund
node scripts/security/check-braces.cjs
node scripts/security/check-ci-dependencies.cjs
npm audit --omit=dev --audit-level=high
```

The new guard verifies every locked and installed copy of the four packages,
checks prototype pollution and proxy trust handling, bounds the source-map attack
probe in a child process, decodes and resizes SVG with the actual Sharp binding,
and generates types through Medusa's real consumer. CI runs it before the
unchanged audit gate. Existing transparent `braces` security backport and its
provenance checks remain in place.

When upstream Medusa's dependency ranges include these fixed releases, remove
redundant overrides individually and rerun these checks plus commerce native
integration tests and frontend/admin builds. Reverting the overrides restores
vulnerable packages; the security gate must then remain failing until an actual
fix is selected. Moderate advisories outside these four fixes remain visible to
the audit and are outside this CI repair's scope.

`@medusajs/admin-bundler` is overridden to `vite` 7.3.7. The hoisted production
copy was 7.3.6, which fails `npm audit --omit=dev --audit-level=high`
([GHSA-587h-7wmj-h5pm](https://github.com/advisories/GHSA-587h-7wmj-h5pm) and
the two related launch-editor advisories). The override is nested so `libs/ui`
stays on vite 6.4.3. Commerce's own devDependency range `^7.3.6` already
accepts 7.3.7. Vite's dependency set is unchanged between 7.3.6 and 7.3.7.

## 24 Oct 2026 prod audit repair

`npm audit --omit=dev --audit-level=high` failed on `next` 16.3.8 (critical),
`zod` &lt;4.6.6 (high, including Medusa 2.21.1's exact 4.2.0 pins), `body-parser`
&lt;1.20.9 (high), and `multer` &lt;2.5.0 (high). Medusa stays on 2.21.1. Direct
`next` dependencies and the root override are 16.4.3, the latest stable 16.x.
Commerce's direct `zod` dependency is 4.6.7. The other fixes are root overrides:

| Override | Version | Why this shape |
| --- | --- | --- |
| `fast-uri` | 3.1.9 | Replaces the previous 3.1.7 pin, which was still inside GHSA-hrr3-gc8f-f4qj and the related fast-uri advisories. |
| `multer` | 2.5.0 | Medusa's `^2.3.0` range already accepts this patch. |
| `qs` | 6.16.1 | Clears GHSA-4mjr-xmp4-gh2g and GHSA-x5fp-wj9c-mxmx. Express 4.22.2 still requests `~6.15.1`; the override is what installs the fixed minor. |
| `body-parser@^1` | 1.20.9 | Patches the 1.x copy Express 4 installs. The `@^1` selector leaves `@modelcontextprotocol/sdk`'s body-parser 2.x alone. |
| `zod@^4.0.0` | 4.6.7 | Lifts Medusa's exact 4.2.0 copies and the hoisted Zod 4.4.3. Zod 3 under `shadcn` (`^3.24.1`) does not match. Medusa re-exports Zod from `@medusajs/deps/zod`. |
| `bullmq` → `uuid` | 11.1.1 | BullMQ 5.13.0 (pinned by Medusa) only calls `uuid.v4()`. Uuid 11 still ships that function for `require()`. The root production dependency hoists `uuid@11.1.1` so `@medusajs/core-flows` can `require("uuid")` in the commerce image. `@nxlv/python` keeps nested uuid 9. |
| `@rushstack/node-core-library` → `ajv` | 8.20.0 | The production copy under MikroORM's `umzug` was ajv 8.13.0. Ajv 6 stays for ESLint. |
| `postcss-selector-parser@^7` | 7.1.7 | Patches the 7.1.x copy (shadcn). The 6.x copies under Tailwind 3 / `postcss-nested` stay on 6.1.5: Tailwind 3 requires `postcss-selector-parser/dist/util/unesc`, which a major bump to 7.x would drop. GHSA-rj75-hqrm-r3gf therefore remains moderate and does not fail `--audit-level=high`. |
