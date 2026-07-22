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
  auto-starts it, so a fresh VM boots clean and idle — it will **not** crash-loop on the blank
  config. It comes up only when provisioning runs `docker compose up` (§3).

---

## 3. Per-attendee provisioning — what must happen on a new bridge VM

The **only** per-attendee work is injecting the paired org's identity and starting the stack.

1. **Confirm the VM booted from the Ubuntu 24.04 golden snapshot** (not a stock AMI).

2. **Inject the paired attendee org's identity into `.env`.** These four keys are the only
   per-attendee values. The org subdomain and its admin-ui client id come from the Okta org the
   provisioning servicer (`TechCampO4AALabServicer`) created for this attendee — the client id is
   that org's **`O4AA Adapter Admin UI`** OIDC app `client_id`.

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
   ```

3. **Bring the stack up:**

   ```bash
   cd "$BUNDLE" && sudo docker compose -f docker-compose.bundle.yml up -d
   ```

   The adapter migrates the empty DB → healthy on `:8000` (HTTPS); admin-ui reaches it over HTTPS
   → healthy → serves `config.js` on `:3001`; the rest come up healthy.

4. **Ordering — this must finish BEFORE the attendee runs the VDI `bootstrap.ps1`.** The VDI
   bootstrap *reads* `config.js` from the bridge to resolve the admin-ui client id; if the bridge
   isn't up/configured, the bootstrap aborts with a "config.js unreachable" error.

### Where the org identity comes from (important)

The **VDI PowerShell script does NOT configure the bridge.** Its `-OrgUrl` parameter feeds the
VDI-local Lab Toolkit config and an admin sign-in against the org to resolve toolkit/AS ids; toward
the bridge it only **reads** (`config.js`, the CA) and writes a local hosts entry. So the bridge's
`OKTA_DOMAIN` + admin-ui client id **must be supplied to the bridge at provision time** — the VDI
will not set them, and `OKTA_DOMAIN` cannot be set via the running admin UI (it is a startup env
var; the adapter refuses to start without it).

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
