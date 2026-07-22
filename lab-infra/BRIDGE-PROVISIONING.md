# O4AA Attendee Bridge — Provisioning & Validation

How a per-attendee **MCP Adapter bridge** (Linux VM) must be built and configured, what the golden
snapshot already contains, and how to confirm a fresh environment is correct. Audience: the lab
platform / Heropa engineering team.

---

## 1. What the bridge is

Each attendee gets a paired **Okta MCP Adapter** ("the bridge") running on its own **Linux VM**,
reachable from the attendee's Windows VDI at the fixed internal IP **`10.0.0.5`**:

| Port | Service | Protocol | Purpose |
|---|---|---|---|
| **8000** | `okta-agent-mcp-adapter` | **HTTPS** | the adapter / gateway (XAA + use-time authorization) |
| **3001** | `okta-mcp-admin-ui` | **HTTP** | admin UI; serves `config.js` (the VDI reads the admin-ui client id from it) |

The stack is the **bundle** distribution (`okta-mcp-adapter-bundle-0.15.14`) unpacked at
**`/opt/bridge/`** — a self-contained set of prebuilt image tarballs (`images/*.tar.gz`), a
`docker-compose.bundle.yml`, an `.env`, and helper scripts (`install.sh`, `configure.sh`,
`status.sh`, `uninstall.sh`). It is **not** a git checkout.

Containers: `okta-agent-mcp-adapter`, `okta-mcp-admin-ui`, `okta-mcp-postgres`, `okta-mcp-redis`,
plus two built-in demo backends `hr-mcp-server` and `deploy-mcp-server` (not part of the
VantageCRM/VantageDesk lab path).

**Base OS must be Ubuntu 24.04.** A stock **Amazon Linux 2023** image was the cause of an early
failure — it has no Docker and none of the bundle, so nothing came up.

---

## 2. What the golden snapshot already contains (do NOT redo)

The snapshot is taken from a configured template VM and already includes:

- **Ubuntu 24.04** + Docker/containerd (enabled at boot).
- The bundle at `/opt/bridge/okta-mcp-adapter-bundle-0.15.14/` with **two fixes baked in** (see §5).
- **Empty DB** — the postgres/redis data volumes are reset. The adapter **auto-migrates on first
  `up`** (static-password mode; psycopg3 runner over `deploy/migrations/sql`), so an empty DB
  rebuilds its own schema. No separate migration step is needed.
- **`.env` fully populated EXCEPT the org identity** — TLS certs, `GATEWAY_BASE_URL`, DB/redis
  credentials, and the encryption key are all present; the Okta fields are **blank**.
- **Stack is DOWN** (containers removed). There is **no** systemd unit / cron / rc.local that
  auto-starts the stack, so a fresh VM boots clean and idle. It will **not** crash-loop on the blank
  config. It comes up only when the Launcher API runs `docker compose up` in response to the VDI's
  `/launch` call (section 3).
- **The Launcher API** - `bridge-launcher.py` plus its systemd unit (`bridge-launcher.service`,
  **enabled at boot**), with the fleet bearer secret baked at `/opt/bridge/launcher/secret`. The
  launcher listens on `:9090` from first boot and idles until the paired VDI calls `POST /launch`,
  which writes the org identity and brings the stack up. See [`bridge-launcher/`](./bridge-launcher/)
  for the drop-in artifacts and [`BRIDGE-LAUNCHER-API-SPEC.md`](./BRIDGE-LAUNCHER-API-SPEC.md) for the
  full spec.

---

## 3. Per-attendee provisioning: the VDI launches the bridge

The per-attendee trigger is the **attendee's own VDI bootstrap**. The bridge boots bare and idle;
the attendee's `bootstrap.ps1 -LaunchBridge` calls the **Launcher API** on the bridge (`POST
/launch`), and the launcher performs the org-identity `.env` write and `docker compose up` on the
bridge's behalf. There is no longer a "provision the bridge before the VDI runs" ordering step; the
attendee's run is the single moment org + VDI + bridge are tied together. Full contract:
[`BRIDGE-LAUNCHER-API-SPEC.md`](./BRIDGE-LAUNCHER-API-SPEC.md).

**Primary path (launcher-driven):**

1. **Confirm the VM booted from the Ubuntu 24.04 golden snapshot** (not a stock AMI) with the
   Launcher API enabled and listening on `:9090` (`curl -s http://localhost:9090/healthz`).
2. **Nothing else on the bridge.** The attendee's VDI bootstrap does the rest: it POSTs
   `{okta_domain, admin_ui_client_id}` with the fleet bearer secret to `POST /launch`; the launcher
   validates the inputs, writes the 4 `.env` keys, runs `docker compose up -d`, and the VDI polls
   `GET /status` until the adapter and admin-ui report healthy. The org subdomain and admin-ui client
   id are platform-injected into the bootstrap (see section 5 of the spec): the subdomain comes from
   the Okta org the provisioning servicer (`TechCampO4AALabServicer`) created for the attendee, and
   the client id is that org's **`O4AA Adapter Admin UI`** OIDC app `client_id`.

**What the launcher does under the hood (also the manual fallback).** If you ever need to configure a
bridge by hand (no VDI, or to reproduce a failure), the launcher's `/launch` is exactly the following
two steps. These four keys are the only per-attendee values.

```bash
BUNDLE=/opt/bridge/okta-mcp-adapter-bundle-0.15.14
ORG=demo-xxxx-yyyy-12345          # attendee org subdomain
ADMIN_UI_CID=0oaXXXXXXXXXXXX       # that org's "O4AA Adapter Admin UI" app client_id
sudo sed -i -E \
  -e "s|^OKTA_DOMAIN=.*|OKTA_DOMAIN=${ORG}.okta.com|" \
  -e "s|^OKTA_ISSUER=.*|OKTA_ISSUER=https://${ORG}.okta.com|" \
  -e "s|^ADMIN_UI_OKTA_ISSUER=.*|ADMIN_UI_OKTA_ISSUER=https://${ORG}.okta.com|" \
  -e "s|^ADMIN_UI_OKTA_CLIENT_ID=.*|ADMIN_UI_OKTA_CLIENT_ID=${ADMIN_UI_CID}|" \
  "$BUNDLE/.env"
cd "$BUNDLE" && sudo docker compose -f docker-compose.bundle.yml up -d
```

The adapter migrates the empty DB to healthy on `:8000` (HTTPS); admin-ui reaches it over HTTPS,
goes healthy, and serves `config.js` on `:3001`; the rest come up healthy.

### How the identity reaches the bridge (important)

Under the launcher model the **VDI supplies the org identity to the bridge**: it POSTs `okta_domain`
+ admin-ui client id to `/launch`, and the launcher writes them into `.env` before bringing the stack
up. (The rest of the VDI bootstrap still only **reads** from the bridge, `config.js` and the CA, and
writes a local hosts entry.) `OKTA_DOMAIN` cannot be set via the running admin UI (it is a startup
env var; the adapter refuses to start without it), which is exactly why the launcher writes it to
`.env` and then runs `compose up`: it is the one component that can set the startup identity on a bare
bridge.

---

## 4. Validation — run on the companion Windows VDI

Confirms the paired bridge is **up** *and* **configured with an org** (a blank/un-provisioned
bridge fails here). Paste into Windows PowerShell on the attendee VDI:

```powershell
# === O4AA bridge validation (run on the attendee VDI) ===
$Bridge = "10.0.0.5"   # paired bridge, fixed IP

# trust the self-signed adapter cert for this check (PS 5.1-safe, re-runnable)
if (-not ([System.Management.Automation.PSTypeName]'TrustAllCertsPolicy').Type) {
  Add-Type @"
using System.Net; using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsPolicy : ICertificatePolicy {
  public bool CheckValidationResult(ServicePoint s, X509Certificate c, WebRequest r, int p) { return true; }
}
"@
}
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ok = $true
function Say($m,$p){ if($p){Write-Host "  [PASS] $m" -ForegroundColor Green}else{Write-Host "  [FAIL] $m" -ForegroundColor Red;$script:ok=$false} }
Write-Host "`nValidating bridge $Bridge ...`n" -ForegroundColor Cyan

# 1. ports open
Say "adapter :8000 reachable"  (Test-NetConnection $Bridge -Port 8000 -WarningAction SilentlyContinue).TcpTestSucceeded
Say "admin-ui :3001 reachable" (Test-NetConnection $Bridge -Port 3001 -WarningAction SilentlyContinue).TcpTestSucceeded

# 2. adapter healthy (HTTPS well-known -> 200)
try { $r = Invoke-WebRequest "https://$Bridge`:8000/.well-known/oauth-protected-resource" -UseBasicParsing -TimeoutSec 8
      Say "adapter well-known responds (HTTP $($r.StatusCode))" ($r.StatusCode -eq 200) }
catch { Say "adapter well-known FAILED: $($_.Exception.Message)" $false }

# 3. bridge is CONFIGURED with an org (config.js has a real client id, not blank)
try {
  $cfg = (Invoke-WebRequest "http://$Bridge`:3001/config.js" -UseBasicParsing -TimeoutSec 8).Content
  $cid = ([regex]::Match($cfg,'VITE_OKTA_CLIENT_ID:\s*"([^"]*)"')).Groups[1].Value
  $iss = ([regex]::Match($cfg,'VITE_OKTA_ISSUER:\s*"([^"]*)"')).Groups[1].Value
  Say "config.js served on :3001" $true
  Say "admin-ui client id injected (org set): '$cid'" ([bool]$cid)
  if ($iss) { Write-Host "  [info] issuer: $iss  (should be THIS attendee's org)" -ForegroundColor DarkGray }
} catch { Say "config.js unreachable (admin-ui down / adapter never started -> likely blank OKTA_DOMAIN)" $false }

Write-Host "`nRESULT: $(if($ok){'ENVIRONMENT OK'}else{'PROBLEMS FOUND'})`n" -ForegroundColor $(if($ok){'Green'}else{'Red'})
```

**Reading it:**
- All **PASS** + non-empty client id + issuer matching the attendee's org → bridge provisioned
  correctly; the attendee's `bootstrap.ps1` will work.
- `config.js unreachable` **or empty client id** → the bridge came up but the org identity was never
  injected (§3 step 2 didn't run) — the exact failure to catch before an attendee sits down.

---

## 5. Fixes baked into the golden image (context / known issues)

Two defects in the stock bundle were fixed on the template before snapshotting. If the bundle is
ever rebuilt upstream, these should be fixed at the source.

### 5.1 `deploy-mcp-server` image missing `requests`
The prebuilt `okta-mcp-deploy-server` (and latently `okta-mcp-hr-server`) images ship **without the
`requests` package**, a transitive dependency of `okta_jwt_verifier`. `deploy-mcp-server` imports it
at module load, so it **crash-looped** (observed 34,917 restarts). Fixed by layering
`pip install requests` onto the image and re-saving it over `images/okta-mcp-deploy-server.tar.gz`
(so a re-run of `install.sh` keeps the fix). `hr-mcp-server` carries the same latent defect but runs
today because its startup path doesn't hit that import — worth fixing upstream too.

### 5.2 admin-ui uses HTTP for its internal upstream when the adapter has TLS on
The adapter serves **HTTPS** on `:8000` (because `ADAPTER_TLS_CERT`/`ADAPTER_TLS_KEY` are set), but
the admin-ui entrypoint defaults `ADMIN_UI_GATEWAY_INTERNAL_URL` to **`http://`** — so its startup
health-gate probes HTTP against the HTTPS listener, never succeeds, nginx never binds `:3001`, and
admin-ui is **permanently unhealthy after any restart**. Fixed by adding to the admin-ui service
`environment:` in `docker-compose.bundle.yml`:

```yaml
      ADMIN_UI_GATEWAY_INTERNAL_URL: ${ADMIN_UI_GATEWAY_INTERNAL_URL:-https://okta-agent-mcp-adapter:8000}
```

The entrypoint's probe already uses `wget --no-check-certificate` and the nginx block already uses
`proxy_ssl_verify off`, so the self-signed cert is handled — the internal URL just needed to be
`https`. **Upstream fix:** the admin-ui entrypoint should derive the internal scheme from whether
the adapter has TLS enabled (as it already does for the browser-facing `GATEWAY_URL`).

---

## 6. Quick reference (on the bridge Linux VM)

```bash
BUNDLE=/opt/bridge/okta-mcp-adapter-bundle-0.15.14
sudo docker ps                                             # 6 containers, admin-ui should be healthy
cd $BUNDLE && ./status.sh                                  # bundle's own health dashboard (--json for machine output)
sudo docker logs okta-agent-mcp-adapter | grep -i migrat   # "Migrations applied successfully" on a fresh DB
sudo grep -E '^OKTA_DOMAIN|^ADMIN_UI_OKTA_CLIENT_ID' $BUNDLE/.env   # org identity present?
```
