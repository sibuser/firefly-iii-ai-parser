# -------- Stage 1: Builder (installs deps & project into a venv) --------
FROM python:3.13-slim AS builder

# System deps needed at build time (wheels, OpenCV headers, PyMuPDF build helpers, etc.)
RUN apt-get update && apt-get install -y \
  build-essential \
  libgl1 \
  libglib2.0-0 \
  poppler-utils \
  && rm -rf /var/lib/apt/lists/*

# Install uv (project/package manager)
RUN pip install --no-cache-dir uv

# Create an isolated virtualenv for the app
# We install into /opt/venv so it’s easy to COPY into the runtime image
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy only manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install locked dependencies (no project code yet -> better cache reuse)
# Use a cache mount so repeat builds are fast
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen

# Now bring in the rest of the source code and install the project itself
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen
# At this point, /opt/venv contains all deps + your project installed.

# -------- Stage 2: Runtime (slim image with only what’s needed to run) --------
FROM python:3.13-slim AS runtime

# Runtime-only system libs for OpenCV + PyMuPDF
# (libGL & glib are common cv2 runtime deps; poppler-utils for some PDF ops)
RUN apt-get update && apt-get install -y \
  libgl1 \
  libglib2.0-0 \
  poppler-utils \
  && rm -rf /var/lib/apt/lists/*

# Copy the ready-to-run virtualenv from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Add venv to PATH
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Copy only your app (no build toolchain)
WORKDIR /app
COPY --from=builder /app /app

# Start the bot / CLI
CMD [".venv/bin/python", "main.py"]