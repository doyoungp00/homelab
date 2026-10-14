FROM codercom/code-server:latest
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates git libicu-dev gpg \
    python3 python3-pip python3-venv python3-dev python-is-python3 \
    && mkdir -p -m 755 /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# .NET SDK (installed outside $HOME on purpose)
ENV DOTNET_ROOT=/usr/share/dotnet \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1
RUN curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dn.sh \
    && bash /tmp/dn.sh --channel LTS --install-dir /usr/share/dotnet \
    && ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet \
    && rm /tmp/dn.sh

# Rust (system-wide, writable by the coder user)
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile default --no-modify-path \
    && chmod -R a+rwX /usr/local/rustup /usr/local/cargo

# sops
ARG SOPS_VERSION=3.13.3
RUN curl -fsSL -o /usr/local/bin/sops \
    "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.amd64" \
    && chmod +x /usr/local/bin/sops

USER root
RUN mkdir -p /home/coder/.cache /home/coder/.dotnet /home/coder/.local/share \
    && chown -R 568:568 /home/coder