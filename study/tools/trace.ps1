param([string]$img, [string]$outCsv, [double[]]$vlines)
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class Tracer {
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
  /* per-row dark runs; skip runs that are just a gridline (near vline and narrow) */
  public static string Runs(double[] vlines, int minRun, int lineHalo, int lineMaxW) {
    List<string> outp = new List<string>();
    for (int y = 0; y < H; y++) {
      int x = 0;
      while (x < W) {
        if (!dark[x, y]) { x++; continue; }
        int x0 = x;
        while (x < W && dark[x, y]) x++;
        int len = x - x0;
        if (len < minRun) continue;
        double cx = (x0 + x - 1) / 2.0;
        bool online = false;
        foreach (double v in vlines)
          if (Math.Abs(cx - v) <= lineHalo && len <= lineMaxW) { online = true; break; }
        if (!online) outp.Add(y + "," + cx.ToString("F1") + "," + len);
      }
    }
    return string.Join("\n", outp);
  }
}
"@ -ReferencedAssemblies System.Drawing
[Tracer]::Load($img, 110)
$res = [Tracer]::Runs($vlines, 12, 9, 24)
Set-Content -Path $outCsv -Value "y,cx,len`n$res" -Encoding ascii
"wrote $outCsv : $((($res -split "`n")).Count) runs; img $([Tracer]::W)x$([Tracer]::H)"