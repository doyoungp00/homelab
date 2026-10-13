FROM codercom/code-server:latest
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates git libicu-dev \
    && rm -rf /var/lib/apt/lists/*

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

USER root
RUN mkdir -p /home/coder/.cache /home/coder/.dotnet /home/coder/.local/share \
    && chown -R 568:568 /home/coder