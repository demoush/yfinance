FROM python:3.11-slim

WORKDIR /app


# Install security updates and cron
RUN apt-get update && apt-get dist-upgrade -y && apt-get install -y cron && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./yfinance/ ./yfinance
COPY requirements.txt .
COPY pyrightconfig.json .
COPY setup.py .
COPY setup.cfg .


# Install all required Python packages, including catalyst dependencies
RUN pip install --upgrade pip \
    && pip install yfinance flask flask-cors scikit-learn pandas ta joblib sec-api finvizfinance transformers

COPY . .


# Add cron job to run build_calendar_cache.py at midnight every day
#RUN echo "0 0 1 * * cd /app && python /app/build_calendar_cache.py >> /var/log/cron.log 2>&1" > /etc/cron.d/calendar-cache
#RUN chmod 0644 /etc/cron.d/calendar-cache && crontab /etc/cron.d/calendar-cache

# Start cron and Flask app
#CMD service cron start && python index.py
CMD python index.py