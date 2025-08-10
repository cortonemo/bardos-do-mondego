param(
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot '..\docs'
if (-not (Test-Path $root)) { Write-Error "docs/ not found: $root"; exit 1 }

function RelPathExisting([string]$abs) {
  # For existing paths only
  $fullRoot = [IO.Path]::GetFullPath($root) + [IO.Path]::DirectorySeparatorChar
  $fullAbs  = [IO.Path]::GetFullPath($abs)
  return ($fullAbs.Substring($fullRoot.Length)) -replace '\\','/'
}
function JoinRel($parentRel, $leaf) {
  $parentRel = ($parentRel -replace '\\','/').TrimEnd('/')
  if ([string]::IsNullOrEmpty($parentRel)) { return ($leaf -replace '\\','/') }
  return "$parentRel/$leaf"
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
  $fromRel = RelPathExisting $d.FullName
  $toRel   = JoinRel (Split-Path $fromRel -Parent) $newName
  $plan += [pscustomobject]@{ Type='dir'; FromAbs=$d.FullName; ToAbs=$toAbs; FromRel=$fromRel; ToRel=$toRel }
}
foreach ($f in $files) {
  $newName = $f.Name -replace ' ','_'
  if ($newName -eq $f.Name) { continue }
  $toAbs = Join-Path $f.Directory.FullName $newName
  $fromRel = RelPathExisting $f.FullName
  $toRel   = JoinRel (Split-Path $fromRel -Parent) $newName
  $plan += [pscustomobject]@{ Type='file'; FromAbs=$f.FullName; ToAbs=$toAbs; FromRel=$fromRel; ToRel=$toRel }
}

if ($plan.Count -eq 0) {
  Write-Host "No names with spaces under $root."
  return
}

Write-Host "Planned renames:" -ForegroundColor Cyan
$plan | ForEach-Object { Write-Host "  $($_.Type): $($_.FromRel) -> $($_.ToRel)" }

if (-not $DryRun) {
  foreach ($p in $plan) {
    if (Test-Path -LiteralPath $p.ToAbs) {
      Write-Warning "Target exists, skipping: $($p.ToRel)"
      continue
    }
    Rename-Item -LiteralPath $p.FromAbs -NewName ([IO.Path]::GetFileName($p.ToAbs))
    Write-Host "Renamed: $($p.FromRel) -> $($p.ToRel)"
  }
}

# Map last-segment changes (for link rewriting)
$segmentMap = @{}
foreach ($p in $plan) {
  $oldSeg = [IO.Path]::GetFileName($p.FromAbs)
  $newSeg = [IO.Path]::GetFileName($p.ToAbs)
  $segmentMap[$oldSeg] = $newSeg
}

function RewriteUrl([string]$url, [string]$fileDir) {
  if ($url -match '^(https?://|mailto:|tel:|#)') { return $url }
  $u = $url -replace '\\','/'
  # segment-level replace: spaces -> _, and apply known renames
  $parts = $u.Split('/')
  for ($i=0; $i -lt $parts.Length; $i++) {
    $seg = $parts[$i]
    if ($segmentMap.ContainsKey($seg)) { $parts[$i] = $segmentMap[$seg] }
    else { $parts[$i] = $seg -replace ' ','_' }
  }
  $u2 = [string]::Join('/', $parts)

  # if path exists under docs/, make it relative to the current file dir
  $candidate = Join-Path $root ($u2 -replace '/','\')
  $abs = Resolve-Path -LiteralPath $candidate -ErrorAction SilentlyContinue
  if ($abs) {
    $uriFile = [Uri]$abs.Path
    $uriDir  = [Uri]("$fileDir\")
    return [Uri]::UnescapeDataString($uriDir.MakeRelativeUri($uriFile).ToString()).Replace('\','/')
  }
  return $u2
}

# 2) Rewrite links in Markdown
$mdFiles = Get-ChildItem $root -Recurse -Filter *.md -File
[int]$rewritten = 0
foreach ($f in $mdFiles) {
  $text = Get-Content $f.FullName -Raw
  if ([string]::IsNullOrEmpty($text)) { continue }
  $orig = $text
  $dir  = Split-Path $f.FullName

  # Inline + image
  $pat = '(\!\[[^\]]*\]|\[[^\]]*\])\(([^)]+)\)'
  foreach ($m in [regex]::Matches($text, $pat)) {
    $prefix = $m.Groups[1].Value
    $url    = $m.Groups[2].Value
    $newUrl = RewriteUrl $url $dir
    if ($newUrl -ne $url) { $text = $text.Replace($m.Value, "$prefix($newUrl)") }
  }

  # Reference-style
  $patRef = '(^\s*\[[^\]]+\]:\s*)([^#\s]+)'
  $text = [regex]::Replace($text, $patRef, {
    param($m)
    $head = $m.Groups[1].Value
    $url  = $m.Groups[2].Value
    $newUrl = RewriteUrl $url (Split-Path $f.FullName)
    if ($newUrl -ne $url) { return "$head$newUrl" }
    return $m.Value
  }, 'Multiline')

  # Angle-bracket autolinks
  $text = [regex]::Replace($text, '<([^:>\s][^>]*)>', {
    param($m)
    $url = $m.Groups[1].Value
    $newUrl = RewriteUrl $url (Split-Path $f.FullName)
    if ($newUrl -ne $url) { return "<$newUrl>" }
    return $m.Value
  })

  if ($text -ne $orig) {
    if ($DryRun) {
      Write-Host "Would rewrite links in: $(RelPathExisting $f.FullName)"
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
