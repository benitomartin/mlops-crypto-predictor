# Docker Configuration

This document explains the multi-stage Dockerfile used for the trades service.

## Overview

The `trades.Dockerfile` uses a multi-stage build pattern to create an optimized and secure production image. It consists of two stages:

1. Builder stage - for dependency installation
2. Final stage - for running the application

## Stage 1: Builder

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
```

This stage uses `uv` to handle dependencies. Key features:

- Uses official `uv` image with Python 3.12
- Based on Debian Bookworm (slim variant)
- Tagged as 'builder' for reference in second stage

Environment configuration:

```dockerfile
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
```

- `UV_COMPILE_BYTECODE=1`: Pre-compiles Python bytecode for faster startup
- `UV_LINK_MODE=copy`: Copies dependencies instead of symlinking
- `UV_PYTHON_DOWNLOADS=0`: Uses system Python interpreter

The build process uses Docker's cache mount feature for faster builds:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
```

Add project files and sync full dependencies (prod only):

```dockerfile
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
```

## Stage 2: Final Image

```dockerfile
FROM python:3.12-slim-bookworm
```

The final stage creates a minimal production image. Security features include:

- Non-root user creation
- Proper file ownership
- Volume mounting for state persistence

Security configuration:

```dockerfile
RUN groupadd -r app && useradd -r -g app app
COPY --from=builder --chown=app:app /app /app
```

State management:

```dockerfile
RUN mkdir -p /app/state && chown app:app /app/state
VOLUME /app/state
```

The service runs as non-root user:

```dockerfile
USER app
CMD ["python", "/app/services/trades/src/trades/main.py"]
```

## Best Practices Implemented

1. **Security**:
   - Non-root user
   - Minimal base image
   - Proper file permissions

2. **Performance**:
   - Multi-stage build
   - Cache optimization
   - Bytecode compilation

3. **Size Optimization**:
   - Slim base image
   - No dev dependencies
   - Clean build artifacts

4. **Reproducibility**:
   - Locked dependencies
   - Frozen environment
   - Explicit Python version

## Building the Image

```bash
docker build -t trades:dev -f docker/trades.Dockerfile .
```

## Running the Container

```bash
docker run -d \
  --name trades-service \
  -v trades-data:/app/state \
  trades:dev
```
