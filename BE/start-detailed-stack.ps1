$ErrorActionPreference = 'Stop'
$workspace = $PSScriptRoot
$project = Split-Path -Parent $workspace
$backend = Join-Path $workspace 'hauiTrash'
$frontend = Join-Path $project 'FE'
$model = Join-Path $project 'Model_AI\ModelFeatNew\Model_AI_Yolo'
$logs = Join-Path $workspace '.integration'
$jar = Join-Path $backend 'target\hauiTrash-0.0.1-SNAPSHOT.jar'
$java = 'C:\Program Files\Microsoft\jdk-21.0.11.10-hotspot\bin\java.exe'
$python = 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$node = (Get-Command node.exe -ErrorAction Stop).Source
foreach ($file in @($jar,$java,$python,(Join-Path $frontend 'serve.mjs'),(Join-Path $model 'trashsmart\models\components-experimental-v1\experimental-release.json'))) {
    if (!(Test-Path -LiteralPath $file)) { throw "Missing required file: $file" }
}
New-Item -ItemType Directory -Path $logs -Force | Out-Null
function StartService([int]$port,[string]$file,[string[]]$arguments,[string]$directory,[string]$name,[string]$expected) {
    $owners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($owners.Count -gt 0) {
        if ($owners.Count -ne 1) { throw "Port $port has multiple owners; inspect before starting." }
        $running = Get-CimInstance Win32_Process -Filter "ProcessId=$($owners[0])"
        if ($running.CommandLine -notmatch $expected) { throw "Port $port belongs to another application; it was not stopped." }
        Write-Output "$name already listening on $port (PID $($owners[0]))."
        return [int]$owners[0]
    }
    $process = Start-Process -FilePath $file -ArgumentList $arguments -WorkingDirectory $directory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs "detailed-$name.log") -RedirectStandardError (Join-Path $logs "detailed-$name-error.log") -PassThru
    Write-Output "$name launched on $port (PID $($process.Id))."
    return [int]$process.Id
}
$runtime = @{}
$result = @(StartService 8000 $python @('-X','utf8','-m','uvicorn','api:app','--host','127.0.0.1','--port','8000','--no-access-log') $model 'legacy-ai' 'uvicorn\s+(api:app|trashsmart\.pipeline\.main:app)')
$runtime.legacyAi = $result[-1]; $result[0..($result.Count-2)] | Write-Output
$result = @(StartService 8080 $java @('-jar',$jar,'--app.admin.bootstrap-enabled=false') $backend 'backend' ([regex]::Escape($jar)))
$runtime.backend = $result[-1]; $result[0..($result.Count-2)] | Write-Output
$env:PORT = '5500'
$result = @(StartService 5500 $node @((Join-Path $frontend 'serve.mjs')) $frontend 'frontend' ([regex]::Escape((Join-Path $frontend 'serve.mjs'))))
$runtime.frontend = $result[-1]; $result[0..($result.Count-2)] | Write-Output
$runtime | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logs 'detailed-runtime.json') -Encoding utf8
Write-Output 'User: http://127.0.0.1:5500/User/index.html'
Write-Output 'Admin: http://127.0.0.1:5500/Admin/login.html'
Write-Output 'Detailed AI shares the usual process: http://127.0.0.1:8000/details/health'
Write-Output 'Service startup is asynchronous; logs are in BE/.integration/detailed-*.log.'
