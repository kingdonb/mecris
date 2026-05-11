# .devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:3.13-bullseye

# Install Node.js (for MCP server and other tools)
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get update && apt-get install -y nodejs

# Install Rust and WASM target
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && /root/.cargo/bin/rustup target add wasm32-wasip1

# Install uv for Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Spin CLI and plugins
RUN curl -fsSL https://developer.fermyon.com/downloads/install.sh | bash \
    && mv spin /usr/local/bin/ \
    && spin plugins update \
    && spin plugins install py2wasm --yes

# Install Java 17 (needed for Android components)
RUN apt-get update && apt-get install -y openjdk-17-jdk

# Install additional system dependencies
RUN apt-get update && apt-get install -y \
    jq \
    make \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Add cargo and local bin to PATH
ENV PATH="/root/.cargo/bin:/root/.local/bin:${PATH}"

# Verify installations
RUN python3 --version && node --version && rustc --version && uv --version && spin --version
