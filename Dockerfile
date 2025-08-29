FROM --platform=$BUILDPLATFORM python:3.13-alpine AS builder

WORKDIR /app
RUN apk add git openssl curl
COPY requirements.txt /app
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt

COPY . /app

# Add mount point for data volume
# VOLUME /data

ENTRYPOINT ["python3"]
CMD ["server.py"]

FROM builder AS dev-envs
