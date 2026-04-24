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

# Set environment variables for Langflow
ENV LANGFLOW_HOST=0.0.0.0
ENV LANGFLOW_PORT=9090
ENV PATH="/app/.venv/bin:$PATH"

# Expose port 9090
EXPOSE 9090

# Run Langflow
CMD ["langflow", "run", "--host", "0.0.0.0", "--port", "9090"]
