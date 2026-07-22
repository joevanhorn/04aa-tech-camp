# Spec — VDI-triggered bridge launch via a Launcher API

**Status: VALIDATED.** Tested end-to-end twice, cold, on a real bridge + VDI: `-LaunchBridge` ->
`POST /launch` on an empty-DB bridge -> `Applied 5 migration(s)` -> all 6 containers healthy (adapter,
admin-ui, postgres, redis, and the two demo backends) -> CA fetch succeeds -> toolkit + OpenCode
installed. The design below is the shipped model. Goal: let the attendee's VDI `bootstrap.ps1`
**configure and start** its paired bridge at run time, so the Linux bridge VM can **boot with zero
Okta org data** and idle until an attendee is assigned. This decouples the bridge from the org/VDI
(which Heropa does not tie together) and removes the "bridge must be pre-provisioned before the VDI
runs" ordering dependency.

Companion to [`BRIDGE-PROVISIONING.md`](./BRIDGE-PROVISIONING.md).

---

## 1. Model shift

**Today:** something must inject the org identity into the bridge `.env` and `up` the stack *before*
the attendee runs the VDI bootstrap (which reads `config.js` from an already-running bridge).

**Proposed:** the bridge boots **bare/idle** (golden image: Docker + bundle + fixed images, blank
`.env`, stack down). A small **Launcher API** runs on the bridge. The attendee's `bootstrap.ps1`
calls it with the org identity (which the platform injects into the bootstrap), the launcher writes
`.env` + brings the stack up, the VDI polls until healthy, then continues. The **attendee's action is
the single moment org + VDI + bridge are tied together.**

```
Platform  --(-OrgUrl, -AdminUiClientId, -BridgeLauncherSecret placeholders)-->  VDI bootstrap.ps1
VDI bootstrap.ps1  --POST /launch {okta_domain, admin_ui_client_id} + Bearer-->  Bridge Launcher API (10.0.0.5:9090)
Launcher  --> writes .env (4 keys) --> `docker compose up -d` --> adapter :8000 + admin-ui :3001 healthy
VDI bootstrap.ps1  --poll /status (or /.well-known + config.js)--> ready --> continues normal setup
```

---

## 2. The Launcher API

A tiny, single-purpose HTTP service on the bridge. **Dependency-free** (Python stdlib
`http.server`) so nothing extra is baked into the image. Runs as a systemd unit, enabled at boot.

### Endpoints

| Method / path | Auth | Body | Behavior |
|---|---|---|---|
| `GET /healthz` | none | — | Launcher liveness — `200 {"launcher":"ok"}`. Lets the VDI confirm the launcher is up before POSTing. |
| `POST /launch` | `Authorization: Bearer <secret>` | `{"okta_domain":"demo-x.okta.com","admin_ui_client_id":"0oa…"}` | Validate → write the 4 `.env` keys → `docker compose up -d` (force-recreate adapter+admin-ui on re-config). Returns `202 {"status":"launching","okta_domain":…}`. **Idempotent** — re-POST reconfigures + restarts. |
| `GET /status` | `Bearer` | — | Reports container health + readiness: `{"adapter_ready":bool,"admin_ui_ready":bool,"containers":{…},"okta_domain":…}`. VDI polls this. |

### `/launch` logic

1. Check `Authorization: Bearer` == configured secret (else `401`).
2. Validate inputs: `okta_domain` matches `^[a-z0-9-]+\.okta(preview)?\.com$`; `admin_ui_client_id`
   matches `^0oa[a-zA-Z0-9]+$` (else `400`). **Reject anything else** — the launcher must never run
   arbitrary values.
3. Write into the bundle `.env` (bundle dir discovered via `/opt/bridge/okta-mcp-adapter-bundle-*`):
   ```
   OKTA_DOMAIN=<domain>
   OKTA_ISSUER=https://<domain>
   ADMIN_UI_OKTA_ISSUER=https://<domain>
   ADMIN_UI_OKTA_CLIENT_ID=<client_id>
   ```
4. `docker compose -f docker-compose.bundle.yml up -d` (first launch creates all services; on
   re-config it recreates the services whose resolved env changed — force `--force-recreate
   okta-agent-mcp-adapter admin-ui` to guarantee the new org is applied).
5. Return `202` immediately; readiness is observed via `/status`.

### Skeleton (Python stdlib — golden-image safe)

```python
#!/usr/bin/env python3
# /opt/bridge/launcher/bridge-launcher.py  — single-purpose configure+up service
import json, os, re, glob, subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SECRET   = open("/opt/bridge/launcher/secret").read().strip()
BUNDLE   = sorted(glob.glob("/opt/bridge/okta-mcp-adapter-bundle-*"))[-1]
ENV      = os.path.join(BUNDLE, ".env")
COMPOSE  = os.path.join(BUNDLE, "docker-compose.bundle.yml")
DOMAIN_RE = re.compile(r"^[a-z0-9-]+\.okta(preview)?\.com$")
CID_RE    = re.compile(r"^0oa[a-zA-Z0-9]+$")

def set_env(domain, cid):
    lines, keys = [], {
        "OKTA_DOMAIN": domain, "OKTA_ISSUER": f"https://{domain}",
        "ADMIN_UI_OKTA_ISSUER": f"https://{domain}", "ADMIN_UI_OKTA_CLIENT_ID": cid}
    seen = set()
    for ln in open(ENV):
        k = ln.split("=", 1)[0]
        if k in keys: lines.append(f"{k}={keys[k]}\n"); seen.add(k)
        else: lines.append(ln)
    for k in keys:
        if k not in seen: lines.append(f"{k}={keys[k]}\n")
    open(ENV, "w").writelines(lines)

def compose_up():
    subprocess.run(["docker", "compose", "-f", COMPOSE, "up", "-d",
                    "--force-recreate", "okta-agent-mcp-adapter", "admin-ui"],
                   cwd=BUNDLE, check=True)
    # first-launch safety: ensure the rest are up too
    subprocess.run(["docker", "compose", "-f", COMPOSE, "up", "-d"], cwd=BUNDLE, check=True)

def container_health(name):
    out = subprocess.run(["docker", "inspect", "-f",
        "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}", name],
        capture_output=True, text=True)
    return out.stdout.strip() or "absent"

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj): 
        b = json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def _auth(self):
        return self.headers.get("Authorization","") == f"Bearer {SECRET}"
    def do_GET(self):
        if self.path == "/healthz": return self._send(200, {"launcher":"ok"})
        if self.path == "/status":
            if not self._auth(): return self._send(401, {"error":"unauthorized"})
            a = container_health("okta-agent-mcp-adapter"); u = container_health("okta-mcp-admin-ui")
            return self._send(200, {"adapter_ready": a=="healthy", "admin_ui_ready": u=="healthy",
                                    "containers": {"adapter": a, "admin_ui": u}})
        return self._send(404, {"error":"not found"})
    def do_POST(self):
        if self.path != "/launch": return self._send(404, {"error":"not found"})
        if not self._auth(): return self._send(401, {"error":"unauthorized"})
        n = int(self.headers.get("Content-Length","0")); body = json.loads(self.rfile.read(n) or b"{}")
        d, c = body.get("okta_domain",""), body.get("admin_ui_client_id","")
        if not DOMAIN_RE.match(d) or not CID_RE.match(c):
            return self._send(400, {"error":"invalid okta_domain or admin_ui_client_id"})
        try:
            set_env(d, c); compose_up()
            return self._send(202, {"status":"launching","okta_domain":d})
        except Exception as e:
            return self._send(500, {"error": str(e)})

ThreadingHTTPServer(("0.0.0.0", 9090), H).serve_forever()
```

### systemd unit (`/etc/systemd/system/bridge-launcher.service`)

```ini
[Unit]
Description=O4AA bridge launcher API
After=docker.service
Requires=docker.service

[Service]
ExecStart=/usr/bin/python3 /opt/bridge/launcher/bridge-launcher.py
Restart=always
User=root          # needs to write .env + run docker compose

[Install]
WantedBy=multi-user.target
```

---

## 3. Bridge golden-image additions

On top of the current golden image (Ubuntu 24.04, Docker, bundle, fixed images, blank `.env`, stack
down), add:

- `/opt/bridge/launcher/bridge-launcher.py` (above).
- `/opt/bridge/launcher/secret` — the shared bearer secret, `chmod 600 root:root`.
- `bridge-launcher.service` (enabled). Boots with the box, so the launcher is listening before any
  attendee arrives. The **bridge stack stays down** until `/launch` is called.
- Firewall/SG: expose the launcher port (9090) **only to the paired VDI** on the pod-internal
  network — same posture as 8000/3001. Not public.

Net: a fresh bridge boots with **no org data**, the launcher idle-listening, ready to be assigned.

---

## 4. VDI `bootstrap.ps1` additions

New params:
- `-LaunchBridge` (switch) — enable launcher-driven bring-up.
- `-BridgeLauncherPort` (int, default `9090`).
- `-BridgeLauncherSecret` (string) — platform-injected.
- **`-AdminUiClientId` becomes required** when `-LaunchBridge` (we can't read `config.js` before the
  bridge is up — the platform supplies it instead; this also makes the script skip the `config.js`
  read entirely).

New flow, **before** the existing config.js/admin-token steps:

```powershell
if ($LaunchBridge -and $BridgeAddress) {
    $lb = "http://$BridgeAddress`:$BridgeLauncherPort"
    $domain = ([uri]$OrgUrl).Host
    if (-not $AdminUiClientId) { throw "-LaunchBridge requires -AdminUiClientId (platform-injected)." }

    # 1. launcher alive?
    Invoke-RestMethod "$lb/healthz" -TimeoutSec 8 | Out-Null   # throws -> clear "bridge box/launcher down"

    # 2. configure + launch
    $hdr = @{ Authorization = "Bearer $BridgeLauncherSecret" }
    Invoke-RestMethod "$lb/launch" -Method POST -Headers $hdr -ContentType "application/json" `
        -Body (@{ okta_domain = $domain; admin_ui_client_id = $AdminUiClientId } | ConvertTo-Json) -TimeoutSec 20 | Out-Null

    # 3. poll until healthy (adapter + admin-ui), up to ~120s
    $deadline = (Get-Date).AddSeconds(120)
    do {
        Start-Sleep 5
        $st = Invoke-RestMethod "$lb/status" -Headers $hdr -TimeoutSec 8
        Log "bridge status: adapter=$($st.adapter_ready) admin_ui=$($st.admin_ui_ready)"
    } until (($st.adapter_ready -and $st.admin_ui_ready) -or (Get-Date) -gt $deadline)
    if (-not ($st.adapter_ready -and $st.admin_ui_ready)) { throw "bridge did not become healthy in time." }
}
```

Everything after this works unchanged — the bridge is now up and org-configured, and
`-AdminUiClientId` is already known.

---

## 5. Platform placeholders to inject into the bootstrap

The platform already knows all of these from provisioning the attendee's org (the JS servicer emits
per-org ids). Inject them as Mustache placeholders, same pattern as `-OpenAIApiKey` /
`-PersonaPassword`:

| Param | Source |
|---|---|
| `-OrgUrl` | the attendee's org domain (`{{idp.tenantDomain}}`) |
| `-AdminUiClientId` | that org's **`O4AA Adapter Admin UI`** app `client_id` (servicer output) |
| `-BridgeLauncherSecret` | the launcher shared secret (see §6) |
| `-LaunchBridge` | present (switch) for the Heropa flow |

---

## 6. Security

- **Network:** launcher bound to the pod-internal interface; SG allows the port only from the paired
  VDI. HTTP is acceptable pod-internal; optionally serve TLS with the adapter cert.
- **Auth:** `Bearer` secret on every mutating/status call.
- **Secret model (decided: fleet-wide):** a single secret baked into the golden image + injected into
  the bootstrap by the platform. Sensitivity is low (ephemeral lab orgs, fake data) and pod-internal
  networking is the primary control. Future hardening if ever needed: a **per-pod** secret provisioned
  into both the bridge (`/opt/bridge/launcher/secret`) and the VDI bootstrap at pod creation.
- **Transport (decided: plain HTTP, pod-internal):** the pod is closed and holds only fake data, so
  the launcher runs plain HTTP on the internal network. No TLS.
- **Blast radius:** the launcher does *exactly one thing* — write 4 validated `.env` keys and
  `compose up`. No shell, no arbitrary commands, strict input regex. Even with the secret, an attacker
  can only (re)point a bridge at an Okta org that matches the regex.

---

## 7. Failure modes & idempotency

- **Re-run bootstrap:** `/launch` reconfigures + force-recreates adapter/admin-ui — safe, idempotent.
- **Single-org lifecycle (no DB reset needed):** a bridge VM is assigned to exactly ONE org for its
  life, then torn down — it is never re-pointed to a second org. The empty golden-image DB is populated
  with the assigned org's data on the first `/launch` and stays that org's for the pod's lifetime.
  Idempotent re-runs (attendee re-runs bootstrap) target the SAME org, so no reset is ever required.
  *(If a future flow ever re-assigns a live bridge to a different org, add a DB-volume reset to
  `/launch` keyed on a domain change — not needed under the current single-use model.)*
- **Bridge box down / launcher not up:** `GET /healthz` fails → bootstrap throws a clear error at the
  attendee, not a silent dead bridge.
- **Bad org / wrong client id:** adapter fails to go healthy → `/status` never ready → bootstrap times
  out with a clear message.

---

## 8. Work items

**Bridge side (golden image): built + TESTED.** drop-in artifacts in
[`bridge-launcher/`](./bridge-launcher/) (`bridge-launcher.py`, `bridge-launcher.service`,
`install-launcher.sh`, README); installer and service verified on a real bridge, and the golden image
re-snapshotted with the launcher installed, enabled at boot, and the fleet secret baked.
- [x] Launcher service + systemd unit + installer written and syntax-checked.
- [x] `sudo ./install-launcher.sh --secret <FLEET_SECRET>` run on the bridge; service enabled and
      listening on `:9090`.
- [x] Launcher port (9090) firewalled to the paired VDI only.
- [x] Re-snapshot: the golden image now carries the launcher (installed, enabled, fleet secret baked).

**VDI side (`Configure-OpenCodeAgent.ps1`): built + TESTED** (ofcto-workforce-taskvantage `53cab3f`)
- [x] Added `-LaunchBridge`, `-BridgeLauncherPort` (9090), `-BridgeLauncherSecret`,
      `-BridgeLaunchTimeoutSec` (120); `-AdminUiClientId` required when launching; the
      `/healthz` -> `/launch` -> poll-`/status` block runs before the CA fetch; re-embedded and
      parse-verified on the VDI (PS 5.1, 0 errors).
- [x] End-to-end launch verified twice cold: empty-DB `Applied 5 migration(s)` -> all 6 containers
      healthy -> CA fetch succeeds -> toolkit + OpenCode installed.

**Dependency (CA fetch):** this flow relies on the CA-fetch TLS-1.2 fix in
`Configure-OpenCodeAgent.ps1` - `Get-BridgeCa` now pins `SslProtocols.Tls12` (ofcto-workforce-
taskvantage `31b01d7`). Without it the CA fetch against the freshly launched bridge fails and the
toolkit/OpenCode install cannot proceed.

**Platform: still pending.**
- [ ] Expose the `-AdminUiClientId` and `-BridgeLauncherSecret` placeholders in the bootstrap
      snippet: the two `{{TODO-*}}` tokens in `module-1-environment-tour.md`
      (`{{TODO-admin-ui-client-id}}` and `{{TODO-bridge-launcher-secret}}`) must be replaced with the
      real per-org / fleet Mustache tokens before shipping.

**Validation:** the existing VDI validation snippet in `BRIDGE-PROVISIONING.md` still applies; after
`-LaunchBridge` completes, it should show all PASS with a non-empty client id.

---

## 9. Decisions

1. **Secret model — fleet-wide** (baked into the golden image + platform-injected). Per-pod secret is a
   future hardening option, not needed now.
2. **DB on re-assign — no reset.** A bridge is single-org for its lifetime (assigned once, then torn
   down), so the empty golden-image DB simply fills with that org's data on first `/launch`. A reset
   would only be needed if a live bridge were re-pointed to a *different* org — which the current model
   does not do. *(Assumes Heropa never recycles a bridge VM across attendees — always tears down and
   hands out fresh ones.)*
3. **Transport — plain HTTP, pod-internal.** Closed pod, fake data only; no TLS.
