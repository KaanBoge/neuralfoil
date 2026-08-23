param([string]$runsCsv, [double]$y0base, [double]$y0slope, [double]$cd0x, [double]$pitch, [string]$label, [double]$M0 = 0.90, [double]$xref = 260)
# groups dark runs into connected components; reports marker-like components as (M, cd)
$runs = Import-Csv $runsCsv | ForEach-Object {
  [pscustomobject]@{ y = [int]$_.y; x = [double]$_.cx; len = [int]$_.len }
} | Where-Object { $_.len -le 70 } | Sort-Object y, x
# spatial hash by y
$byY = @{}
foreach ($r in $runs) { if (-not $byY[$r.y]) { $byY[$r.y] = [System.Collections.ArrayList]@() }; [void]$byY[$r.y].Add($r) }
$comp = @{}; $nid = 0
$assign = @{}
foreach ($r in $runs) {
  $key = "$($r.y):$($r.x)"
  if ($assign[$key]) { continue }
  $nid++
  $stack = [System.Collections.Stack]@(); $stack.Push($r)
  $assign[$key] = $nid
  $members = [System.Collections.ArrayList]@()
  while ($stack.Count) {
    $c = $stack.Pop(); [void]$members.Add($c)
    for ($dy = -3; $dy -le 3; $dy++) {
      if ($dy -eq 0) { continue }
      $row = $byY[$c.y + $dy]
      if (-not $row) { continue }
      foreach ($n in $row) {
        $nkey = "$($n.y):$($n.x)"
        if ($assign[$nkey]) { continue }
        if ([math]::Abs($n.x - $c.x) -le 9) { $assign[$nkey] = $nid; $stack.Push($n) }
      }
    }
  }
  $comp[$nid] = $members
}
"components: $($comp.Count)"
$out = foreach ($k in $comp.Keys) {
  $m = $comp[$k]
  if ($m.Count -lt 6) { continue }
  $ys = $m | ForEach-Object { $_.y }
  $h = ($ys | Measure-Object -Maximum).Maximum - ($ys | Measure-Object -Minimum).Minimum + 1
  $maxlen = ($m | Measure-Object -Property len -Maximum).Maximum
  $meanlen = ($m | Measure-Object -Property len -Average).Average
  $cy = ($m | Measure-Object -Property y -Average).Average
  $cx = ($m | Measure-Object -Property x -Average).Average
  $y0 = $y0base + ($cx - $xref) * $y0slope
  $M = $M0 - ($cy - $y0) / 107.3 * 0.025
  $cd = ($cd0x - $cx) / $pitch * 0.0025
  $kind = if ($maxlen -ge 30 -and $h -ge 22 -and $h -le 70 -and $meanlen -ge 18) { "MARKER" } elseif ($h -gt 70) { "track" } else { "seg" }
  [pscustomobject]@{ kind = $kind; M = [math]::Round($M,4); cd = [math]::Round($cd,5); n = $m.Count; h = $h; maxlen = $maxlen; meanlen = [math]::Round($meanlen,1); y = [math]::Round($cy,0); x = [math]::Round($cx,0) }
}
"== MARKER candidates =="
$out | Where-Object { $_.kind -eq "MARKER" } | Sort-Object M -Descending | Format-Table -AutoSize | Out-String -Width 140
"== tall tracks (plateau/bundle) =="
$out | Where-Object { $_.kind -eq "track" } | Sort-Object n -Descending | Select-Object -First 25 | Format-Table -AutoSize | Out-String -Width 140