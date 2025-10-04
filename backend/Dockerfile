# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install minimal system dependencies and Playwright browser dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    git \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxss1 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf-2.0-0 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrender1 \
    libxtst6 \
    libglib2.0-0 \
    libcairo2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libx11-6 \
    libx11-xcb1 \
    libxau6 \
    libxcb1 \
    libxdmcp6 \
    libxinerama1 \
    fonts-liberation \
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create virtual env (we're in container)
RUN poetry config virtualenvs.create false

# Install Python dependencies
RUN poetry install --no-root

# Copy application code
COPY . .

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app

# Change ownership to app user
RUN chown -R app:app /app

# Switch to non-root user for browser installation
USER app

# Install Playwright browsers as the app user
RUN poetry run playwright install chromium

# Switch back to root temporarily for final setup
USER root

# Expose port
EXPOSE 8000

# Set environment variables
ENV PORT=8000
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER app

# Start command
CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]