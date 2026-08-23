param([string]$img, [int[]]$bands)
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class RowBand {
  public static int W, H;
  static bool[,] dark;
  public static void Load(string path, int thr) {
    Bitmap bmp = new Bitmap(path);
    W = bmp.Width; H = bmp.Height;
    dark = new bool[W, H];
    BitmapData bd = bmp.LockBits(new Rectangle(0,0,W,H), ImageLockMode.ReadOnly, PixelFormat.Format24bppRgb);
    int stride = bd.Stride;
    byte[] buf = new byte[stride * H];
    Marshal.Copy(bd.Scan0, buf, 0, buf.Length);
    bmp.UnlockBits(bd);
    for (int y = 0; y < H; y++)
      for (int x = 0; x < W; x++) {
        int i = y * stride + x * 3;
        int v = (buf[i] + buf[i+1] + buf[i+2]) / 3;
        dark[x, y] = v < thr;
      }
    bmp.Dispose();
  }
  public static double[] RowProfileBand(int x0, int x1) {
    double[] p = new double[H];
    for (int y = 0; y < H; y++) { int c = 0; for (int x = x0; x < x1; x++) if (dark[x,y]) c++; p[y] = (double)c / (x1 - x0); }
    return p;
  }
}
"@ -ReferencedAssemblies System.Drawing
[RowBand]::Load($img, 110)
for ($b = 0; $b -lt $bands.Length; $b += 2) {
  $x0 = $bands[$b]; $x1 = $bands[$b+1]
  $rp = [RowBand]::RowProfileBand($x0, $x1)
  $mean = ($rp | Measure-Object -Average).Average
  $minv = [math]::Max(0.45, $mean * 1.8)
  "BAND x $x0-$x1 (mean $([math]::Round($mean,3))), HLINES:"
  $i = 0
  $res = @()
  while ($i -lt $rp.Length) {
    if ($rp[$i] -ge $minv) {
      $j = $i; $best = $i
      while ($j -lt $rp.Length -and $rp[$j] -ge $minv) { if ($rp[$j] -gt $rp[$best]) { $best = $j }; $j++ }
      $res += "  y=$best f=$([math]::Round($rp[$best],3)) w=$($j-$i)"
      $i = $j
    } else { $i++ }
  }
  $res -join "`n"
}