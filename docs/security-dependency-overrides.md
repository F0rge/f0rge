# CI security dependency overrides

The root production audit gate remains `npm audit --omit=dev --audit-level=high`.
The October 2026 dependency refresh fixes four upstream advisories without
changing Medusa 2.21.1, Next 16.3.8, or application behavior.

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
moves from Node 20.19 / 22.12 to >=22.15.0. CI and storefront Docker images already
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
