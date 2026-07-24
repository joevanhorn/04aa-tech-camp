<#
  setup-crm-resource.ps1 - O4AA Lab Module 2 helper (the toolkit's Action 7).

  After the attendee registers their agent ("TaskVantage Sales Agent") in Module 2.3-2.7, this
  wires their VantageCRM access end-to-end: it mints an admin token via the no-browser brokered
  flow against the okta-mcp-admin-ui client (NOMFA-mapped, so no second factor), resolves the
  agent by name + vantage-crm-as by audience, then creates the agent's INCLUDE_ONLY managed
  connection in Okta and the CRM resource in the MCP adapter. Idempotent - safe to re-run (also
  the fix if the adapter is restarted). A pure-PowerShell port of wire_adapter_resource.py.

  Config: toolkit.config.json beside this file (org_url, adapter_url, crm_as_id, admin_ui_client_id,
  agent_name, mcp_host). Prompts for the attendee's Okta admin login + password.
#>
[CmdletBinding()]
param(
  [string]$AdminLogin,                 # Okta admin login (prompted if omitted)
  [securestring]$AdminPassword,        # admin password (prompted securely if omitted)
  [string]$ConfigPath
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Web
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ConfigPath) { $ConfigPath = Join-Path $Here "toolkit.config.json" }
$Cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json

$AgentName = if ($Cfg.agent_name) { $Cfg.agent_name } else { "TaskVantage Sales Agent" }
$McpHost   = if ($Cfg.mcp_host)   { $Cfg.mcp_host }   else { "mcp-crm.taskvantage.oktademo.app" }
$Audience  = "api://vantage-crm"
$McpUrl    = "https://$McpHost/mcp"
$Scopes    = @("crm.accounts.read","crm.accounts.write","crm.contacts.read",
               "crm.opportunities.read","crm.opportunities.write")
$AdminScopes = "openid okta.aiAgents.manage okta.aiAgents.read okta.apps.read"

if (-not $Cfg.admin_ui_client_id) { throw "toolkit.config.json has no admin_ui_client_id - re-run the VDI setup (it resolves it from the org)." }

# --- PKCE + HTTP helpers (same proven engine as Lab-Toolkit.ps1) -----------
function B64Url([byte[]]$b) { [Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_') }
function New-Verifier { $b = New-Object byte[] 48; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); B64Url $b }
function Get-Challenge([string]$v) { $sha=[Security.Cryptography.SHA256]::Create(); B64Url ($sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($v))) }
function FromJson($t){ if($t){try{$t|ConvertFrom-Json}catch{$t}}else{$null} }

function Invoke-Web {
  param([string]$Method,[string]$Url,[string]$Body,[string]$ContentType,
        [hashtable]$Headers,[System.Net.CookieContainer]$Jar,[switch]$NoRedirect)
  $r = [System.Net.HttpWebRequest]::Create($Url)
  $r.Method = $Method; $r.AllowAutoRedirect = -not $NoRedirect
  if ($Jar) { $r.CookieContainer = $Jar }
  $r.Accept = "application/json"
  if ($Headers) { foreach ($k in $Headers.Keys) {
    if ($k -eq "Accept") { $r.Accept = $Headers[$k] }
    elseif ($k -eq "Content-Type") { $r.ContentType = $Headers[$k] }
    else { $r.Headers[$k] = $Headers[$k] }
  } }
  if ($Body) { $r.ContentType = $ContentType; $bytes=[Text.Encoding]::UTF8.GetBytes($Body)
               $r.ContentLength=$bytes.Length; $s=$r.GetRequestStream(); $s.Write($bytes,0,$bytes.Length); $s.Close() }
  try {
    $resp = $r.GetResponse(); $loc=$resp.Headers["Location"]; $code=[int]$resp.StatusCode
    $sr=New-Object IO.StreamReader($resp.GetResponseStream()); $txt=$sr.ReadToEnd(); $sr.Close(); $resp.Close()
    return @{ status=$code; body=$txt; location=$loc }
  } catch [System.Net.WebException] {
    $resp=$_.Exception.Response
    if (-not $resp) { return @{ status=-1; body=$_.Exception.Message; location=$null } }
    $loc=$resp.Headers["Location"]; $code=[int]$resp.StatusCode
    $sr=New-Object IO.StreamReader($resp.GetResponseStream()); $txt=$sr.ReadToEnd(); $sr.Close()
    return @{ status=$code; body=$txt; location=$loc }
  }
}

# JSON call with a Bearer token; returns @{status; body=<parsed>}
function Invoke-Api {
  param([string]$Method,[string]$Url,[string]$Token,$BodyObj)
  $body = if ($null -ne $BodyObj) { $BodyObj | ConvertTo-Json -Depth 8 } else { $null }
  $h = @{ Authorization = "Bearer $Token" }
  $r = Invoke-Web $Method $Url $body $(if($body){"application/json"}) $h
  return @{ status=$r.status; body=(FromJson $r.body) }
}

function Get-OktaSession([string]$login,$password,[System.Net.CookieContainer]$jar) {
  $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
             [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))
  $r = Invoke-Web POST "$($Cfg.org_url)/api/v1/authn" (@{username=$login;password=$plain}|ConvertTo-Json) "application/json" $null $jar
  $d = FromJson $r.body
  if ($d.status -ne "SUCCESS" -or -not $d.sessionToken) {
    throw "admin authn returned '$($d.status)'. The admin must be on the lab NOMFA policy (okta-mcp-admin-ui is mapped to it) so the no-browser flow isn't MFA-challenged."
  }
  $u = "$($Cfg.org_url)/login/sessionCookieRedirect?token=$([uri]::EscapeDataString($d.sessionToken))&redirectUrl=$([uri]::EscapeDataString("$($Cfg.org_url)/app/UserHome"))"
  Invoke-Web GET $u $null $null $null $jar -NoRedirect | Out-Null
}

function Follow-Authorize([string]$authorizeUrl,[string]$redirectUri,[System.Net.CookieContainer]$jar) {
  $url=$authorizeUrl
  for ($i=0; $i -lt 12; $i++) {
    $r = Invoke-Web GET $url $null $null $null $jar -NoRedirect
    if (-not $r.location) { throw "authorize stopped at HTTP $($r.status) with no redirect (MFA/consent?). $($r.body.Substring(0,[Math]::Min(180,$r.body.Length)))" }
    $loc=$r.location; if ($loc.StartsWith("/")) { $loc=([uri]$url).GetLeftPart([UriPartial]::Authority)+$loc }
    if ($loc.StartsWith($redirectUri)) {
      $q=[System.Web.HttpUtility]::ParseQueryString(([uri]$loc).Query)
      if ($q["error"]) { throw "authorize error: $($q['error']) $($q['error_description'])" }
      return $q["code"]
    }
    $url=$loc
  }
  throw "authorize did not reach the callback after 12 hops"
}

function Get-AdminToken([string]$login,$password) {
  # Brokered no-browser auth-code/PKCE against the ORG AS with the okta-mcp-admin-ui client.
  # The resulting org-API access token carries okta.aiAgents.manage + okta.apps.read - it is both
  # the Okta API token (managed-connection create) AND the adapter admin token (issuer = the org).
  $jar = New-Object System.Net.CookieContainer
  Get-OktaSession $login $password $jar
  $v=New-Verifier; $c=Get-Challenge $v; $state=[Guid]::NewGuid().ToString("N")
  $redir="http://localhost:3001/callback"
  $auth="$($Cfg.org_url)/oauth2/v1/authorize?response_type=code&client_id=$($Cfg.admin_ui_client_id)&redirect_uri=$([uri]::EscapeDataString($redir))&scope=$([uri]::EscapeDataString($AdminScopes))&state=$state&code_challenge=$c&code_challenge_method=S256"
  $code=Follow-Authorize $auth $redir $jar
  $tok=FromJson (Invoke-Web POST "$($Cfg.org_url)/oauth2/v1/token" "grant_type=authorization_code&code=$code&redirect_uri=$([uri]::EscapeDataString($redir))&client_id=$($Cfg.admin_ui_client_id)&code_verifier=$v" "application/x-www-form-urlencoded" $null $null).body
  if (-not $tok.access_token) { throw "admin token exchange failed: $($tok | ConvertTo-Json -Compress)" }
  return $tok.access_token
}

# --- wire sequence (port of wire_adapter_resource.py) ----------------------
function Resolve-AgentId([string]$tok) {
  $r = Invoke-Api GET "$($Cfg.org_url)/workload-principals/api/v1/ai-agents?limit=200" $tok $null
  $data = if ($r.body.data) { $r.body.data } else { $r.body }
  foreach ($a in $data) { if ($a.profile.name -eq $AgentName -or $a.name -eq $AgentName) { return $a.id } }
  return $null
}

function Get-OrgId([string]$tok) {
  # Primary: the admin-ui app's own record carries an ORN embedding the org id
  # (orn:okta:idp:<orgId>:apps:...) and reading it needs only okta.apps.read,
  # which this token always has. No dependence on any pre-existing agent state.
  $app = Invoke-Api GET "$($Cfg.org_url)/api/v1/apps/$($Cfg.admin_ui_client_id)" $tok $null
  if ($app.status -eq 200 -and $app.body.orn -match 'orn:okta:idp:([^:]+):') { return $Matches[1] }
  # Secondary: /api/v1/org - needs okta.orgs.read, which the admin-ui client is
  # typically NOT granted; check the status instead of trusting the body.
  $r = Invoke-Api GET "$($Cfg.org_url)/api/v1/org" $tok $null
  if ($r.status -eq 200 -and $r.body.id) { return $r.body.id }
  # Fallback: lift the org id from any existing agent connection's ORN
  # (orn:okta:idp:<orgId>:authorization_servers:<asId>). The pre-provisioned
  # example agent always carries a CRM connection, and listing agents and
  # connections only needs okta.aiAgents.read, which this token has.
  $ag = Invoke-Api GET "$($Cfg.org_url)/workload-principals/api/v1/ai-agents?limit=200" $tok $null
  $agents = if ($ag.body.data) { $ag.body.data } else { $ag.body }
  foreach ($a in @($agents)) {
    $cr = Invoke-Api GET "$($Cfg.org_url)/workload-principals/api/v1/ai-agents/$($a.id)/connections" $tok $null
    foreach ($conn in @($cr.body.data)) {
      if ($conn.authorizationServer.orn -match 'orn:okta:idp:([^:]+):') { return $Matches[1] }
    }
  }
  throw "could not resolve the org id: apps lookup returned $($app.status), /api/v1/org returned $($r.status), and no existing agent connection carries an ORN to derive it from"
}

function Ensure-ManagedConnection([string]$tok,[string]$aid) {
  $url="$($Cfg.org_url)/workload-principals/api/v1/ai-agents/$aid/connections"
  $r = Invoke-Api GET $url $tok $null
  foreach ($conn in @($r.body.data)) { if ($conn.resourceIndicator -eq $Audience) { Write-Host "      Okta managed connection for $Audience already exists ($($conn.id))"; return } }
  $orgId = Get-OrgId $tok
  $orn = "orn:okta:idp:${orgId}:authorization_servers:$($Cfg.crm_as_id)"
  $c = Invoke-Api POST $url $tok @{
    connectionType="IDENTITY_ASSERTION_CUSTOM_AS"; authorizationServer=@{orn=$orn}
    resourceIndicator=$Audience; scopeCondition="INCLUDE_ONLY"; scopes=$Scopes }
  if ($c.status -notin 200,201 -or -not $c.body.id) { throw "create Okta managed connection failed ($($c.status)): $($c.body | ConvertTo-Json -Compress)" }
  Write-Host "      created Okta managed connection $($c.body.id) (INCLUDE_ONLY, $($Scopes.Count) scopes)"
}

function Get-AdapterSlug([string]$tok,[string]$aid) {
  $r = Invoke-Api GET "$($Cfg.adapter_url)/api/admin/agents" $tok $null
  $agents = if ($r.body -is [array]) { $r.body } elseif ($r.body.agents) { $r.body.agents } else { $r.body.data }
  foreach ($a in @($agents)) { if ($a.okta_ai_agent_id -eq $aid -or $a.principal_id -eq $aid) { return $a.agent_id } }
  return $null
}

function Find-Resource([string]$tok,[string]$slug) {
  $r = Invoke-Api GET "$($Cfg.adapter_url)/api/admin/resources" $tok $null
  $list = if ($r.body.resources) { $r.body.resources } else { $r.body }
  $asl = $Cfg.crm_as_id.ToLower()
  foreach ($res in @($list)) {
    $nameL = ("$($res.name)").ToLower()
    $asMatch = ($res.resource_id -eq $Cfg.crm_as_id -or $nameL -eq $asl -or $nameL.StartsWith("$asl-") -or $res.config.resource_indicator -eq $Audience)
    if ($asMatch -and $res.agent_id -eq $slug) { return $res }
  }
  return $null
}

Write-Host "`n== Set up your CRM resource (Lab 2) ==" -ForegroundColor Cyan
if (-not $AdminLogin)   { $AdminLogin = Read-Host "Your Okta admin login (e.g. you@company.com)" }
if (-not $AdminPassword){ $AdminPassword = Read-Host "Okta admin password" -AsSecureString }

Write-Host "Signing in as $AdminLogin and minting an admin token (no-browser) ..." -ForegroundColor DarkGray
$tok = Get-AdminToken $AdminLogin $AdminPassword

Write-Host "Resolving '$AgentName' + $Audience in $($Cfg.org_url) ..."
$aid = Resolve-AgentId $tok
if (-not $aid) { throw "No AI agent named '$AgentName' in your org - register it first (Module 2.3)." }
Write-Host "  agent id       = $aid"
Write-Host "  vantage-crm-as = $($Cfg.crm_as_id)"

Write-Host "[0] ensuring Okta managed connection for $Audience ..."
Ensure-ManagedConnection $tok $aid

Write-Host "[1/5] importing agent into the adapter ..."
$imp = Invoke-Api POST "$($Cfg.adapter_url)/api/admin/okta/agents/$aid/import" $tok @{}
if ($imp.body.error -eq "insufficient_scopes") { throw "admin token lacks Okta AI-Agent scopes - the okta-mcp-admin-ui app must grant okta.aiAgents.manage." }
$slug = Get-AdapterSlug $tok $aid
if (-not $slug) { throw "agent not found in adapter after import - check the agent / admin token." }
Write-Host "      adapter agent id = $slug"

Write-Host "[2/5] marking agent DCR-selectable ..."
Invoke-Api PUT "$($Cfg.adapter_url)/api/admin/agents/$slug/dcr-selectable" $tok @{dcr_selectable=$true} | Out-Null

Write-Host "[3/5] syncing managed connections ..."
Invoke-Api POST "$($Cfg.adapter_url)/api/admin/okta/agents/$aid/sync" $tok @{} | Out-Null
Invoke-Api POST "$($Cfg.adapter_url)/api/admin/connections/sync" $tok @{} | Out-Null

Write-Host "[4/5] ensuring resource -> $McpUrl ..."
$existing = Find-Resource $tok $slug
if (-not $existing) {
  Start-Sleep -Seconds 2
  Invoke-Api POST "$($Cfg.adapter_url)/api/admin/connections/sync" $tok @{} | Out-Null
  $existing = Find-Resource $tok $slug
}
if ($existing) {
  $name = $existing.name
  $cur = if ($existing.url) { $existing.url } else { $existing.mcp_url }
  if ($cur -ne $McpUrl -or -not $existing.enabled) {
    Write-Host "      updating existing resource '$name' (url/enabled)"
    Invoke-Api PUT "$($Cfg.adapter_url)/api/admin/resources/$name" $tok @{url=$McpUrl; mcp_url=$McpUrl; enabled=$true} | Out-Null
  } else { Write-Host "      resource '$name' already correct" }
} else {
  Write-Host "      resource not auto-materialized - POST-creating (older adapter path)"
  $c = Invoke-Api POST "$($Cfg.adapter_url)/api/admin/resources" $tok @{
    name="vantage-crm"; resource_id=$Cfg.crm_as_id; url=$McpUrl; mcp_url=$McpUrl; protocol="mcp"
    auth_method="okta-cross-app"; enabled=$true
    config=@{ metadata=@{ resource_indicator=$Audience; authorization_server_orn="authorization_servers:$($Cfg.crm_as_id)" }; resource_indicator=$Audience } }
  if ($c.status -notin 200,201) { throw "create resource failed ($($c.status)): $($c.body | ConvertTo-Json -Compress)" }
  $name = if ($c.body.name) { $c.body.name } else { "vantage-crm" }
}

Write-Host "[5/5] verifying ..."
$r = Invoke-Api GET "$($Cfg.adapter_url)/api/admin/resources/$name" $tok $null
$res = $r.body
$gotUrl = if ($res.url) { $res.url } else { $res.mcp_url }
$ok = ($res.enabled -and $gotUrl -eq $McpUrl -and $res.scope_condition -eq "INCLUDE_ONLY" -and $res.scopes)
Write-Host "      enabled=$($res.enabled) url=$gotUrl scope_condition=$($res.scope_condition) scopes=$($res.scopes -join ',')"
if (-not $ok) {
  Write-Host "WARNING: resource not fully wired. If scope_condition is ALLOW_ALL / scopes empty, confirm the Okta managed connection is INCLUDE_ONLY with granular scopes, then re-run (it re-syncs)." -ForegroundColor Yellow
  exit 1
}
Write-Host "OK: '$name' wired -> $McpUrl (audience $Audience, $($res.scopes.Count) scopes)." -ForegroundColor Green

# Point OpenCode at the agent under its REAL adapter slug (ground truth from the import above),
# so X-MCP-Agent matches what the adapter resolves - no guessing the slug at configure time.
$ocPath = if ($Cfg.opencode_config) { $Cfg.opencode_config } else { "C:\opencode-agent\opencode.json" }
if (Test-Path $ocPath) {
  try {
    $oc = Get-Content $ocPath -Raw | ConvertFrom-Json
    if ($oc.mcp.'okta-bridge'.headers.'X-MCP-Agent' -ne $slug) {
      $oc.mcp.'okta-bridge'.headers.'X-MCP-Agent' = $slug
      $oc | ConvertTo-Json -Depth 8 | Set-Content -Path $ocPath -Encoding UTF8
      Write-Host "Updated $ocPath -> X-MCP-Agent: $slug  (restart OpenCode to pick it up)." -ForegroundColor Green
    }
  } catch { Write-Host "Note: could not update opencode.json X-MCP-Agent ($_). Set it to '$slug' manually." -ForegroundColor Yellow }
}
