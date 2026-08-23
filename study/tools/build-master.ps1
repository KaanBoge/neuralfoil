# build-master.ps1 : merges per-figure raw CSVs into master-dataset.csv (schema per protocol-deviations.md A9)
# Single read path: every later figure/analysis reads master-dataset.csv, never the raw layer.
param([string]$dir = $PSScriptRoot)
$out = Join-Path $dir "master-dataset.csv"

function LoadCsv($name) { (Get-Content (Join-Path $dir $name)) | Where-Object { $_ -notmatch '^\s*#' } | ConvertFrom-Csv }

# optional lookups (created after the conventions/CL digitization)
$reTab = @()
if (Test-Path (Join-Path $dir "ferri-re.csv")) { $reTab = LoadCsv "ferri-re.csv" | ForEach-Object { [pscustomobject]@{ M = [double]$_.M; Re = [double]$_.Re_million * 1e6 } } | Sort-Object M }
$clTab = @()
if (Test-Path (Join-Path $dir "ferri-cl.csv")) { $clTab = LoadCsv "ferri-cl.csv" | ForEach-Object { [pscustomobject]@{ alpha = [double]$_.alpha; M = [double]$_.M; CL = [double]$_.CL } } }

function InterpRe([double]$M) {
  if ($reTab.Count -lt 2) { return "" }
  if ($M -le $reTab[0].M) { return [math]::Round($reTab[0].Re, 0) }
  if ($M -ge $reTab[-1].M) { return [math]::Round($reTab[-1].Re, 0) }
  for ($i = 1; $i -lt $reTab.Count; $i++) {
    if ($M -le $reTab[$i].M) {
      $a = $reTab[$i-1]; $b = $reTab[$i]
      return [math]::Round($a.Re + ($b.Re - $a.Re) * ($M - $a.M) / ($b.M - $a.M), 0)
    }
  }
  return ""
}
function InterpCL([double]$alpha, [double]$M) {
  $c = @($clTab | Where-Object { [math]::Abs($_.alpha - $alpha) -lt 0.01 } | Sort-Object M)
  if ($c.Count -lt 2) { return "" }
  if ($M -le $c[0].M) { return [math]::Round($c[0].CL, 3) }
  if ($M -ge $c[-1].M) { return [math]::Round($c[-1].CL, 3) }
  for ($i = 1; $i -lt $c.Count; $i++) {
    if ($M -le $c[$i].M) {
      $a = $c[$i-1]; $b = $c[$i]
      return [math]::Round($a.CL + ($b.CL - $a.CL) * ($M - $a.M) / ($b.M - $a.M), 3)
    }
  }
  return ""
}

$rows = [System.Collections.ArrayList]@()

foreach ($r in (LoadCsv "harris-fig8.csv")) {
  $sweep = switch ("$($r.Re)|$($r.transition)") {
    "3.0e6|fixed" { "H8-3F" } "6.0e6|fixed" { "H8-6F" } "9.0e6|fixed" { "H8-9F" } "3.0e6|free" { "H8-3free" } default { "H8-x" }
  }
  [void]$rows.Add([pscustomobject]@{
    sweep_id = $sweep; report = $r.report; figure = $r.figure; airfoil = $r.airfoil; family = $r.family
    tc_percent = $r.tc_percent; camber = $r.camber; Re = $r.Re; mach = $r.mach; transition = $r.transition
    alpha_nominal = "-0.14"; alpha_plotted = "-0.14"; CL = $r.CL_nominal; CD = $r.CD
    tier_source = ""; tier_extraction = $r.quality_tier
    double_read = if ($r.method -match "\+shape|double-read") { "TRUE" } else { "FALSE" }
    method = $r.method; u_cd = $r.uncertainty_cd; u_M = $r.uncertainty_M; mdd_rule = ""
    role = "holdout"; notes = $r.notes
  })
}

foreach ($r in (LoadCsv "ferri-2309.csv")) {
  $ap = $r.alpha_deg
  $an = if ($ap -eq "-1,0") { "0" } else { $ap }
  $sweep = "F33-a" + $an
  $M = [double]$r.mach
  [void]$rows.Add([pscustomobject]@{
    sweep_id = $sweep; report = $r.report; figure = $r.figure; airfoil = $r.airfoil; family = $r.family
    tc_percent = $r.tc_percent; camber = $r.camber
    Re = $(if ($reTab.Count) { InterpRe $M } else { $r.Re })
    mach = $r.mach; transition = $r.transition
    alpha_nominal = $an; alpha_plotted = $ap
    CL = $(if ($clTab.Count) { InterpCL ([double]$an) $M } else { $r.CL_nominal })
    CD = $r.CD
    tier_source = ""; tier_extraction = $r.quality_tier
    double_read = if ($r.method -match "QC|double") { "TRUE" } else { "FALSE" }
    method = $r.method; u_cd = $r.uncertainty_cd; u_M = $r.uncertainty_M; mdd_rule = ""
    role = "calibration-increment-only"; notes = $r.notes
  })
}

# apply QC double-read flags for the sampled alpha 1 / alpha 2 points if the sample file exists
if (Test-Path (Join-Path $dir "ferri-qc-sample.csv")) {
  $qc = LoadCsv "ferri-qc-sample.csv"
  foreach ($q in $qc) {
    $t = $rows | Where-Object { $_.sweep_id -eq $q.sweep_id -and [math]::Abs([double]$_.mach - [double]$q.mach) -lt 0.012 }
    foreach ($m in $t) { $m.double_read = "TRUE"; $m.notes = ($m.notes + " | QC re-read delta " + $q.delta_counts + " counts").Trim(" |") }
  }
}

$rows | Export-Csv -Path $out -NoTypeInformation -Encoding ascii
"wrote $out : $($rows.Count) rows"
"double_read TRUE: $(($rows | Where-Object { $_.double_read -eq 'TRUE' }).Count) of $($rows.Count) ($([math]::Round(($rows | Where-Object { $_.double_read -eq 'TRUE' }).Count / $rows.Count * 100, 1))%)"