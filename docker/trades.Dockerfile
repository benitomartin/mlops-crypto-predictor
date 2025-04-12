# The multistage.Dockerfile example extends the Dockerfile example to use multistage
# builds to reduce the final size of the image.

# --- Stage 1: Build the application ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Enable bytecode compilation and set uv to use system interpreter
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies using uv (cache + bind mounts for speed)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Add project files and sync full dependencies (prod only)
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# --- Stage 2: Final image without uv ---
FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN groupadd -r app && useradd -r -g app app

# Copy application files from builder stage with correct ownership
COPY --from=builder --chown=app:app /app /app

# Create state folder and mark it as a volume
RUN mkdir -p /app/state && chown app:app /app/state
VOLUME /app/state

# Set environment path to virtual environment if applicable
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER app

# Start the Python service without uv
CMD ["python", "/app/services/trades/src/trades/main.py"]
    

# If you want to debug the file system, uncomment the line below
# This will keep the container running and allow you to exec into it
# CMD ["/bin/bash", "-c", "sleep 999999"]