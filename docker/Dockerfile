# The multistage.Dockerfile example extends the Dockerfile example to use multistage
# builds to reduce the final size of the image.

# --- Stage 1: Build the application ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Enable bytecode compilation and set uv to use system interpreter
ENV UV_COMPILE_BYTECODE=1

# Copy dependencies instead of symlinking and use system Python interpreter
ENV UV_LINK_MODE=copy

# Use system Python interpreter
ENV UV_PYTHON_DOWNLOADS=0

# Set working directory
WORKDIR /app

# Add the workspace before the installation step
# Otherwise, uv will try to install the workspace before it's added
# And will fail  the uv sync command below
COPY services /app/services

# Install dependencies using uv (cache + bind mounts for speed)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Add project files and sync full dependencies (prod only)
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Clean up unnecessary files to reduce image size
RUN find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true; \
    find /app -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true; \
    find /app -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true; \
    find /app -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true; \
    find /app -type d -name "images" -exec rm -rf {} + 2>/dev/null || true; \
    find /app -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true; \
    find /app -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true; \
    find /app -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true; \
    find /app -type f -name "*.pyc" -delete 2>/dev/null || true


# --- Stage 2: Final image without uv ---
FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /app

# Add service name as an argument
ARG SERVICE_NAME
ENV SERVICE_NAME=${SERVICE_NAME}

# Create non-root user for security
RUN groupadd -r app && useradd -r -g app app

# Create state directory with proper permissions
RUN mkdir -p /app/state && chown -R app:app /app/state

# Copy application files from builder stage with correct ownership
COPY --from=builder --chown=app:app /app /app

# Set environment path to virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER app

# Start the Python service without uv
ENTRYPOINT ["sh", "-c", "exec python /app/services/${SERVICE_NAME}/src/${SERVICE_NAME}/main.py"]
CMD []

# If you want to debug the file system, uncomment the line below
# This will keep the container running and allow you to exec into it
# CMD ["/bin/bash", "-c", "sleep 999999"]