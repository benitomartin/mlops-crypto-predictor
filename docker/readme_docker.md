# Docker Configuration

This document explains the multi-stage Dockerfile used for the trades service.

## Overview

The `Dockerfile` uses a multi-stage build pattern to create an optimized and secure production image. It consists of two stages:

1. Builder stage - for dependency installation
1. Final stage - for running the application

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
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0
```

- `UV_COMPILE_BYTECODE=1`: Pre-compiles Python bytecode for faster startup
- `UV_LINK_MODE=copy`: Copies dependencies instead of symlinking
- `UV_PYTHON_DOWNLOADS=0`: Uses system Python interpreter

The workspace is added before dependency installation:

```dockerfile
COPY services /app/services
```

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
- Environment path and variable setup

The service name is passed as an argument:

```dockerfile
ARG SERVICE_NAME
ENV SERVICE_NAME=${SERVICE_NAME}
```

Security configuration:

```dockerfile
RUN groupadd -r app && useradd -r -g app app
COPY --from=builder --chown=app:app /app /app
```

The virtual environment is added to the PATH:

```dockerfile
ENV PATH="/app/.venv/bin:$PATH"
```

The service is started without `uv` and as a non-root user:

```dockerfile
USER app
ENTRYPOINT ["sh", "-c", "exec python /app/services/${SERVICE_NAME}/src/${SERVICE_NAME}/main.py"]
CMD []
```

## Best Practices Implemented

1. **Security**:

   - Non-root user
   - Minimal base image
   - Proper file permissions

1. **Performance**:

   - Multi-stage build
   - Cache optimization
   - Bytecode compilation

1. **Size Optimization**:

   - Slim base image
   - No dev dependencies
   - Clean build artifacts

1. **Reproducibility**:

   - Locked dependencies
   - Frozen environment
   - Explicit Python version

## Building the Image

```bash
make build-for-dev service=trades # Add the service name as an argument
```

## Loading the Image into the Kind Cluster

```bash
make push-for-dev service=trades # Add the service name as an argument
```

You can verify the image is loaded in the Kind cluster with:

```bash
docker exec rwml-34fa-control-plane crictl images | grep trades
```

## Deploying the Image into the Kind Cluster

For deployment, you need to apply the Kubernetes manifest under `deployments/dev/`. Make sure to set the `KAFKA_BROKER_ADDRESS` to the correct address.

```bash
make deploy-for-dev service=trades # Add the service name as an argument
```

To verify the deployment, use the following command or use `k9s` terminal:

```bash
kubectl get deployments --all-namespaces
```

![deployment trades](../images/deployment_trades1.png)

![deployment trades](../images/deployment_trades2.png)
