FROM python:3.9-alpine

RUN apk update \
    && apk add curl \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin

RUN mkdir -p /app/lib

COPY requirements.txt /app
RUN cd /app && pip install -r requirements.txt

COPY lib /app/lib

ENV PYTHONPATH /app/lib
