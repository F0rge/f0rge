# F0rge `braces` security derivative

This package is a transparent, locally maintained derivative of the MIT-licensed
[`braces@3.0.3`](https://github.com/micromatch/braces/tree/3.0.3) source. It is
not an official upstream release and does not claim to be one. Its package
version, `3.0.4-f0rge.1`, identifies F0rge's local backport.

The derivative addresses [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
by imposing a maximum nesting depth of 100 while parsing and before recursive
AST walkers run. Callers may set a smaller `maxDepth`; larger, non-finite, and
invalid values cannot raise the hard maximum. Parser-created and directly
supplied ASTs are checked, and cyclic ASTs are rejected before recursive
processing. Excessive nesting and cycles throw `SyntaxError` values with
`ERR_BRACES_MAX_DEPTH` or `ERR_BRACES_CYCLIC_AST` codes.

The parser enforces the limit for nested braces and parentheses. `compile`,
`expand`, and `stringify` validate AST child paths before recursion; `expand`
also receives cycle and depth checks for AST `parent` links. The source changes
are limited to those guards and their shared helper.

The recursive walkers retain the original 3.0.3 parent-handling behavior,
including `stringify` behavior with `escapeInvalid`. This intentionally avoids
the separate output change reported during review of the still-unreleased
upstream fix proposal.

Run the focused adversarial and compatibility checks with:

```sh
node --test test/security.test.js
```

The upstream copyright and MIT license are retained in [LICENSE](LICENSE).
The upstream npm tarball integrity, tag commit, and SHA-256 hashes for each
source input are recorded in [UPSTREAM.json](UPSTREAM.json).

## Maintenance and rollback

Recheck the upstream advisory and release status before each dependency refresh.
Once upstream publishes a compatible fixed release, compare it against the
derivative, remove the root local-tarball dependency and override together, and
verify that the lockfile resolves to the official release and the unchanged
audit gate passes. To roll back this derivative before then, revert the local
tarball wiring as one change; that restores the vulnerable upstream dependency,
so the high-severity audit gate must remain failing until a reviewed fix is
selected.
