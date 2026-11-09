param(
    [string]$Python = "python",
    [string]$Source = "D:\thacsi\DOAN\HAUI-TRASH\data\data-yolo",
    [int]$BatchSize = 16,
    [int]$HeadEpochs = 10,
    [int]$FinetuneEpochs = 40,
    [ValidateSet("legacy", "object")]
    [string]$TrainProfile = "legacy"
)
$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $project
try {
    $dataset = Join-Path $project "outputs\data-resnet"
    $manifestPath = Join-Path $dataset "manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        & $Python -m trashsmart.training.prepare_yolo --source $Source --output $dataset --classes glass metal paper plastic
        if ($LASTEXITCODE -ne 0) { throw "Dataset conversion failed." }
    } else {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        if ([IO.Path]::GetFullPath($Source) -ne $manifest.source -or
            ($manifest.classes -join ',') -ne 'glass,metal,paper,plastic') {
            throw "Existing crops belong to a different source or class mapping."
        }
    }
    $runDir = Join-Path $project ("outputs\resnet-yolo-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    & $Python -u -m trashsmart.training.train_yolo_crops --dataset $dataset --run-dir $runDir --batch-size $BatchSize --head-epochs $HeadEpochs --finetune-epochs $FinetuneEpochs --train-profile $TrainProfile
    if ($LASTEXITCODE -ne 0) { throw "ResNet training failed. See the error above." }
} finally {
    Pop-Location
}
