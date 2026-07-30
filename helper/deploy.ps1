param(
    [string]$PiHost = "RaspberryThiago",
    [string]$PiUser = "thiago",
    [string]$RemotePath = "/home/thiago/cat-feeder",
    [string]$ServiceName = "cat-feeder"
)

$ScriptDir = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $ScriptDir

$credFile = Join-Path $ProjectRoot "credentials.txt"
if (Test-Path $credFile) {
    $creds = Get-Content $credFile
    if ($creds.Count -ge 1 -and $creds[0].Trim()) {
        $PiUser = $creds[0].Trim()
    }
}

$excludeDirs = ".git", "__pycache__", ".venv", "venv", "node_modules", "helper"
$excludeFiles = "*.pyc", "credentials*"

Write-Host "Stopping ${ServiceName} service on ${PiUser}@${PiHost} ..."
ssh "${PiUser}@${PiHost}" "sudo systemctl stop ${ServiceName}"

Write-Host "Deploying to ${PiUser}@${PiHost}:${RemotePath} ..."

if (Get-Command rsync -ErrorAction SilentlyContinue) {
    $rsyncExcludes = ($excludeDirs | ForEach-Object { "--exclude=$_" }) + ($excludeFiles | ForEach-Object { "--exclude=$_" })
    & rsync -avz --delete $rsyncExcludes "$ProjectRoot/" "${PiUser}@${PiHost}:${RemotePath}/"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "rsync failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}
else {
    $tempDir = Join-Path $env:TEMP "cat-feeder-deploy"
    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

    $xdArgs = $excludeDirs | ForEach-Object { "/XD", $_ }
    $xfArgs = $excludeFiles | ForEach-Object { "/XF", $_ }

    & robocopy $ProjectRoot $tempDir /E $xdArgs $xfArgs /NFL /NDL /NJH /NJS
    if ($LASTEXITCODE -ge 8) {
        Write-Error "robocopy failed with exit code $LASTEXITCODE"
        Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
        exit $LASTEXITCODE
    }

    ssh "${PiUser}@${PiHost}" "mkdir -p ${RemotePath}"
    scp -r "$tempDir\*" "${PiUser}@${PiHost}:${RemotePath}/"

    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
}

Write-Host "Installing dependencies and restarting ${ServiceName} ..."
ssh "${PiUser}@${PiHost}" "cd ${RemotePath} && .venv/bin/pip install -r requirements.txt && sudo systemctl restart ${ServiceName}"

Write-Host "Deploy complete."
