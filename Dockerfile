FROM --platform=$BUILDPLATFORM python:3.13-alpine AS builder

WORKDIR /app
RUN apk add git openssl curl
COPY requirements.txt /app
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt

COPY . /app

# Add mount point for data volume
VOLUME /app/user_data


ARG BUILD_DATE
ARG VCS_REF

LABEL org.opencontainers.image.title="FireWallet" \
      org.opencontainers.image.description="The Handshake Wallet That is Fire" \
      org.opencontainers.image.url="https://firewallet.au" \
      org.opencontainers.image.source="https://git.woodburn.au/nathanwoodburn/firewalletbrowser" \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.created=$BUILD_DATE \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENTRYPOINT ["python3"]
CMD ["server.py"]

FROM builder AS dev-envs
