#!/usr/bin/env powershell
# Check if _detect_encoding is in the production file

$remote_file = '/opt/meddatabridge/app/services/file_poller.py'
$cmd = "grep -c '_detect_encoding' $remote_file && echo 'Method found' || echo 'NOT FOUND'"

Write-Host "[CHECK] Verifying _detect_encoding method is deployed..." -ForegroundColor Cyan
plink cpage@qualifinterop.cpage.cloud -batch -p 22 $cmd
