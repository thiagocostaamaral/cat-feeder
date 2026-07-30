param(
    [string]$PiHost = "RaspberryThiago",
    [string]$PiUser = "thiago",
    [string]$RemotePath = "/home/thiago/cat-feeder",
    [string]$LocalPath = $null
)

$ScriptDir = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $ScriptDir

if ([string]::IsNullOrEmpty($LocalPath)) {
    $LocalPath = $ProjectRoot
}

$credFile = Join-Path $ProjectRoot "credentials.txt"
if (Test-Path $credFile) {
    $creds = Get-Content $credFile
    if ($creds.Count -ge 1 -and $creds[0].Trim()) {
        $PiUser = $creds[0].Trim()
    }
}

$excludeDirs = ".git", "__pycache__", ".venv", "venv", "node_modules"
$excludeFiles = "*.pyc", "credentials*"

New-Item -ItemType Directory -Path $LocalPath -Force | Out-Null

Write-Host "Retrieving from ${PiUser}@${PiHost}:${RemotePath} to ${LocalPath} ..."

if (Get-Command rsync -ErrorAction SilentlyContinue) {
    $rsyncExcludes = ($excludeDirs | ForEach-Object { "--exclude=$_" }) + ($excludeFiles | ForEach-Object { "--exclude=$_" })
    & rsync -avz $rsyncExcludes "${PiUser}@${PiHost}:${RemotePath}/" "$LocalPath/"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "rsync failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}
else {
    scp -r "${PiUser}@${PiHost}:${RemotePath}/*" "$LocalPath/"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "scp failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

Write-Host "Retrieve complete. Files saved to ${LocalPath}"
