param(
    [string]$Python = "python",
    [string]$Additional = "D:\thacsi\DOAN\HAUI-TRASH\data\dataset_new_chai",
    [string]$Checkpoint = "outputs\resnet-yolo-20261021-225037\best.pth",
    [int]$Epochs = 5
)
$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $project
try {
    $dataset = Join-Path $project 'outputs\data-resnet-incremental-chai'
    $manifestPath = Join-Path $dataset 'incremental_manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        & $Python -m trashsmart.training.prepare_incremental --old-dataset outputs/data-resnet --additional $Additional --output $dataset
        if ($LASTEXITCODE -ne 0) { throw 'Preparing replay dataset failed.' }
    } else {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        if ([IO.Path]::GetFullPath($Additional) -ne $manifest.additional_source) {
            throw 'Existing replay dataset uses a different additional source.'
        }
    }
    $runDir = Join-Path $project ('outputs\resnet-chai-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    & $Python -u -m trashsmart.training.train_yolo_crops --dataset $dataset --run-dir $runDir --init-checkpoint $Checkpoint --finetune-epochs $Epochs --learning-rate 0.00001 --batch-size 16
    if ($LASTEXITCODE -ne 0) { throw 'Fine-tuning failed. See the error above.' }
} finally {
    Pop-Location
}
