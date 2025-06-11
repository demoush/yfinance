FROM python:3.11-slim

WORKDIR /app

# Install security updates
RUN apt-get update && apt-get dist-upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN apt install python3-flask

COPY ./yfinance/ ./yfinance
COPY requirements.txt .
COPY pyrightconfig.json .
COPY setup.py .
COPY setyp.cfg .

RUN pip install yfinance
RUN pip install flask

COPY . .

CMD ["python", "index.py"]