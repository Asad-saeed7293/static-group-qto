# Builds a complete package that runs on another Windows laptop. Zip contents:
#     START_HERE.txt          instructions (Roman Urdu + English)
#     Static-Group-QTO\       the application + processed results (no .venv - run.bat rebuilds it)
#     DWG\<short-id>\        each project's DXF drawing folder;  DWG\<short-id>-BOQ\  its historical BOQ file
#     DWG\manifest.json       which bundled folder / file belongs to which project
# Short folder names keep every path well under Windows' 260-character limit, so Windows "Extract All" works.
# run.bat (tools\relink_paths.py) points the projects to the bundled Drawings folder on first start.
#   powershell -ExecutionPolicy Bypass -File make_portable_zip.ps1            (with drawings - default)
#   powershell -ExecutionPolicy Bypass -File make_portable_zip.ps1 -NoDrawings
param([switch]$NoDrawings)
$ErrorActionPreference = "Stop"
$app = $PSScriptRoot
$stage = Join-Path $env:TEMP "static_qto_package"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
$dst = Join-Path $stage "Static-Group-QTO"
New-Item -ItemType Directory -Force $dst | Out-Null
robocopy $app $dst /E /NFL /NDL /NJH /NJS /NP /XD .venv __pycache__ .pytest_cache cache .claude /XF *.pyc | Out-Null
Copy-Item (Join-Path $app "START_HERE.txt") $stage
if (-not $NoDrawings) {
  $cfg = Get-Content (Join-Path $app "config\projects.json") -Raw -Encoding UTF8 | ConvertFrom-Json
  $manifest = [ordered]@{}
  foreach ($p in $cfg.projects) {
    if ($p.archived) { continue }
    $entry = [ordered]@{}
    if ($p.source_folder -and (Test-Path -LiteralPath $p.source_folder) -and $p.source_folder -notlike "$app*") {
      Write-Host "Adding drawings for $($p.id)"
      $short = ($p.id -split "-")[0]
      robocopy $p.source_folder (Join-Path $stage "DWG\$short") /E /NFL /NDL /NJH /NJS /NP /XF *.pdf *.jpg *.jpeg *.png *.bak *.dwl *.dwl2 | Out-Null
      $entry["source_folder"] = $short
    }
    if ($p.historical_boq -and (Test-Path -LiteralPath $p.historical_boq)) {
      Write-Host "Adding historical BOQ for $($p.id)"
      $bdir = Join-Path $stage ("DWG\" + ($p.id -split "-")[0] + "-BOQ")
      New-Item -ItemType Directory -Force $bdir | Out-Null
      $name = Split-Path $p.historical_boq -Leaf
      Copy-Item -LiteralPath $p.historical_boq (Join-Path $bdir $name)
      $entry["historical_boq"] = (($p.id -split "-")[0]) + "-BOQ\" + $name
    }
    if ($entry.Count) { $manifest[$p.id] = $entry }
  }
  $manifest | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $stage "DWG\manifest.json")
}
# safety: no path inside the zip may come near the Windows 260-character limit
$long = Get-ChildItem $stage -Recurse -File | ForEach-Object { $_.FullName.Substring($stage.Length + 1) } | Where-Object { $_.Length -gt 190 }
if ($long) { throw "Paths too long for Windows Extract All:`n$($long -join "`n")" }
$max = (Get-ChildItem $stage -Recurse -File | ForEach-Object { $_.FullName.Substring($stage.Length + 1).Length } | Measure-Object -Maximum).Maximum
$zip = Join-Path (Split-Path $app -Parent) ("SG-QTO-Setup" + ($(if ($NoDrawings) { "-no-drawings" } else { "" })) + ".zip")
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -CompressionLevel Optimal
Remove-Item $stage -Recurse -Force
"Created $zip  ($([math]::Round((Get-Item $zip).Length / 1MB, 1)) MB, longest path inside: $max characters)"
