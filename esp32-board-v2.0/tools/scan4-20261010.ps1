$ErrorActionPreference = "Continue"
$proj = "c4799361d2dd4e09bdd31ddc8a57a1ba"
$out = "C:\Code\epdf-hardware\esp32-board-v2.0\work\scan-20261010"
New-Item -ItemType Directory -Force -Path $out | Out-Null
& easyeda pcb list --include-pads --include-bbox --project $proj 2>&1 |
  Out-File -FilePath (Join-Path $out "pcb-list-pads.log") -Encoding utf8
Write-Output "pcb-list-pads done"
