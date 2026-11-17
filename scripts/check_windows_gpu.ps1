# Run from a Python 3.11 CUDA environment (see docs/MODEL_SIZE_PROBE.md).
param(
    [ValidateSet(2, 4)][int]$Size = 2,
    [string]$Views = "runs/hm3d-views",
    [string]$Questions = "data/raw/route-a/open-eqa-v0.json"
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$run = "runs/windows-probe-" + $Size + "b-" + (Get-Date -Format "yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Path $run | Out-Null
nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv | Tee-Object "$run/gpu.csv"
if ($LASTEXITCODE -ne 0) { throw "nvidia-smi failed; check NVIDIA driver" }
python -c "import torch; assert torch.cuda.is_available(), 'Install a CUDA build of PyTorch'; print(torch.__version__, torch.version.cuda)"
if ($LASTEXITCODE -ne 0) { throw "CUDA preflight failed" }

python scripts/openeqa_size_probe.py --backend cuda --size $Size --views $Views --questions $Questions --output "$run/result.json"
if ($LASTEXITCODE -ne 0) { throw "Inference failed; keep the error and gpu.csv" }
Write-Output "Results: $run/result.json"
