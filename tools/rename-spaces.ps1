param(
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot '..\docs'
if (-not (Test-Path $root)) { Write-Error "docs/ not found: $root"; exit 1 }

function RelPath([string]$abs) {
  ((Resolve-Path -LiteralPath $abs).Path.Substring($root.Length + 1)) -replace '\\','/'
}

# 1) Plan renames: directories (deepest first), then files
$dirs  = Get-ChildItem $root -Recurse -Directory | Where-Object { $_.Name -match ' ' } |
         Sort-Object { $_.FullName.Split('\').Count } -Descending
$files = Get-ChildItem $root -Recurse -File      | Where-Object { $_.Name -match ' ' }

$plan = @()
foreach ($d in $dirs) {
  $newName = $d.Name -replace ' ','_'
  if ($newName -eq $d.Name) { continue }
  $toAbs = Join-Path $d.Parent.FullName $newName
  $plan += [pscustomobject]@{
    Type   = 'dir'
    FromAbs= $d.FullName
    ToAbs  = $toAbs
    FromRel= RelPath $d.FullName
    ToRel  = RelPath $toAbs
  }
}
foreach ($f in $files) {
  $newName = $f.Name -replace ' ','_'
  if ($newName -eq $f.Name) { continue }
  $toAbs = Join-Path $f.Directory.FullName $newName
  $plan += [pscustomobject]@{
    Type   = 'file'
    FromAbs= $f.FullName
    ToAbs  = $toAbs
    FromRel= RelPath $f.FullName
    ToRel  = RelPath $toAbs
  }
}

if ($plan.Count -eq 0) {
  Write-Host "No names with spaces under $($root)."
} else {
  Write-Host "Planned renames:" -ForegroundColor Cyan
  $plan | ForEach-Object { Write-Host "  $($_.Type): $($_.FromRel) -> $($_.ToRel)" }
}

if (-not $DryRun -and $plan.Count -gt 0) {
  foreach ($p in $plan) {
    if (Test-Path -LiteralPath $p.ToAbs) {
      Write-Warning "Target exists, skipping: $($p.ToRel)"
      continue
    }
    Rename-Item -LiteralPath $p.FromAbs -NewName ([IO.Path]::GetFileName($p.ToAbs))
    Write-Host "Renamed: $($p.FromRel) -> $($p.ToRel)"
  }
}

# Build fast lookup maps for link rewriting (old segment -> new segment)
# We only need segment-level replacement: "notable figures" -> "notable_figures"
$segmentMap = @{}
foreach ($p in $plan) {
  # map only the last segment (file or folder name)
  $oldSeg = [IO.Path]::GetFileName($p.FromAbs)
  $newSeg = [IO.Path]::GetFileName($p.ToAbs)
  $segmentMap[$oldSeg] = $newSeg
}

function RewriteUrl([string]$url, [string]$fileDir) {
  if ($url -match '^(https?://|mailto:|tel:|#)') { return $url }

  # normalize slashes
  $u = $url -replace '\\','/'

  # replace spaces -> underscores in each segment (and apply known segment renames)
  $parts = $u.Split('/')
  for ($i=0; $i -lt $parts.Length; $i++) {
    $seg = $parts[$i]
    if ($segmentMap.ContainsKey($seg)) {
      $parts[$i] = $segmentMap[$seg]
    } else {
      $parts[$i] = $seg -replace ' ','_'
    }
  }
  $u2 = [string]::Join('/', $parts)

  # if it looks root-ish and exists, re-relativize from current file
  $candidate = Join-Path $root ($u2 -replace '/','\')
  $abs = Resolve-Path -LiteralPath $candidate -ErrorAction SilentlyContinue
  if ($abs) {
    $uriFile = [Uri]$abs.Path
    $uriDir  = [Uri]("$fileDir\")
    return [Uri]::UnescapeDataString($uriDir.MakeRelativeUri($uriFile).ToString()).Replace('\','/')
  }

  return $u2
}

# 2) Rewrite links in all Markdown files
$mdFiles = Get-ChildItem $root -Recurse -Filter *.md -File
[int]$rewritten = 0

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
    $newUrl = RewriteUrl $url $dir
    if ($newUrl -ne $url) {
      $text = $text.Replace($m.Value, "$prefix($newUrl)")
    }
  }

  # Reference-style: [id]: url
  $patRef = '(^\s*\[[^\]]+\]:\s*)([^#\s]+)'
  $text = [regex]::Replace($text, $patRef, {
    param($m)
    $head = $m.Groups[1].Value
    $url  = $m.Groups[2].Value
    $newUrl = RewriteUrl $url (Split-Path $f.FullName)
    if ($newUrl -ne $url) { return "$head$newUrl" }
    return $m.Value
  }, 'Multiline')

  # Angle-bracket autolinks: <url>
  $text = [regex]::Replace($text, '<([^:>\s][^>]*)>', {
    param($m)
    $url = $m.Groups[1].Value
    $newUrl = RewriteUrl $url (Split-Path $f.FullName)
    if ($newUrl -ne $url) { return "<$newUrl>" }
    return $m.Value
  })

  if ($text -ne $orig) {
    if ($DryRun) {
      Write-Host "Would rewrite links in: $(RelPath $f.FullName)"
    } else {
      [System.IO.File]::WriteAllText($f.FullName, [string]$text, [System.Text.Encoding]::UTF8)
      $rewritten++
    }
  }
}

if ($DryRun) {
  Write-Host "`nDry-run complete. Files that would change: $rewritten" -ForegroundColor Yellow
} else {
  Write-Host "`nRenames done: $($plan.Count). Links rewritten in: $rewritten file(s)." -ForegroundColor Green
}
