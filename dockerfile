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
CMD ["python", "index.py"]