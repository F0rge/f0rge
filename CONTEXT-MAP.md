# Context Map

## Contexts

- [Delivery](./.github/CONTEXT.md): how a change on `main` becomes a running App
- [Firstout](./apps/firstout/CONTEXT.md): how the furniture back office prices, taxes and records a sale

## Relationships

- **Delivery → every App**: Delivery treats each App as a set of Projects that are built, tested and released together; it knows nothing about what an App does.
