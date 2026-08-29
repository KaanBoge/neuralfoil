"""Parse the UIUC LSAT measured corpus into one CSV.
Sources: DRAG01/02/03/06.TXT (Summary of Low-Speed Airfoil Data vols 1,2,3 and
the Williamson vol 6 files) + SoarTech-8 ALL.PD. GPL v2 data, Selig et al.
Output rows: source, airfoil_raw, config, Re, alpha, CL, CD, u_cd_span
(u_cd_span = half-spread of the spanwise Cd stations when present: a measured
per-point uncertainty proxy).
Geometry: volumes matched to the public UIUC coordinate database (nominal
geometry; the measured-model coordinates in COORD0x.TXT are not public-licensed
and are not used). SoarTech airfoils use their own public .COR measured
coordinates, chord-normalized.
"""
import csv, os, re, sys

def ffloat(s):
    s2 = re.sub(r"[^0-9eE+.-]", "", s)
    return float(s2)

BASE = os.path.dirname(os.path.abspath(__file__))
rows = []

def clean_config(comment):
    c = (comment or "").lower()
    if any(k in c for k in ("trip", "tape", "zigzag", "zig-zag", "rough", "bump",
                            "flap", "gurney", "turbulator", "vortex", "serrat",
                            "upside", "inverted", "gap", "seal", "cover")):
        return "modified"
    return "clean"

# ---------------- volumes: DRAG0x.TXT ----------------
def parse_drag_txt(path, source):
    txt = open(path, errors="replace").read().splitlines()
    i, n = 0, len(txt)
    af, builder, comment = None, None, ""
    while i < n:
        L = txt[i].strip()
        if L.startswith("Airfoil:"):
            af = L.split(":", 1)[1].strip(); comment = ""
        elif L.startswith("Builder:"):
            builder = L.split(":", 1)[1].strip()
        elif L.startswith("Comment:"):
            comment = L.split(":", 1)[1].strip()
        elif L.startswith("Average Reynolds #"):
            i += 1
            Re = float(txt[i].strip())
            while not txt[i].strip().startswith("Number of angles"):
                i += 1
            i += 1
            cnt = int(txt[i].strip())
            while "alpha" not in txt[i]:
                i += 1
            for k in range(cnt):
                i += 1
                p = txt[i].split()
                if len(p) < 3:
                    continue
                try:
                    a, cl, cd = ffloat(p[0]), ffloat(p[1]), ffloat(p[2])
                except ValueError:
                    continue
                span = []
                for x in p[3:]:
                    try: span.append(ffloat(x))
                    except ValueError: pass
                span = span or [cd]
                u = (max(span) - min(span)) / 2 if len(span) > 1 else ""
                rows.append([source, af, clean_config(comment), Re, a, cl, cd, u])
        i += 1

for v, d in (("vol1", "volume01/volume01/DRAG01.TXT"),
             ("vol2", "volume02/volume02/DRAG02.TXT"),
             ("vol3", "volume03/volume03/DRAG03.TXT"),
             ("vol6", "volume06/volume06/DRAG06.TXT")):
    p = os.path.join(BASE, d)
    if not os.path.exists(p):
        alt = [x for x in os.listdir(os.path.join(BASE, d.split("/")[0], d.split("/")[1]))
               if x.upper().startswith("DRAG")] if os.path.isdir(os.path.join(BASE, d.split("/")[0], d.split("/")[1])) else []
        if alt:
            p = os.path.join(BASE, d.split("/")[0], d.split("/")[1], alt[0])
        else:
            print("MISSING", d); continue
    before = len(rows)
    parse_drag_txt(p, v)
    print(v, len(rows) - before, "points")

# ---------------- SoarTech 8: ALL.PD ----------------
pd_path = os.path.join(BASE, "stec8", "ALL.PD")
txt = open(pd_path, errors="replace").read().splitlines()
i, n = 0, len(txt)
before = len(rows)
while i < n:
    L = txt[i].split()
    if L and L[0] == "Airfoil":
        af = " ".join(L[1:])
        i += 1  # Builder line
        i += 1
        nblocks = int(txt[i].split()[0])
        for b in range(nblocks):
            i += 1
            Re = float(txt[i].split()[0])
            i += 1
            cnt = int(txt[i].split()[0])
            for k in range(cnt):
                i += 1
                p = txt[i].split()
                try:
                    cl, cd, a = ffloat(p[0]), ffloat(p[1]), ffloat(p[2])
                except ValueError:
                    continue
                rows.append(["stec8", af, "clean", Re, a, cl, cd, ""])
    i += 1
print("stec8", len(rows) - before, "points")

with open(os.path.join(BASE, "lsat-corpus.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["source", "airfoil", "config", "Re", "alpha", "CL", "CD", "u_cd_span"])
    w.writerows(rows)
afs = sorted(set(r[1] for r in rows))
print("TOTAL", len(rows), "measured points,", len(afs), "airfoil entries")
print("clean:", sum(1 for r in rows if r[2] == "clean"), " modified:", sum(1 for r in rows if r[2] == "modified"))
