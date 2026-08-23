param([string]$runsCsv)
# guided path tracing: follow each series' line upward (decreasing y) from plateau seeds
$runs = Import-Csv $runsCsv | ForEach-Object {
  [pscustomobject]@{ y = [int]$_.y; x = [double]$_.cx; len = [int]$_.len }
} | Where-Object { $_.len -le 70 -and $_.x -gt 150 }
$byY = @{}
foreach ($r in $runs) { if (-not $byY[$r.y]) { $byY[$r.y] = [System.Collections.ArrayList]@() }; [void]$byY[$r.y].Add($r) }
function TracePath([double]$seedX, [int]$seedY, [int]$endY, [string]$name) {
  $x = $seedX; $lastHit = $seedY
  $pts = [System.Collections.ArrayList]@()
  for ($y = $seedY; $y -ge $endY; $y--) {
    $row = $byY[$y]
    if ($row) {
      $best = $null; $bd = 40
      foreach ($r in $row) {
        $d = [math]::Abs($r.x - $x)
        if ($d -lt $bd) { $bd = $d; $best = $r }
      }
      if ($best) {
        # drift limiter: max 1.2 px/row since last hit
        $maxDrift = 5 + 3.5 * ($lastHit - $y)
        if ([math]::Abs($best.x - $x) -le $maxDrift) {
          $x = $best.x; $lastHit = $y
          [void]$pts.Add([pscustomobject]@{ y = $y; x = $x })
        }
      }
    }
    if (($lastHit - $y) -gt 40) { break }  # lost the line
  }
  "PATH $name seed($seedX,$seedY) -> ended y=$($pts[-1].y) x=$($pts[-1].x) points=$($pts.Count)"
  # report every ~13 rows (0.003 M)
  $step = 13; $nexty = $seedY
  foreach ($p in $pts) {
    if ($p.y -le $nexty) {
      $y0 = 120 + ($p.x - 260) * 0.0143
      $M = 0.90 - ($p.y - $y0) / 107.3 * 0.025
      $cd = (1621 - $p.x) / 107.0 * 0.0025
      "  $name M=$([math]::Round($M,4)) cd=$([math]::Round($cd,5)) (y=$($p.y) x=$([math]::Round($p.x,0)))"
      $nexty = $p.y - $step
    }
  }
}
TracePath 1137 985 335 "A_cd0113"
TracePath 1206 985 335 "B_cd0097"
TracePath 1270 985 335 "C_cd0082"
TracePath 1343 985 335 "D_cd0065"
