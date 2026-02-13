FROM python:3.9-alpine

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install kubectl
ARG TARGETARCH
RUN apk update \
    && apk add curl \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/${TARGETARCH}/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin

# Copy project files
WORKDIR /app
COPY pyproject.toml uv.lock README.rst ./
COPY kugl ./kugl

# Install dependencies
RUN uv sync --frozen

# Set Python path
ENV PYTHONPATH=/app

# Default command
ENTRYPOINT ["uv", "run", "kugl"]
