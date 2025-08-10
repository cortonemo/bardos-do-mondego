# tools/rename-spaces.ps1
# Rename files/folders under docs/: " " -> "_" and rewrite Markdown links accordingly.
# Usage:
#   .\tools\rename-spaces.ps1         # real run
#   .\tools\rename-spaces.ps1 -DryRun # preview only

param(
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot '..\docs'

if (-not (Test-Path $root)) {
  Write-Error "docs/ not found: $root"
  exit 1
}

# 1) Build rename list (dirs first, deepest first; then files)
$dirs  = Get-ChildItem $root -Recurse -Directory | Where-Object { $_.Name -match ' ' } |
         Sort-Object { $_.FullName.Split('\').Count } -Descending
$files = Get-ChildItem $root -Recurse -File      | Where-Object { $_.Name -match ' ' }

$plan = @()

function New-Rel($abs) {
  return (Resolve-Path -LiteralPath $abs).Path.Substring($root.Length + 1)
}

foreach ($d in $dirs) {
  $newName = $d.Name -replace ' ','_'
  if ($newName -eq $d.Name) { continue }
  $target = Join-Path ($d.PSParentPath -replace '^Microsoft\.PowerShell\.Core\\FileSystem::','') $newName
  $plan += [pscustomobject]@{
    Type = 'dir'
    FromAbs = $d.FullName
    ToAbs   = $target
    FromRel = (New-Rel $d.FullName)
    ToRel   = (Join-Path (Split-Path $d.FullName -Parent | ForEach-Object { New-Rel $_ }) $newName)
  }
}
foreach ($f in $files) {
  $newName = $f.Name -replace ' ','_'
  if ($newName -eq $f.Name) { continue }
  $target = Join-Path ($f.PSParentPath -replace '^Microsoft\.PowerShell\.Core\\FileSystem::','') $newName
  $plan += [pscustomobject]@{
    Type = 'file'
    FromAbs = $f.FullName
    ToAbs   = $target
    FromRel = (New-Rel $f.FullName)
    ToRel   = (Join-Path (Split-Path $f.FullName -Parent | ForEach-Object { New-Rel $_ }) $newName)
  }
}

if ($plan.Count -eq 0) {
  Write-Host "No names with spaces under $root."
  exit 0
}

Write-Host "Planned renames:" -ForegroundColor Cyan
$plan | ForEach-Object { Write-Host "  $($_.Type): $($_.FromRel) -> $($_.ToRel)" }

if ($DryRun) {
  Write-Host "`nDry-run only. No renames performed." -ForegroundColor Yellow
} else {
  # 2) Apply renames (dirs first already ordered)
  foreach ($item in $plan) {
    if (Test-Path -LiteralPath $item.ToAbs) {
      Write-Warning "Target exists, skipping: $($item.ToRel)"
      continue
    }
    Rename-Item -LiteralPath $item.FromAbs -NewName ([IO.Path]::GetFileName($item.ToAbs))
    Write-Host "Renamed: $($item.FromRel) -> $($item.ToRel)"
  }
}

# 3) Rewrite Markdown links to use new names
# Build map from old forward-slash rel to new forward-slash rel for stable matching
$map = @{}
foreach ($p in $plan) {
  $old = ($p.FromRel -replace '\\','/')
  $new = ($p.ToRel   -replace '\\','/')
  $map[$old] = $new
}

# Helper: given a URL, replace any segment that matches renamed paths
function Rewrite-Url($url, $fileDir) {
  # Normalize slashes for matching
  $u = $url -replace '\\','/'

  # Absolute-ish (relative to docs root) if it resolves from root directly
  $candidate = Join-Path $root ($u -replace '/','\')
  $isRootish = Test-Path -LiteralPath $candidate

  # Try exact map hit
  foreach ($k in $map.Keys) {
    # exact file hit
    if ($u -ieq $k) { $u = $map[$k]; break }
    # inside a renamed dir: k is a dir path, match as prefix
    if ($k -match '/$') { continue }
  }

  # Also try prefix replacement for renamed directories
  foreach ($k in $map.Keys) {
    # treat directory keys by appending a trailing slash if it is a dir in plan
    $isDir = (Split-Path $k -Leaf) -ne [IO.Path]::GetFileName($k)
    $kDir = $k
    if ($isDir -and (-not $k.EndsWith('/'))) { $kDir = $k + '' }
  }

  # Simpler, robust approach: replace each path **segment** with underscores version
  $segments = $u.Split('/')
  $segments = $segments | ForEach-Object { $_ -replace ' ','_' }
  $u = [string]::Join('/', $segments)

  # Re-relativize if URL looked rootish and now exists
  if ($isRootish -or (Test-Path (Join-Path $root ($u -replace '/','\')))) {
    $abs = Resolve-Path -LiteralPath (Join-Path $root ($u -replace '/','\')) -ErrorAction SilentlyContinue
    if ($abs) {
      $uriFile = [Uri]$abs.Path
      $uriDir  = [Uri]("$fileDir\")
      $rel     = [Uri]::UnescapeDataString($uriDir.MakeRelativeUri($uriFile).ToString()).Replace('\','/')
      return $rel
    }
  }

  return $u
}

[int]$changed = 0
$mdFiles = Get-ChildItem $root -Recurse -Filter *.md -File
foreach ($f in $mdFiles) {
  $text = Get-Content $f.FullName -Raw
  if ([string]::IsNullOrEmpty($text)) { continue }
  $orig = $text
  $dir  = Split-Path $f.FullName

  # Inline + image links
  $pat = '(\!\[[^\]]*\]|\[[^\]]*\])\(([^)]+)\)'
  foreach ($m in [regex]::Matches($text, $pat)) {
    $prefix = $m.Groups[1].Value
    $url    = $m.Groups[2].Value
    if ($url -match '^(https?://|mailto:|tel:|#)') { continue }
    $newUrl = Rewrite-Url $url $dir
    if ($newUrl -ne $url) {
      $text = $text.Replace($m.Value, "$prefix($newUrl)")
    }
  }

  # Reference-style links: [id]: url
  $patRef = '(^\s*\[[^\]]+\]:\s*)([^#\s]+)'
  $text = [regex]::Replace($text, $patRef, {
    param($m)
    $head = $m.Groups[1].Value
    $url  = $m.Groups[2].Value
    if ($url -match '^(https?://|mailto:|tel:|#)') { return $m.Value }
    $newUrl = Rewrite-Url $url $dir
    if ($newUrl -ne $url) { return "$head$newUrl" }
    return $m.Value
  }, 'Multiline')

  # Angle-bracket autolinks: <url>
  $text = [regex]::Replace($text, '<([^:>\s][^>]*)>', {
    param($m)
    $url = $m.Groups[1].Value
    if ($url -match '^(https?://|mailto:|tel:|#)') { return $m.Value }
    $newUrl = Rewrite-Url $url $dir
    if ($newUrl -ne $url) { return "<$newUrl>" }
    return $m.Value
  })

  if ($text -ne $orig) {
    if ($DryRun) {
      Write-Host "Would rewrite links in: $(Resolve-Path $f.FullName -Relative)"
    } else {
      Set-Content -Path $f.FullName -Value $text -Encoding UTF8
      $changed++
    }
  }
}

Write-Host ""
if ($DryRun) {
  Write-Host "Dry-run complete. Files that would change: $changed" -ForegroundColor Yellow
} else {
  Write-H
