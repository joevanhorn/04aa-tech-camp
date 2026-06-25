# Heropa user-data / cloud-init snippets

Copy these verbatim into the Heropa VM wizard's **user-data** field. Copying from a
terminal/chat mangles them (smart quotes, wrapped lines) — copy from the rendered code
blocks here (use the GitHub "copy" button) instead.

> **Format matters.** The first line decides how the platform runs it:
> - **Linux:** the script **must start with `#!/bin/bash`** on line 1 (no blank/comment above it), or cloud-init ignores it.
> - **Windows:** the script **must be wrapped in `<powershell>…</powershell>`** tags (EC2Launch runs that as PowerShell).
>
> **Run-once:** user-data runs **only on first boot of a fresh instance** — a plain reboot won't re-run it. Re-launch/recreate (or on Windows add `<persist>true</persist>`) to re-fire.

---

## 1. Linux bridge — grant SSH access (current step)

Adds the Claude host's key to `joevanhorn` (idempotent) **and** enables password auth as a
fallback, logging to `/var/log/o4aa-userdata.log`.

```bash
#!/bin/bash
exec > /var/log/o4aa-userdata.log 2>&1
set -x

KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPRsLIhb6atFSqGXvUl9SMicHXwZZiZ6SVbBFscnPg6j claude-host-o4aa'
JH_HOME=$(getent passwd joevanhorn | cut -d: -f6); JH_HOME=${JH_HOME:-/home/joevanhorn}
mkdir -p "$JH_HOME/.ssh"
grep -qF "$KEY" "$JH_HOME/.ssh/authorized_keys" 2>/dev/null || echo "$KEY" >> "$JH_HOME/.ssh/authorized_keys"
chown -R joevanhorn:joevanhorn "$JH_HOME/.ssh"
chmod 700 "$JH_HOME/.ssh"; chmod 600 "$JH_HOME/.ssh/authorized_keys"

# fallback: also allow password auth (so 410aMy331 works over SSH too)
sed -ri 's/^#?\s*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
for f in /etc/ssh/sshd_config.d/*.conf; do [ -e "$f" ] && sed -ri 's/^#?\s*PasswordAuthentication.*/PasswordAuthentication yes/' "$f"; done
systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null || true
```

Verify after boot: `sudo cat /var/log/o4aa-userdata.log` and
`sudo grep claude-host /home/joevanhorn/.ssh/authorized_keys`.

---

## 2. Windows VDI — base + (placeholder) agent/toolkit bootstrap

The existing Heropa timezone line stays; `%TZOFFSET%` is a Heropa template token it
substitutes at launch. The VDI agent/toolkit bootstrap (download + run
`Configure-OpenCodeAgent.ps1 -UseBridgeDiscovery -InstallToolkit …`) is **pending two
decisions** (see below) before it's filled in.

```powershell
<powershell>
# --- Heropa default: timezone from the injected offset (keep) ---
Set-Timezone -Id (Get-TimeZone -ListAvailable | Select-Object DisplayName,Id | Select-String -Pattern '\(UTC\%TZOFFSET%\).*Id=(.+)}$').Matches.Groups[1].Value

# --- VDI agent + Lab Toolkit bootstrap (TO BE FILLED) ---
# $dir = "C:\o4aa-setup"; New-Item -ItemType Directory -Force -Path $dir | Out-Null
# (download Configure-OpenCodeAgent.ps1 + Lab-Toolkit.ps1 + Discover-Bridge.ps1 + lab CA from S3)
# & "$dir\Configure-OpenCodeAgent.ps1" -UseBridgeDiscovery -InstallToolkit `
#     -OrgUrl "https://<org>.okta.com" -ToolkitClientId "<id>" -CrmAsId "<id>" `
#     -AdapterHost "adapter.taskvantage.lab" -PersonaPassword "<pw>" -OpenAIApiKey "<key>"
</powershell>
```

**Pending before the Windows bootstrap is finalized:**
1. **Do Heropa VMs get an AWS IAM instance role?** If yes → bridge **tag-discovery** works
   (`Discover-Bridge.ps1` needs `ec2:DescribeInstances`). If no → **pin the bridge's private IP**
   in the toolkit config / hosts entry instead.
2. **Which org this VDI pairs with** (→ `OrgUrl`, `ToolkitClientId`, `CrmAsId` from
   `provision_lab_org.py` output) and the **bridge private IP** if not using discovery.

Then the setup files get pushed to S3 and the download+run lines above are filled in.

---

## Reference

- Claude-host public key (the one in §1): `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPRsLIhb6atFSqGXvUl9SMicHXwZZiZ6SVbBFscnPg6j claude-host-o4aa`
- Bridge bundle (copy-and-run): `s3://okta-terraform-demo/o4aa-bridge/okta-mcp-adapter-bundle-0.15.14.tar.gz`
