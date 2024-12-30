FROM python:3.9-alpine

RUN apk update \
    && apk add curl \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin

RUN mkdir -p /app

COPY requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt

COPY kugl /app/kugl

ENV PYTHONPATH /app
