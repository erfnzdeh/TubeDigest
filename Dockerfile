# Common build stage
FROM python:3.11-slim as common-build-stage

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create data directory for persistent storage
RUN mkdir -p /data

# Copy the application
COPY . .

# Create a non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app /data

# Development stage
FROM common-build-stage as development

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=development
ENV YOUTUBE_API_KEY=${YOUTUBE_API_KEY}
ENV TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
ENV TELEGRAM_CHANNEL_ID=${TELEGRAM_CHANNEL_ID}
ENV OPENAI_API_KEY=${OPENAI_API_KEY}
ENV YOUTUBE_CHANNEL_IDS=${YOUTUBE_CHANNEL_IDS}

USER appuser
CMD ["python", "youtube_summary_bot.py"]

# Production stage
FROM common-build-stage as production

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
ENV YOUTUBE_API_KEY=${YOUTUBE_API_KEY}
ENV TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
ENV TELEGRAM_CHANNEL_ID=${TELEGRAM_CHANNEL_ID}
ENV OPENAI_API_KEY=${OPENAI_API_KEY}
ENV YOUTUBE_CHANNEL_IDS=${YOUTUBE_CHANNEL_IDS}

USER appuser
CMD ["python", "youtube_summary_bot.py"] 