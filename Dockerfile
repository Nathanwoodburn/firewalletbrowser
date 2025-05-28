FROM --platform=$BUILDPLATFORM python:3.10-alpine AS builder

WORKDIR /app

COPY requirements.txt /app
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt

COPY . /app

# Add mount point for data volume
# VOLUME /data
RUN apk add git openssl curl

ENTRYPOINT ["python3"]
CMD ["server.py"]

FROM builder as dev-envs
