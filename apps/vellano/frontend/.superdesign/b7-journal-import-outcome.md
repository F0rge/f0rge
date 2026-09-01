# B7 journal CSV import — Superdesign outcome

- **Canvas used:** no.
- **Credits:** `insufficient_credits` this session (billing gate). Did not call the Superdesign CLI.
- **Implementation:** IBM Carbon on existing `/journals`. **Import CSV** (`canMutateBooks`) opens a Modal with `FileUploaderDropContainer` / `FileUploaderItem` (same as bank-recon). Preview then Commit. Errors listed; Commit disabled if `!balanced` or errors. Source `import:simplepay`. No `@f0rge/ui`.
