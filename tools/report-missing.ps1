# tools\report-missing.ps1
$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot '..\docs'

$outFile = Join-Path $PSScriptRoot 'missing-links.txt'
$results = @()

# inline link, image link, reference-style definition
$rx = '(?<!\!)\[[^\]]*\]\((?!https?://)([^)#?]+)\)|!\[[^\]]*\]\((?!https?://)([^)#?]+)\)|^\s*\[[^\]]+\]:\s*(?!https?://)([^#\s]+)'

Get-ChildItem $root -Recurse -Filter *.md -File | ForEach-Object {
    $dir  = Split-Path $_.FullName
    $text = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
    if ([string]::IsNullOrEmpty($text)) { return }   # skip empty/null

    foreach ($m in [regex]::Matches($text, $rx, 'IgnoreCase, Multiline')) {
        $rel = ($m.Groups[1].Value + $m.Groups[2].Value + $m.Groups[3].Value).Trim()
        if (-not $rel) { continue }
        if ($rel -match '^(mailto:|tel:|#)') { continue }

        $rel = $rel -replace '\\','/'
        $abs = Join-Path $dir ($rel -replace '/','\')
        if (-not (Test-Path $abs)) {
            $line = "[MISSING] $($_.FullName) -> $rel"
            Write-Host $line
            $results += $line
        }
    }
}

if ($results.Count -gt 0) {
    $results | Out-File -FilePath $outFile -Encoding UTF8
    Write-Host "Missing links report saved to: $outFile"
} else {
    Write-Host "No missing links found."
}
