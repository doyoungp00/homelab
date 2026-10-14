FROM docker:27-cli

RUN apk add --no-cache python3 git curl ca-certificates

ARG SOPS_VERSION=3.13.3
RUN curl -fsSL -o /usr/local/bin/sops \
  "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.amd64" \
  && chmod +x /usr/local/bin/sops

COPY agent.py favicon.png /

ENTRYPOINT ["python3", "/agent.py"]
