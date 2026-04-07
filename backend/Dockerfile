# Dockerfile for Django backend
# CRITICAL FIX: Use stable Debian Bookworm instead of Trixie (testing) for better network reliability
FROM python:3.13-slim-bookworm

WORKDIR /app

# CRITICAL FIX: Install system dependencies with robust retry logic and error handling
# Split into essential and optional packages - continue even if optional packages fail
# Configure apt to handle network timeouts better
RUN echo 'Acquire::http::Timeout "60";' > /etc/apt/apt.conf.d/99timeout && \
    echo 'Acquire::ftp::Timeout "60";' >> /etc/apt/apt.conf.d/99timeout && \
    echo 'Acquire::Retries "5";' >> /etc/apt/apt.conf.d/99timeout

# Install essential packages (must succeed)
RUN set -eux; \
    # Retry apt-get update up to 5 times with exponential backoff
    for i in 1 2 3 4 5; do \
        apt-get update --fix-missing && break || (echo "Retry $i failed, waiting..." && sleep $((i * 5))); \
    done && \
    # Install essential network and build tools first (must succeed)
    apt-get install -y --no-install-recommends \
        curl \
        wget \
        ca-certificates \
        gnupg2 \
        build-essential \
        python3-dev \
        libpq-dev \
        pkg-config \
    && \
    # Install git separately with retry logic (may have network dependencies)
    (apt-get install -y --no-install-recommends git || \
     (echo "Warning: git install failed, retrying..." && sleep 10 && \
      apt-get install -y --no-install-recommends git || \
      echo "Warning: git installation failed, continuing without it...")) && \
    # Install essential document processing libraries (must succeed)
    apt-get install -y --no-install-recommends \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        libmagic1 \
    && \
    rm -rf /var/lib/apt/lists/*

# Install document processing tools (optional - don't fail build)
RUN set +e; \
    apt-get update --fix-missing || true; \
    apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        antiword \
        unrtf \
    || (echo "Warning: Document tools failed, retrying..." && \
        sleep 10 && \
        apt-get update --fix-missing && \
        apt-get install -y --no-install-recommends \
            poppler-utils \
            tesseract-ocr \
            antiword \
            unrtf \
    || echo "Warning: Document tools installation failed, continuing without them..."); \
    rm -rf /var/lib/apt/lists/* || true

# Install audio processing tools (optional - don't fail build)
# Note: These packages have many X11 dependencies that may fail due to network issues
RUN set +e; \
    apt-get update --fix-missing || true; \
    apt-get install -y --no-install-recommends \
        flac \
        ffmpeg \
        lame \
        libmad0 \
        libsox-fmt-mp3 \
        sox \
        swig \
        libpulse-dev \
    || (echo "Warning: Audio packages failed, retrying..." && \
        sleep 10 && \
        apt-get update --fix-missing && \
        apt-get install -y --no-install-recommends \
            flac \
            ffmpeg \
            lame \
            libmad0 \
            libsox-fmt-mp3 \
            sox \
            swig \
            libpulse-dev \
    || echo "Warning: Audio packages failed to install, continuing without them..."); \
    rm -rf /var/lib/apt/lists/* || true; \
    apt-get clean || true

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download BERTScore models during build (optional - don't fail build if it fails)
# This ensures models are available offline during evaluation
# BERTScore will download models on first use, so we trigger that here during build
RUN set +e; \
    echo "📥 Pre-downloading BERTScore models..." && \
    python3 -c "\
import sys; \
try: \
    from bert_score import score; \
    print('Downloading BERTScore models for English...'); \
    # Trigger model download by running a dummy score calculation \
    P, R, F1 = score(['This is a test sentence.'], ['This is a test sentence.'], lang='en', verbose=False, device='cpu'); \
    print('✅ BERTScore models downloaded successfully'); \
except Exception as e: \
    print(f'⚠️ Warning: BERTScore model pre-download failed: {e}'); \
    print('Models will be downloaded on first use during evaluation'); \
    sys.exit(0) \
" || echo "⚠️ BERTScore model download skipped (will download on first use)"; \
    echo "BERTScore model pre-download step completed"

# Create necessary directories
RUN mkdir -p /app/media /app/logs /app/volumes

# Copy application code
COPY . .

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/admin/ || exit 1

# Default command - runs migrations, sets up container data, and starts server
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate && python manage.py setup_container_data && python manage.py runserver 0.0.0.0:8000"]
