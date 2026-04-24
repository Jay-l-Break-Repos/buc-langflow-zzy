# Use Python 3.12.3-slim to match the official Langflow build
FROM python:3.12.3-slim

# Install system dependencies
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
    build-essential \
    git \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install uv==0.7.20

# Set working directory
WORKDIR /app

# Copy project files
COPY repo/ .

# Install dependencies using uv
RUN uv sync --frozen --no-editable

# Create a stub frontend directory in case the package doesn't include one.
# Without this, the server crashes if --backend-only is not set.
RUN .venv/bin/python -c "\
import langflow, pathlib; \
p = pathlib.Path(langflow.__file__).parent / 'frontend'; \
p.mkdir(exist_ok=True); \
(p / 'index.html').write_text('<html><body>Langflow API</body></html>')" \
    || true

# Set environment variables for Langflow
ENV LANGFLOW_HOST=0.0.0.0
ENV LANGFLOW_PORT=9090
ENV LANGFLOW_BACKEND_ONLY=true
ENV PATH="/app/.venv/bin:$PATH"

# Expose port 9090
EXPOSE 9090

# Run Langflow - use --backend-only to skip frontend serving
CMD ["langflow", "run", "--host", "0.0.0.0", "--port", "9090", "--backend-only"]
