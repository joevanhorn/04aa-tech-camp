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

### 1b. Minimal (key only) — if the wizard rejects the fuller script

```bash
#!/bin/bash
mkdir -p /home/joevanhorn/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPRsLIhb6atFSqGXvUl9SMicHXwZZiZ6SVbBFscnPg6j claude-host-o4aa' >> /home/joevanhorn/.ssh/authorized_keys
chown -R joevanhorn:joevanhorn /home/joevanhorn/.ssh
chmod 700 /home/joevanhorn/.ssh; chmod 600 /home/joevanhorn/.ssh/authorized_keys
```

### 1c. cloud-config alternative — if it wants YAML, not a shell script

Some wizards expect cloud-config. First line **must** be `#cloud-config`:

```yaml
#cloud-config
runcmd:
  - mkdir -p /home/joevanhorn/.ssh
  - echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPRsLIhb6atFSqGXvUl9SMicHXwZZiZ6SVbBFscnPg6j claude-host-o4aa' >> /home/joevanhorn/.ssh/authorized_keys
  - chown -R joevanhorn:joevanhorn /home/joevanhorn/.ssh
  - chmod 700 /home/joevanhorn/.ssh
  - chmod 600 /home/joevanhorn/.ssh/authorized_keys
ssh_pwauth: true
```

> If the **VM update itself fails** (not just "key didn't appear"), user-data likely applies only
> at **create/rebuild** — set it, then launch a fresh VM rather than updating a running one.

---

## 2. Windows VDI — agent/toolkit bootstrap

The existing Heropa timezone line stays; `%TZOFFSET%` is a Heropa template token it
substitutes at launch. The VDI setup downloads and runs the **self-contained `bootstrap.ps1`**
(the built `Configure-OpenCodeAgent.ps1`, published to the CDN): it installs OpenCode + the Lab
Toolkit, writes the paired-bridge hosts entries, trusts the lab CA, and drops the desktop
shortcuts. `Lab-Toolkit.ps1` + `setup-crm-resource.ps1` are embedded, so nothing else is
downloaded. This mirrors the command an attendee pastes in Module 1.

```powershell
<powershell>
# --- Heropa default: timezone from the injected offset (keep) ---
Set-Timezone -Id (Get-TimeZone -ListAvailable | Select-Object DisplayName,Id | Select-String -Pattern '\(UTC\%TZOFFSET%\).*Id=(.+)}$').Matches.Groups[1].Value

# --- VDI agent + Lab Toolkit bootstrap ---
Set-ExecutionPolicy -Scope Process Bypass -Force
$b = "$env:TEMP\bootstrap.ps1"
Invoke-RestMethod "https://cdn.demo.okta.com/labs/techcamp-o4aa/bootstrap.ps1" -OutFile $b
Unblock-File $b
& $b -OrgUrl "https://<org>.okta.com" `
     -OpenAIApiKey "<key>" `
     -PersonaPassword "<pw>" `
     -InstallToolkit
</powershell>
```

Notes:
- **No bridge argument is passed** — the bridge is at the fixed private IP `10.0.0.5` (the script's
  `-BridgeAddress` default), so the hosts entries, CA trust, and bridge-GUI shortcut all wire off
  that automatically. (Passing an unresolved `-BridgeAddress` would override the default and skip
  the whole bridge block.)
- **Per-org values** (`<org>`, `<key>`, `<pw>`) are injected by Heropa. The toolkit's per-org ids
  (lab-toolkit client, `vantage-crm-as`) are resolved at runtime by the script's one-time admin
  sign-in — nothing per-org is baked in.

---

## Reference

- Claude-host public key (the one in §1): `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPRsLIhb6atFSqGXvUl9SMicHXwZZiZ6SVbBFscnPg6j claude-host-o4aa`
- Bridge bundle (copy-and-run): `s3://okta-terraform-demo/o4aa-bridge/okta-mcp-adapter-bundle-0.15.14.tar.gz`
