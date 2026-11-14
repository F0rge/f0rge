# Rust projects in Nx

This is shared build/test groundwork for the accepted Rust stack. It adds no
application, Cargo workspace, database, runtime or deployment. Buycycle remains
on its existing private Pi runtime. The holiday-explorer pilot in P-010 still
needs evidence before broader platform adoption; temporary test crates do not
satisfy that prerequisite.

## Run the checks

The repository pins Rust 1.95.0 with rustfmt and clippy in
[`rust-toolchain.toml`](../../rust-toolchain.toml). This is the initial tested
pin, not a claim to use the newest Rust release. Rustup honors the repository
override; installing this toolchain does not change a user's global default.

```sh
rustup toolchain install 1.95.0 --profile minimal --component rustfmt --component clippy
npx nx run f0rge-rust-checks:test
node .github/rust/guard.mjs
```

The uncached tooling target tests registration and runs real Cargo/Nx commands
against disposable, dependency-free fixtures. Failures are intentional negative
test cases, not production changes. Fixtures never scrape Buycycle or use its
data. The source guard lives in [guard.mjs](guard.mjs), and all Rust target
commands use [run-target.mjs](run-target.mjs).

CI always runs this fixture suite and validates all registered Rust projects
before selecting affected Rust tasks. The Rust job is a required input to the
existing `ci` aggregate: failure, cancellation or unexpected skip prevents that
gate from succeeding. Manual CI dispatch checks all Rust projects. Normal PRs
and main pushes use `nx affected`; there is no custom project-list detect job.

## Register a future crate

First resolve the exact paths through the agent manifest. A newly classified
Cargo manifest does not classify every Rust source file or approve a new app.
App crates still follow the accepted Actix/Diesel/PostgreSQL architecture;
shared crates contain small plumbing, with business rules/models kept app-local.

1. Put the package under `apps/` or `libs/`, with a sibling `project.json`, a
   unique Nx name, `platform:rust` and its existing `scope:` tag. Both tags and
   required target wiring are checked. A stray Rust tag without Cargo is also
   rejected. Existing Node/Python project checks still apply.
2. Use the fixed targets shown below. Keep their commands, inputs, outputs and
   cache setting exact; do not add command/cwd/env/configuration overrides.
3. Generate and commit the applicable Cargo lockfile. Standalone packages may
   own a lockfile; a root virtual Cargo workspace shares its root lockfile.
   This foundation does not choose a production workspace layout in advance.
   Nested virtual workspace-only manifests are not supported by the initial
   registration contract; expand and test that contract before adopting them.
4. Declare every local Cargo dependency as an exact Nx `implicitDependencies`
   project name, including development and target-specific path dependencies.
   The full guard compares Cargo metadata with those declarations. Names must
   be explicit, unique and unnegated so dependency changes can reach consumers.
5. Verify a real source change affects the consuming project, a lock/toolchain
   change reaches the Rust tasks, and failed format/lint/test/build is rejected.

Registration example only (replace the crate path, name and scope):

```json
{
  "name": "example-api",
  "tags": ["platform:rust", "scope:buycycle"],
  "implicitDependencies": [],
  "targets": {
    "format-check": {
      "executor": "nx:run-commands",
      "cache": false,
      "inputs": ["rust", "^rust"],
      "outputs": [],
      "options": {"command": "node .github/rust/run-target.mjs format-check apps/example/backend"}
    },
    "lint": {
      "executor": "nx:run-commands",
      "cache": false,
      "inputs": ["rust", "^rust"],
      "outputs": [],
      "options": {"command": "node .github/rust/run-target.mjs lint apps/example/backend"}
    },
    "test": {
      "executor": "nx:run-commands",
      "cache": false,
      "inputs": ["rust", "^rust"],
      "outputs": [],
      "options": {"command": "node .github/rust/run-target.mjs test apps/example/backend"}
    },
    "build": {
      "executor": "nx:run-commands",
      "cache": false,
      "inputs": ["rust", "^rust"],
      "outputs": [],
      "options": {"command": "node .github/rust/run-target.mjs build apps/example/backend"}
    }
  }
}
```

Cargo metadata discovers packages, workspace roots and local dependencies. Its
`--no-deps --locked` mode is not proof that a lockfile is current. Actual Cargo
lint/test/build commands use `--locked` and must reject inconsistent locks; the
fixture suite checks that behavior through Nx.

## Inputs, intermediate files and limits

The named `rust` input in [`nx.json`](../../nx.json) includes crate source and
tests, Cargo manifests/locks, toolchain/configuration and the shared runner.
`^rust` covers declared dependency inputs. Cargo metadata/configuration changes
are intentionally conservative and may select more Rust projects than the
minimal set. Project-local named-input overrides must not hide these inputs.

Initial Rust targets have Nx caching disabled: restoring native outputs across
toolchains/hosts/targets has not been proven. `nx affected` still selects projects
and Cargo still manages local incremental work under ignored `target/nx/`.
A future cache change needs tested output restoration and environment/target
fingerprints; changing a flag is not sufficient evidence. Existing Python and
TypeScript caching is unchanged.

This gate is build/test plumbing, not a complete architecture/security checker.
It does not prove Actix/Diesel adoption, database isolation, generated API
contracts, Primer UI, ARM64 runtime correctness or release compliance. Gate changes still require independent review. No production artifact is
published or promoted, and no provider credential is used.

Before any app adoption, complete its approved brief and pilot prerequisites.
Every PR uses [the PR process](../../docs/agents/pr-process.md), including the
full named ADR assessment with actual gaps. Leo's separate production-release
approval remains required; keep auto-merge disabled.
