# Build the app once; release promotion uses this tested image by digest.
FROM node:22-bookworm-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee AS web
WORKDIR /repo
COPY package.json package-lock.json ./
COPY apps/marrow/frontend/package.json apps/marrow/frontend/package.json
COPY apps/dk/tag-printer/frontend/package.json apps/dk/tag-printer/frontend/package.json
COPY apps/firstout/frontend/package.json apps/firstout/frontend/package.json
COPY apps/storefront/commerce/package.json apps/storefront/commerce/package.json
COPY apps/storefront/web/package.json apps/storefront/web/package.json
COPY libs/ui/package.json libs/ui/package.json
COPY libs/primer/package.json libs/primer/package.json
COPY apps/buycycle/frontend/package.json apps/buycycle/frontend/package.json
RUN npm ci
COPY libs/primer libs/primer
COPY apps/buycycle/frontend apps/buycycle/frontend
RUN npm run build --workspace apps/buycycle/frontend

FROM rust:1.95.0-bookworm@sha256:6258907abe69656e41cd992e0b705cdcfabcbbe3db374f92ed2d47121282d4a1 AS rust
ARG SOURCE_COMMIT
ARG TARGETARCH
ENV BUYCYCLE_SOURCE_COMMIT=${SOURCE_COMMIT}
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /repo
COPY rust-toolchain.toml ./
COPY libs/rust/api-errors libs/rust/api-errors
COPY libs/rust/identity libs/rust/identity
COPY apps/buycycle/backend apps/buycycle/backend
COPY apps/buycycle/ops/grant-runtime.sql apps/buycycle/ops/grant-runtime.sql
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,id=buycycle-rust-${TARGETARCH},target=/build \
    cargo build --locked --release --manifest-path apps/buycycle/backend/Cargo.toml --bins --target-dir /build \
    && mkdir /artifacts && cp /build/release/buycycle-backend /build/release/collect /build/release/migrate /build/release/import-legacy /build/release/seed /build/release/replay /artifacts/

FROM debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libpq5 curl tzdata && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 buycycle && useradd --uid 10001 --gid 10001 --no-create-home buycycle
ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="https://github.com/F0rge/f0rge" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}"
COPY --from=rust /artifacts/ /usr/local/bin/
COPY --from=web /repo/apps/buycycle/frontend/dist /app/frontend
COPY --chmod=755 apps/buycycle/ops/entrypoint.sh /usr/local/bin/buycycle-entrypoint
USER 10001:10001
ENV BUYCYCLE_BIND=0.0.0.0:8080 BUYCYCLE_FRONTEND_DIR=/app/frontend
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD curl --fail --silent http://127.0.0.1:8080/ready || exit 1
ENTRYPOINT ["/usr/local/bin/buycycle-entrypoint"]
CMD ["buycycle-backend", "serve"]
