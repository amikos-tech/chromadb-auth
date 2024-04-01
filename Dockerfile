ARG CHROMA_VERSION=0.4.24
FROM ghcr.io/chroma-core/chroma:${CHROMA_VERSION} as base

COPY chroma_auth/ /chroma/chroma_auth
