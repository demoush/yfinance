FROM python:3.11-slim

WORKDIR /app

# Install security updates, cron, and Playwright system dependencies
RUN apt-get update && apt-get dist-upgrade -y && apt-get install -y \
    cron \
    libwoff1 \
    libopus0 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    libgtk-3-0 \
    libgles2 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./yfinance/ ./yfinance
COPY requirements.txt .
COPY pyrightconfig.json .
COPY setup.py .
COPY setup.cfg .

# Install Python packages, including Playwright
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && python -m playwright install --with-deps

COPY . .

# Add cron jobs for build_calendar_cache.py and scrape_xstocks.py at midnight daily
RUN echo "0 0 * * * python /app/scrape_xstocks.py >> /app/scrape_xstocks.log 2>&1" >> /etc/cron.d/xstocks_cron \
    && chmod 0644 /etc/cron.d/xstocks_cron \
    && crontab /etc/cron.d/xstocks_cron

# Copy entrypoint script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Use entrypoint to start cron and Flask
CMD ["./entrypoint.sh"]