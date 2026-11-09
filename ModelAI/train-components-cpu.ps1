param(
    [Parameter(Mandatory=$true)][string]$Data,
    [ValidateSet('detector','material')][string]$Task='detector',
    [int]$Epochs=5,
    [int]$Batch=2,
    [int]$ImageSize=416,
    [int]$Threads=4,
    [string]$Python='python',
    [string]$Resume=''
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$resolvedData=(Resolve-Path -LiteralPath $Data).Path
if(-not(Test-Path -LiteralPath (Join-Path $resolvedData 'dataset-report.json'))){throw 'Data phải là thư mục đã export, không phải thư mục ảnh thô.'}
$runName=Get-Date -Format 'yyyyMMdd-HHmmss'
$output=Join-Path (Split-Path -Parent $resolvedData) "cpu-$Task-$runName"
if($Resume){
    $resumeResolved=(Resolve-Path -LiteralPath $Resume).Path
    $output=if($Task -eq 'material'){Split-Path -Parent $resumeResolved}else{Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $resumeResolved))}
}
$arguments=@('-u','-m','trashsmart.components',"train-$Task",'--data',$resolvedData,'--output',$output,'--device','cpu','--epochs',"$Epochs",'--batch',"$Batch",'--imgsz',"$ImageSize",'--threads',"$Threads",'--workers','0')
if($Resume){$arguments+=@('--resume',(Resolve-Path -LiteralPath $Resume).Path)}
Write-Host "Training output: $output"
Write-Host 'Chạy pilot ít epoch trước. Ctrl+C để dừng; checkpoint last dùng để tiếp tục.'
& $Python @arguments
if($LASTEXITCODE -ne 0){throw "Training dừng với mã $LASTEXITCODE. Đọc lỗi dữ liệu trước khi chạy lại."}
