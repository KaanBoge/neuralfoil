param([string]$img, [string]$tag)
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class PlotScan {
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
  public static double[] ColProfile() {
    double[] p = new double[W];
    for (int x = 0; x < W; x++) { int c = 0; for (int y = 0; y < H; y++) if (dark[x,y]) c++; p[x] = (double)c / H; }
    return p;
  }
  public static double[] RowProfile() {
    double[] p = new double[H];
    for (int y = 0; y < H; y++) { int c = 0; for (int x = 0; x < W; x++) if (dark[x,y]) c++; p[y] = (double)c / W; }
    return p;
  }
  /* sliding-window density -> blob mask -> connected components */
  public static string Blobs(int win, double frac, int minArea) {
    int r = win / 2;
    /* integral image of dark */
    int[,] ii = new int[W+1, H+1];
    for (int x = 1; x <= W; x++)
      for (int y = 1; y <= H; y++)
        ii[x,y] = ii[x-1,y] + ii[x,y-1] - ii[x-1,y-1] + (dark[x-1,y-1] ? 1 : 0);
    bool[,] mask = new bool[W, H];
    int area = win * win;
    for (int x = r; x < W - r; x++)
      for (int y = r; y < H - r; y++) {
        int x0 = x - r, y0 = y - r, x1 = x + r + 1, y1 = y + r + 1;
        int c = ii[x1,y1] - ii[x0,y1] - ii[x1,y0] + ii[x0,y0];
        if ((double)c / area >= frac && dark[x,y]) mask[x,y] = true;
      }
    /* CC via BFS */
    int[,] lab = new int[W, H];
    int nl = 0;
    List<string> outp = new List<string>();
    int[] qx = new int[W*H/4]; int[] qy = new int[W*H/4];
    for (int x = 0; x < W; x++)
      for (int y = 0; y < H; y++) {
        if (!mask[x,y] || lab[x,y] != 0) continue;
        nl++;
        int head = 0, tail = 0;
        qx[tail] = x; qy[tail] = y; tail++;
        lab[x,y] = nl;
        long sx = 0, sy = 0; int n = 0;
        int mnx = x, mxx = x, mny = y, mxy = y;
        while (head < tail) {
          int cx = qx[head], cy = qy[head]; head++;
          sx += cx; sy += cy; n++;
          if (cx < mnx) mnx = cx; if (cx > mxx) mxx = cx;
          if (cy < mny) mny = cy; if (cy > mxy) mxy = cy;
          for (int dx = -1; dx <= 1; dx++)
            for (int dy = -1; dy <= 1; dy++) {
              int nx2 = cx + dx, ny2 = cy + dy;
              if (nx2 < 0 || ny2 < 0 || nx2 >= W || ny2 >= H) continue;
              if (mask[nx2,ny2] && lab[nx2,ny2] == 0) { lab[nx2,ny2] = nl; qx[tail] = nx2; qy[tail] = ny2; tail++; }
            }
        }
        if (n >= minArea)
          outp.Add(string.Format("{0:F1},{1:F1},{2},{3},{4}", (double)sx/n, (double)sy/n, n, mxx-mnx+1, mxy-mny+1));
      }
    return string.Join("\n", outp);
  }
}
"@ -ReferencedAssemblies System.Drawing
[PlotScan]::Load($img, 110)
"IMG $tag ${img}: $([PlotScan]::W) x $([PlotScan]::H)"
$cp = [PlotScan]::ColProfile()
$rp = [PlotScan]::RowProfile()
function Peaks([double[]]$p, [double]$minv) {
  $res = @()
  $i = 0
  while ($i -lt $p.Length) {
    if ($p[$i] -ge $minv) {
      $j = $i; $best = $i
      while ($j -lt $p.Length -and $p[$j] -ge $minv) { if ($p[$j] -gt $p[$best]) { $best = $j }; $j++ }
      $res += ,@($best, [math]::Round($p[$best],3), ($j - $i))
      $i = $j
    } else { $i++ }
  }
  return ,$res
}
$colMean = ($cp | Measure-Object -Average).Average
$rowMean = ($rp | Measure-Object -Average).Average
"colMean=$([math]::Round($colMean,3)) rowMean=$([math]::Round($rowMean,3))"
"VLINES (x, darkfrac, width):"
(Peaks $cp ([math]::Max(0.30, $colMean * 2.2))) | ForEach-Object { "  $($_[0])  $($_[1])  w$($_[2])" }
"HLINES (y, darkfrac, width):"
(Peaks $rp ([math]::Max(0.30, $rowMean * 2.2))) | ForEach-Object { "  $($_[0])  $($_[1])  w$($_[2])" }
"BLOBS (cx,cy,area,w,h):"
[PlotScan]::Blobs(13, 0.72, 60)
