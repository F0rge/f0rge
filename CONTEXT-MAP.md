# Context Map

Vellano-family product work uses these contexts. Marrow and dk stay out of Stockroom tenancy language.

## Contexts

- [Vellano / Stockroom](./apps/vellano/CONTEXT.md): furniture back-office product (placeholder name **Stockroom**); Vellano is the first Company
- Marrow: health tracker — no `CONTEXT.md` yet
- dk tag printer: DasKasas price tags — no `CONTEXT.md` yet

## Relationships

- **Stockroom → Company workspace**: the landing creates a Company; the shared Vellano app serves that Company’s workspace on its own hostname and database
- **Vellano (the shop) → Stockroom**: the existing Gauteng retailer is tenant `vellano`, not a special code path in the landing
