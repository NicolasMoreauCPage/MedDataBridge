# Update Deploiement package with Python 3.8 fixes
$ErrorActionPreference = "Stop"

Write-Host "Updating Deploiement/app/ with fixed Python 3.8 code..." -ForegroundColor Cyan

# Copy fixed app files to Deploiement
$appDirs = @("services", "routers", "runtime")
foreach ($dir in $appDirs) {
    $sourcePath = "app\$dir"
    $destPath = "Deploiement\app\$dir"
    
    if (Test-Path $sourcePath) {
        Write-Host "Copying $sourcePath to $destPath..."
        Copy-Item -Path "$sourcePath\*.py" -Destination $destPath -Recurse -Force
    }
}

# Also copy app root .py files
Copy-Item -Path "app\*.py" -Destination "Deploiement\app\" -Force
Copy-Item -Path "app\runners.py" -Destination "Deploiement\app\" -Force -ErrorAction SilentlyContinue

Write-Host "✅ Deploiement/app/ updated with Python 3.8 fixes" -ForegroundColor Green
