"""Generates Gatus's config.yaml from gatus.* labels on running containers.

Gatus has no built-in label-based service discovery (unlike Traefik) — it
only reads a static config.yaml, though it does hot-reload that file on
change. This fills the gap: every GENERATE_INTERVAL_SECONDS, it lists
containers carrying `gatus.enable=true`, reads their `gatus.*` labels, and
rewrites config.yaml from them.

Label contract, per container:
  gatus.enable=true               required to be picked up at all
  gatus.url=http://...            required
  gatus.name=<name>               optional, defaults to the compose service name
  gatus.group=<group>             optional
  gatus.interval=<duration>       optional (e.g. "30s"); Gatus's own default applies if absent
  gatus.conditions=<json>         optional JSON array of condition strings,
                                   defaults to '["[STATUS] == 200"]'
  gatus.alert=true                optional, sends an ntfy notification when this
                                   endpoint goes down and again when it recovers
  gatus.headers.<Header>=val      optional, any number of these become the endpoint's `headers:` map
  gatus.dns.<key>=val             optional, any number of these become the endpoint's `dns:` map
                                   (e.g. gatus.dns.query-name=, gatus.dns.query-type=) — for the
                                   DNS endpoint type, key names passed through verbatim

Docker labels are a flat key->value map, not a multi-map — a container that
tunnels several logical services through itself (e.g. network_mode:
service:gluetun) can't just repeat `gatus.url=` for each one, since the
later value silently overwrites the earlier one. For that case, add a
bracketed index after `gatus`, matching Homepage's own `widgets[N]`
convention: `gatus[1].url=...`, `gatus[1].name=...`, etc. Unindexed labels
are index 0, so every existing single-service container needs no changes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/config/config.yaml"))
INTERVAL_SECONDS = int(os.environ.get("GENERATE_INTERVAL_SECONDS", "30"))
DEFAULT_CONDITIONS = ["[STATUS] == 200"]
GATUS_FIELD_RE = re.compile(r"^gatus(?:\[(\d+)\])?\.(.+)$")
# Reached over `proxy` rather than through Traefik, for the same reason the
# checks themselves are: going out to the public hostname and back in would
# hairpin an internal alert through the WAF. NTFY_TOPIC has to match the topic
# ntfy's own NTFY_AUTH_ACCESS grants the `gatus` account write access to.
NTFY_URL = os.environ.get("NTFY_URL", "http://ntfy")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "alerts")


def log(message: str) -> None:
    print(f"[gatus-generator] {message}", flush=True)


def labeled_container_ids() -> list[str]:
    result = subprocess.run(
        ["docker", "ps", "-q", "--filter", "label=gatus.enable=true"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def container_labels(container_ids: list[str]) -> list[dict[str, str]]:
    if not container_ids:
        return []
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{json .Config.Labels}}", *container_ids],
        check=True,
        capture_output=True,
        text=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line]


def grouped_fields_by_index(labels: dict[str, str]) -> dict[str, dict[str, str]]:
    """Splits e.g. {"gatus[1].url": "...", "gatus.name": "..."} into
    {"1": {"url": "..."}, "0": {"name": "..."}} — unindexed labels are
    index "0"."""
    grouped: dict[str, dict[str, str]] = {}
    for key, value in labels.items():
        match = GATUS_FIELD_RE.match(key)
        if not match:
            continue
        index, field = match.group(1) or "0", match.group(2)
        grouped.setdefault(index, {})[field] = value
    return grouped


def endpoint_from_fields(
    fields: dict[str, str], labels: dict[str, str]
) -> dict[str, Any] | None:
    url = fields.get("url")
    if not url:
        return None

    endpoint: dict[str, Any] = {
        "name": fields.get("name") or labels.get("com.docker.compose.service") or "unnamed",
        "url": url,
    }
    if "group" in fields:
        endpoint["group"] = fields["group"]
    if "interval" in fields:
        endpoint["interval"] = fields["interval"]

    conditions_raw = fields.get("conditions")
    if conditions_raw:
        try:
            endpoint["conditions"] = json.loads(conditions_raw)
        except json.JSONDecodeError:
            log(
                f"WARNING: {endpoint['name']}: gatus.conditions is not valid "
                "JSON, using default"
            )
            endpoint["conditions"] = list(DEFAULT_CONDITIONS)
    else:
        endpoint["conditions"] = list(DEFAULT_CONDITIONS)

    if fields.get("alert", "").lower() == "true":
        endpoint["alerts"] = [{"type": "ntfy"}]

    headers = {
        field[len("headers.") :]: value
        for field, value in fields.items()
        if field.startswith("headers.")
    }
    if headers:
        endpoint["headers"] = headers

    dns = {
        field[len("dns.") :]: value
        for field, value in fields.items()
        if field.startswith("dns.")
    }
    if dns:
        endpoint["dns"] = dns

    return endpoint


def endpoints_from_labels(labels: dict[str, str]) -> list[dict[str, Any]]:
    endpoints = []
    for fields in grouped_fields_by_index(labels).values():
        endpoint = endpoint_from_fields(fields, labels)
        if endpoint is not None:
            endpoints.append(endpoint)
    return endpoints


def ntfy_alerting() -> dict[str, Any]:
    """The `alerting.ntfy` block that `alerts: [{type: ntfy}]` resolves against.

    The token is emitted as a literal `${NTFY_TOKEN}` rather than its value:
    Gatus expands environment variables when it loads config.yaml, so the
    credential stays in gatus's own env and never reaches the file, which this
    generator rewrites in the clear on a volume Homepage and Dozzle can read.
    """
    return {
        "url": NTFY_URL,
        "topic": NTFY_TOPIC,
        "token": "${NTFY_TOKEN}",
        # Three consecutive failures before alerting, so a single missed check
        # during a redeploy doesn't page anyone.
        "default-alert": {
            "failure-threshold": 3,
            "success-threshold": 2,
            "send-on-resolved": True,
        },
    }


def build_config() -> dict[str, Any]:
    endpoints = []
    for labels in container_labels(labeled_container_ids()):
        container_endpoints = endpoints_from_labels(labels)
        if not container_endpoints:
            log(f"WARNING: gatus.enable=true but no gatus.url, skipping: {labels}")
            continue
        endpoints.extend(container_endpoints)
    endpoints.sort(key=lambda e: e["name"])
    config: dict[str, Any] = {"storage": {"type": "sqlite", "path": "/data/data.db"}}
    # Declared only when something references it. An unused provider block
    # would have Gatus resolving ${NTFY_TOKEN} — and complaining when it's
    # unset — on a stack where nothing has opted into alerting yet.
    if any("alerts" in endpoint for endpoint in endpoints):
        config["alerting"] = {"ntfy": ntfy_alerting()}
    config["endpoints"] = endpoints
    return config


def write_if_changed(config: dict[str, Any]) -> None:
    new_text = yaml.safe_dump(config, sort_keys=False)
    old_text = CONFIG_PATH.read_text() if CONFIG_PATH.is_file() else None
    if new_text == old_text:
        return
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(new_text)
    log(f"wrote {len(config['endpoints'])} endpoint(s) to {CONFIG_PATH}")


def main() -> int:
    while True:
        try:
            write_if_changed(build_config())
        except subprocess.CalledProcessError as exc:
            log(
                f"ERROR: docker call failed: {exc.stderr.strip() if exc.stderr else exc}"
            )
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
