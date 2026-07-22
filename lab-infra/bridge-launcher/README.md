# Bridge Launcher API

Drop-in artifacts for the VDI-triggered bridge bring-up model. Design + rationale:
[`../BRIDGE-LAUNCHER-API-SPEC.md`](../BRIDGE-LAUNCHER-API-SPEC.md).

A bridge VM boots **bare/idle** (blank `.env`, stack down) with this small **Launcher API** running.
When an attendee is assigned, their VDI `bootstrap.ps1` (`-LaunchBridge`) POSTs the org identity to
`/launch`; the launcher writes the four `.env` keys and runs `docker compose up`, and the VDI polls
`/status` until the adapter + admin-ui are healthy.

## Files
| File | Purpose |
|---|---|
| `bridge-launcher.py` | The service - stdlib only, runs as root, serves `/healthz`, `/launch`, `/status`. |
| `bridge-launcher.service` | systemd unit (enabled at boot). |
| `install-launcher.sh` | Installs the above onto a bridge VM and enables the service. |

## Install (bake into the golden image)

On the bridge VM, as root:

```bash
sudo ./install-launcher.sh --secret <FLEET_SECRET>
```

- Use the **same fleet-wide secret** on every bridge; inject that same value into the VDI bootstrap
  as `-BridgeLauncherSecret` (platform placeholder).
- Omit `--secret` to have it generate + print one (handy for a first test).
- Then **re-snapshot** the VM so every attendee bridge boots with the launcher ready.

Expose port **9090** only to the paired VDI (pod-internal), same posture as 8000/3001.

## API

| Method / path | Auth | Body / result |
|---|---|---|
| `GET /healthz` | none | `{"launcher":"ok"}` |
| `POST /launch` | `Authorization: Bearer <secret>` | `{"okta_domain":"demo-x.okta.com","admin_ui_client_id":"0oa..."}` -> `202 {"status":"launching"}` |
| `GET /status` | `Bearer` | `{"phase":"idle|launching|up|error","adapter_ready":bool,"admin_ui_ready":bool,"containers":{...},"okta_domain":...,"error":...}` |

Input is strictly validated (`okta_domain` = `<sub>.okta.com`, `admin_ui_client_id` = `0oa...`); the
service does nothing else - no shell, no arbitrary commands. Idempotent: a repeat `/launch` for the
same org reconfigures + restarts the adapter/admin-ui.

## Quick test

From the paired VDI (or anywhere allowed to reach the launcher):

```bash
SECRET=<fleet-secret>; BRIDGE=10.0.0.5
curl -fsS http://$BRIDGE:9090/healthz

curl -fsS -X POST http://$BRIDGE:9090/launch \
  -H "Authorization: Bearer $SECRET" -H "Content-Type: application/json" \
  -d '{"okta_domain":"demo-xxxx.okta.com","admin_ui_client_id":"0oaXXXXXXXX"}'

# poll until adapter_ready && admin_ui_ready
curl -fsS http://$BRIDGE:9090/status -H "Authorization: Bearer $SECRET"
```

Then confirm end-to-end with the VDI validation snippet in
[`../BRIDGE-PROVISIONING.md`](../BRIDGE-PROVISIONING.md) (adapter well-known 200 + `config.js` with a
non-empty client id).

## On the bridge (troubleshooting)
```bash
systemctl status bridge-launcher
journalctl -u bridge-launcher -n 100 -f
sudo docker ps                       # after /launch: 6 containers, admin-ui healthy
```
