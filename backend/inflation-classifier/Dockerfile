FROM python:3.12-slim

WORKDIR /inference
ENV HF_HOME=/inference/.cache/huggingface
ENV TRANSFORMERS_CACHE=/inference/.cache/huggingface/transformers

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency metadata first for better Docker layer caching
COPY pyproject.toml uv.lock README.md ./

# Install dependencies into a project-local virtualenv without installing this project yet
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src ./src

# Install the project now that src/ exists
RUN uv sync --frozen --no-dev

# Make the venv executables available
ENV PATH="/inference/.venv/bin:$PATH"

# Pre-download the model into the image during build
RUN python -c "from transformers import pipeline; pipeline('zero-shot-classification', model='facebook/bart-large-mnli', device='cpu')"

# Copy source code
COPY src ./src

# Optional: avoid Python writing .pyc files and buffer logs less
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["inflation-classifier"]