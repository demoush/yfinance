FROM python:3.11-slim

WORKDIR /app

# Install security updates
RUN apt-get update && apt-get dist-upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./yfinance/ ./yfinance
COPY requirements.txt .
COPY pyrightconfig.json .
COPY setup.py .
COPY setup.cfg .

RUN pip install yfinance
RUN pip install flask
RUN pip install flask-cors
RUN pip install scikit-learn pandas ta joblib

COPY . .

CMD ["python", "index.py"]