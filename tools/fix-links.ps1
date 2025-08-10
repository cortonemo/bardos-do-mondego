# tools\fix-links.ps1  (v4)
# - (folder/) -> (folder/index.md) even with spaces
# - backslashes -> forward slashes inside link URLs (inline/image/reference/autolink)
# - root-like links (e.g., dm/summary/x.md) become proper relative links from each file
# - skips http(s), mailto, tel, and anchors

$ErrorActionPreference = 'Stop'

$root  = Join-Path $PSScriptRoot '..\docs'
$files = Get-ChildItem $root -Recurse -Filter *.md -File

function Add-IndexMdInline($s) {
  # [text](path/) -> [text](path/index.md), allow spaces
  return ($s -replace '\]\((?!https?://)([^)]+/)\)', '](\1index.md)')
}
function Add-IndexMdRef($s) {
  # [id]: path/  (leading spaces allowed), allow spaces
  return ($s -replace '(^\s*\[[^\]]+\]:\s*)(?!https?://)([^#]+/)\s*$', '${1}${2}index.md')
}
function Add-IndexMdAngles($s) {
  # <path/> -> <path/index.md>
  return ($s -replace '<(?!https?://)([^>#]+/)>', '<\1index.md>')
}

function NormalizeSlashesInLine($s) {
  # inline + image links
  $pat = '(\!\[[^\]]*\]|\[[^\]]*\])\(([^)]+)\)'
  foreach ($m in [regex]::Matches($s, $pat)) {
    $prefix = $m.Groups[1].Value
    $url    = $m.Groups[2].Value -replace '\\','/'
    # optionally encode spaces (MkDocs handles raw spaces, but %20 is safer)
    # $url = $url -replace ' ', '%20'
    $s = $s.Replace($m.Value, "$prefix($url)")
  }
  return $s
}
function NormalizeSlashesInRefs($s) {
  # [id]: path with backslashes
  $pat = '(^\s*\[[^\]]+\]:\s*)([^#\s]+)'
  return ([regex]::Replace($s, $pat, {
    param($m)
    $head = $m.Groups[1].Value
    $url  = $m.Groups[2].Value -replace '\\','/'
    "$head$url"
  }, 'Multiline'))
}
function NormalizeSlashesInAngles($s) {
  # <path\with\backslashes>
  return ($s -replace '<([^:>]+)>', { param($m) "<" + ($m.Groups[1].Value -replace '\\','/') + ">" })
}

function RelativizeRootishLinks($s, $fileDir) {
  # For links that don't start with ./ ../ http # and look like "dm/..." or "images/foo.png",
  # if that target exists under $root, rewrite to the relative path from $fileDir.
  $pat = '(\!\[[^\]]*\]|\[[^\]]*\])\(([^)]+)\)'
  foreach ($m in [regex]::Matches($s, $pat)) {
    $prefix = $m.Groups[1].Value
    $url    = $m.Groups[2].Value

    if ($url -match '^(https?://|mailto:|tel:|#|\.\/|\.\./)') { continue }

    $candidate = Join-Path $root ($url -replace '/','\')
    if (Test-Path $candidate) {
      $rel = Resolve-Path -LiteralPath $candidate | ForEach-Object {
        $uriFile = New-Object System.Uri($_.Path)
        $uriDir  = New-Object System.Uri("$fileDir\")
        [uri]::UnescapeDataString($uriDir.MakeRelativeUri($uriFile).ToString()).Replace('\','/')
      }
      $s = $s.Replace($m.Value, "$prefix($rel)")
    }
  }

  # reference-style
  $patRef = '(^\s*\[[^\]]+\]:\s*)([^#\s]+)'
  $s = [regex]::Replace($s, $patRef, {
    param($m)
    $head = $m.Groups[1].Value
    $url  = $m.Groups[2].Value
    if ($url -match '^(https?://|mailto:|tel:|#|\.\/|\.\./)') { return $m.Value }
    $candidate = Join-Path $root ($url -replace '/','\')
    if (Test-Path $candidate) {
      $rel = Resolve-Path -LiteralPath $candidate | ForEach-Object {
        $uriFile = New-Object System.Uri($_.Path)
        $uriDir  = New-Object System.Uri("$fileDir\")
        [uri]::UnescapeDataString($uriDir.MakeRelativeUri($uriFile).ToString()).Replace('\','/')
      }
      return "$head$rel"
    }
    return $m.Value
  }, 'Multiline')

  return $s
}

[int]$changed = 0
foreach ($f in $files) {
  $text = Get-Content $f.FullName -Raw
  if ([string]::IsNullOrEmpty($text)) { continue }
  $orig = $text

  # avoid fenced code blocks toggling — we’ll still be conservative
  $lines = $text -split "`r?`n",-1
  $out = New-Object System.Text.StringBuilder
  $inCode = $false
  foreach ($line in $lines) {
    if ($line -match '^\s*```') { $inCode = -not $inCode; [void]$out.AppendLine($line); continue }
    if (-not $inCode) {
      $l = $line
      $l = Add-IndexMdInline $l
      $l = Add-IndexMdRef    $l
      $l = Add-IndexMdAngles $l

      $l = NormalizeSlashesInLine $l
      $l = NormalizeSlashesInRefs $l
      $l = NormalizeSlashesInAngles $l

      $l = RelativizeRootishLinks $l (Split-Path $f.FullName)
      [void]$out.AppendLine($l)
    } else {
      [void]$out.AppendLine($line)
    }
  }

  $new = $out.ToString()
  if ($new -ne $orig) {
    Set-Content -Path $f.FullName -Value $new -Encoding UTF8
    $changed++
  }
}

Write-Host "Updated $changed of $($files.Count) Markdown files under $root."
