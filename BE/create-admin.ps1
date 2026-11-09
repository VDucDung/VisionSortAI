param(
    [ValidateSet('New','UpdateExisting')]
    [string]$Mode = 'New',
    [string]$Email,
    [string]$Phone
)

$ErrorActionPreference = 'Stop'
$backendDirectory = Join-Path $PSScriptRoot 'hauiTrash'
if (!(Test-Path -LiteralPath (Join-Path $backendDirectory 'mvnw.cmd'))) {
    throw 'Cannot find the backend Maven wrapper.'
}
if (Get-NetTCPConnection -State Listen -LocalPort 8080 -ErrorAction SilentlyContinue) {
    throw 'BE is already running on 8080. Stop it with Ctrl+C, then run this command again.'
}
if ([string]::IsNullOrWhiteSpace($Email)) { $Email = Read-Host 'Admin email' }
$Email = $Email.Trim().ToLowerInvariant()
if ([string]::IsNullOrWhiteSpace($Email)) { throw 'Admin email is required.' }
if ($Mode -eq 'New') {
    if ([string]::IsNullOrWhiteSpace($Phone)) { $Phone = Read-Host 'Unused phone number (starts with 0; 10-11 digits)' }
    $Phone = $Phone.Trim()
    if ($Phone -notmatch '^0\d{9,10}$') { throw 'Phone must start with 0 and contain 10-11 digits.' }
} elseif (![string]::IsNullOrWhiteSpace($Phone)) {
    throw 'UpdateExisting selects by email and preserves the existing phone. Omit -Phone.'
}

$secureAdminPassword = Read-Host 'New admin password (at least 8 characters)' -AsSecureString
$plainAdminPassword = [System.Net.NetworkCredential]::new('', $secureAdminPassword).Password
if ($plainAdminPassword.Length -lt 8 -or [Text.Encoding]::UTF8.GetByteCount($plainAdminPassword) -gt 72) {
    $plainAdminPassword = $null
    $secureAdminPassword.Dispose()
    throw 'Password must have at least 8 characters and at most 72 UTF-8 bytes.'
}
$adminEnvironmentNames = @('ADMIN_EMAIL','ADMIN_PHONE','ADMIN_PASSWORD','ADMIN_UPDATE_EXISTING')
$previousAdminEnvironment = @{}
foreach ($name in $adminEnvironmentNames) { $previousAdminEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
Push-Location -LiteralPath $backendDirectory
try {
    $env:ADMIN_EMAIL = $Email
    $env:ADMIN_PHONE = if ($Mode -eq 'New') { $Phone } else { '' }
    $env:ADMIN_PASSWORD = $plainAdminPassword
    $env:ADMIN_UPDATE_EXISTING = if ($Mode -eq 'UpdateExisting') { 'true' } else { 'false' }
    Write-Host "Provisioning mode: $Mode. Keep this terminal open while using BE."
    if ($Mode -eq 'UpdateExisting') { Write-Host 'Only the account selected by email is updated. Its phone, profile and history are preserved.' }
    & .\mvnw.cmd clean spring-boot:run '-Dspring-boot.run.arguments=--app.admin.bootstrap-enabled=true'
    if ($LASTEXITCODE -ne 0) { throw 'Admin provisioning/startup failed. Read the BE error above; no success has been assumed.' }
} finally {
    Pop-Location
    foreach ($name in $adminEnvironmentNames) { [Environment]::SetEnvironmentVariable($name, $previousAdminEnvironment[$name], 'Process') }
    $plainAdminPassword = $null
    $secureAdminPassword.Dispose()
}
