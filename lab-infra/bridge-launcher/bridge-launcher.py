#!/usr/bin/env python3
"""
O4AA bridge Launcher API - single-purpose configure+up service.

Lets the attendee's Windows VDI bootstrap start its paired bridge at run time, so the bridge VM can
boot bare/idle (blank .env, stack down) and receive its Okta org identity only when an attendee is
assigned. See lab-infra/BRIDGE-LAUNCHER-API-SPEC.md.

Dependency-free (Python 3 stdlib). Runs as root via systemd so it can write the bundle .env and run
`docker compose`. Bind is pod-internal; a Bearer secret gates the mutating/status calls.

Endpoints:
  GET  /healthz  (no auth)  -> {"launcher":"ok"}                       launcher liveness
  POST /launch   (Bearer)   -> 202 {"status":"launching",...}          write .env + `docker compose up`
                               body: {"okta_domain":"x.okta.com","admin_ui_client_id":"0oa..."}
  GET  /status   (Bearer)   -> {"phase","adapter_ready","admin_ui_ready","containers","okta_domain","error"}
"""
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --- config ---------------------------------------------------------------
SECRET_PATH = os.environ.get("BRIDGE_LAUNCHER_SECRET_FILE", "/opt/bridge/launcher/secret")
PORT        = int(os.environ.get("BRIDGE_LAUNCHER_PORT", "9090"))
BUNDLE_GLOB = os.environ.get("BRIDGE_BUNDLE_GLOB", "/opt/bridge/okta-mcp-adapter-bundle-*")
COMPOSE_FILE = "docker-compose.bundle.yml"
ADAPTER_CONTAINER  = "okta-agent-mcp-adapter"
ADMIN_UI_CONTAINER = "okta-mcp-admin-ui"
ADAPTER_SERVICE    = "okta-agent-mcp-adapter"
ADMIN_UI_SERVICE   = "admin-ui"
COMPOSE_TIMEOUT = 240  # seconds

DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.okta(preview)?\.com$")
CID_RE    = re.compile(r"^0oa[a-zA-Z0-9]+$")

# --- shared state ---------------------------------------------------------
_state_lock = threading.Lock()
_state = {"phase": "idle", "okta_domain": None, "error": None}  # phase: idle|launching|up|error
_launch_lock = threading.Lock()  # serialize launches


def log(msg):
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} [launcher] {msg}", flush=True)


def read_secret():
    with open(SECRET_PATH) as f:
        return f.read().strip()


def bundle_dir():
    matches = sorted(glob.glob(BUNDLE_GLOB))
    if not matches:
        raise RuntimeError(f"no bundle dir matching {BUNDLE_GLOB}")
    return matches[-1]


def set_env(bundle, domain, cid):
    """Idempotently set the 4 org-identity keys in the bundle .env, preserving everything else."""
    env_path = os.path.join(bundle, ".env")
    keys = {
        "OKTA_DOMAIN": domain,
        "OKTA_ISSUER": f"https://{domain}",
        "ADMIN_UI_OKTA_ISSUER": f"https://{domain}",
        "ADMIN_UI_OKTA_CLIENT_ID": cid,
    }
    seen, out = set(), []
    with open(env_path) as f:
        for line in f:
            k = line.split("=", 1)[0].strip()
            if k in keys:
                out.append(f"{k}={keys[k]}\n")
                seen.add(k)
            else:
                out.append(line)
    for k, v in keys.items():
        if k not in seen:
            out.append(f"{k}={v}\n")
    tmp = env_path + ".tmp"
    with open(tmp, "w") as f:
        f.writelines(out)
    os.replace(tmp, env_path)
    log(f"wrote org identity to {env_path} (OKTA_DOMAIN={domain})")


def compose(bundle, *args, check=True):
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, *args]
    log("run: " + " ".join(cmd))
    return subprocess.run(cmd, cwd=bundle, check=check, timeout=COMPOSE_TIMEOUT,
                          capture_output=True, text=True)


def do_launch(domain, cid):
    """Runs in a background thread; updates _state."""
    try:
        bundle = bundle_dir()
        set_env(bundle, domain, cid)
        # force-recreate the two services whose env changed, then ensure the whole stack is up
        compose(bundle, "up", "-d", "--force-recreate", ADAPTER_SERVICE, ADMIN_UI_SERVICE)
        compose(bundle, "up", "-d")
        with _state_lock:
            _state.update(phase="up", error=None)
        log(f"launch complete for {domain}")
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or str(e)).strip()[-500:]
        with _state_lock:
            _state.update(phase="error", error=msg)
        log(f"launch FAILED: {msg}")
    except Exception as e:  # noqa: BLE001
        with _state_lock:
            _state.update(phase="error", error=str(e))
        log(f"launch FAILED: {e}")
    finally:
        if _launch_lock.locked():
            _launch_lock.release()


def container_health(name):
    try:
        out = subprocess.run(
            ["docker", "inspect", "-f",
             "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}", name],
            capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "absent"
    except Exception:  # noqa: BLE001
        return "unknown"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        return self.headers.get("Authorization", "") == f"Bearer {read_secret()}"

    def log_message(self, *a):  # quiet the default access log; we log our own
        pass

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"launcher": "ok"})
        if self.path == "/status":
            if not self._authed():
                return self._send(401, {"error": "unauthorized"})
            a = container_health(ADAPTER_CONTAINER)
            u = container_health(ADMIN_UI_CONTAINER)
            with _state_lock:
                st = dict(_state)
            return self._send(200, {
                "phase": st["phase"],
                "okta_domain": st["okta_domain"],
                "error": st["error"],
                "adapter_ready": a == "healthy",
                "admin_ui_ready": u == "healthy",
                "containers": {"adapter": a, "admin_ui": u},
            })
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/launch":
            return self._send(404, {"error": "not found"})
        if not self._authed():
            return self._send(401, {"error": "unauthorized"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:  # noqa: BLE001
            return self._send(400, {"error": "invalid JSON body"})
        domain = str(body.get("okta_domain", "")).strip().lower()
        cid = str(body.get("admin_ui_client_id", "")).strip()
        if not DOMAIN_RE.match(domain):
            return self._send(400, {"error": "invalid okta_domain (expected <sub>.okta.com)"})
        if not CID_RE.match(cid):
            return self._send(400, {"error": "invalid admin_ui_client_id (expected 0oa...)"})
        if not _launch_lock.acquire(blocking=False):
            return self._send(409, {"error": "a launch is already in progress"})
        with _state_lock:
            _state.update(phase="launching", okta_domain=domain, error=None)
        threading.Thread(target=do_launch, args=(domain, cid), daemon=True).start()
        return self._send(202, {"status": "launching", "okta_domain": domain})


def main():
    # fail fast if the secret file is missing/unreadable
    try:
        if not read_secret():
            raise RuntimeError("secret file is empty")
    except Exception as e:  # noqa: BLE001
        log(f"FATAL: cannot read secret at {SECRET_PATH}: {e}")
        sys.exit(1)
    log(f"starting on 0.0.0.0:{PORT} (bundle glob {BUNDLE_GLOB})")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
