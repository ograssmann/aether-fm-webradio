"""Digitaler Zwilling AETHER V7: Gehaeuse (vereinfacht) + Bauteile als einfache Koerper -> GLB fuer den 3D-Viewer."""
import numpy as np, trimesh, fast_simplification, math
from trimesh.creation import box as tbox, cylinder as tcyl
import importlib.util, sys

# Gehaeuse-Parameter aus der CAD-Datei lesen (ohne neu zu rechnen)
src = open('gehaeuse_v7.py').read()
P = {}
exec(src.split("# ----- Design")[0], P)
EX, EY, EZ, F, W = P['EX'], P['EY'], P['EZ'], P['F'], P['W']
BX, BY, BZ0, BZ1 = P['BX'], P['BY'], P['BZ0'], P['BZ1']
g = {}
for line in src.splitlines():   # einzelne Zahlen-Konstanten
    for k in ("CH_Y", "CH_Z", "OX", "ROW_Y", "TA_X", "TA_Z", "IR_Y", "IR_LINSE_Z", "MOD_DX", "CLIP_D"):
        if line.startswith(k + " =") or line.startswith(k + ","):
            pass
CH_Y, CH_Z = EY - W - 14.0, F + 22.0
OX, ROW_Y = EX - 45.0, 24.0
TA_X, TA_Z = EX - 20.0, F + 17.0
IR_Y, IR_LZ = 60.0, F + 23.0
MOD_X0, MOD_DX, MOD_Z = EX - W - 110.0 - 8.0, 33.0, F + 5.0
OLED_PCB_Z = EZ - 0.3 - 1.8 - 1.6

parts = []   # (name, mesh, rgba)
def add(name, m, col):
    parts.append((name, m, col))
def B(name, x0, y0, z0, x1, y1, z1, col):
    m = tbox(extents=[x1 - x0, y1 - y0, z1 - z0]); m.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]); add(name, m, col)
def Cx(name, x0, x1, y, z, r, col, sec=32):     # Zylinder laengs x
    m = tcyl(radius=r, height=x1 - x0, sections=sec)
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])); m.apply_translation([(x0 + x1) / 2, y, z]); add(name, m, col)
def Cy(name, x, y0, y1, z, r, col, sec=32):
    m = tcyl(radius=r, height=y1 - y0, sections=sec)
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])); m.apply_translation([x, (y0 + y1) / 2, z]); add(name, m, col)
def Cz(name, x, y, z0, z1, r, col, sec=32):
    m = tcyl(radius=r, height=z1 - z0, sections=sec); m.apply_translation([x, y, (z0 + z1) / 2]); add(name, m, col)

GREEN, SILVER, BLACK, GOLD = [30, 120, 60, 255], [200, 202, 206, 255], [25, 25, 28, 255], [212, 175, 55, 255]
WHITE, BLUE, PURPLE, DARK = [235, 235, 235, 255], [30, 70, 170, 255], [110, 50, 150, 255], [60, 60, 66, 255]

# --- Detaillierte Bauteile (teile.py) ---
import sys; sys.path.insert(0, '.')
import teile as T_
irz = IR_LZ - 6.0 - 1.6
for n, m, c in (T_.place(T_.raspberry_pi5(), BX, BY, BZ0) + T_.place(T_.active_cooler(), BX, BY, BZ0)
                + T_.place(T_.sabrent_dac(), BX + 79.6, BY + 29.1, BZ1 + 4.1)
                + T_.place(T_.oled_13(), OX - 17.7, ROW_Y - 16.75, OLED_PCB_Z)
                + T_.place(T_.ky022(), EX - W - 1 - 19.3, IR_Y - 7.5, irz)
                + T_.place(T_.si4713_modul(), MOD_X0 - 3.5, CH_Y - 15.0, MOD_Z)):
    add(n, m, c)
# --- Taster 12 mm in der Frontwand ---
Cy("Taster", TA_X, -2.0, 22.0, TA_Z, 6.0, SILVER)
Cy("Taster Mutter", TA_X, W, W + 2.5, TA_Z, 8.0, SILVER, 6)

# --- Antennenkette: F-Durchfuehrung -> 20 dB -> 10 dB -> F-Stecker ---
Cx("F-Durchfuehrung", EX - 16.0, EX + 8.0, CH_Y, CH_Z, 4.7, SILVER)
Cx("F-Mutter innen", EX - W - 3.0, EX - W, CH_Y, CH_Z, 6.4, SILVER, 6)
Cx("Daempfer 20 dB", 165.0, 193.0, CH_Y, CH_Z, 5.3, SILVER)
Cx("Daempfer Sechskant", 161.5, 166.0, CH_Y, CH_Z, 6.35, SILVER, 6)
Cx("Daempfer 10 dB", 134.0, 162.0, CH_Y, CH_Z, 5.3, SILVER)
Cx("Daempfer Sechskant", 192.0, 199.5, CH_Y, CH_Z, 6.35, SILVER, 6)
Cx("F-Stecker", 122.0, 134.0, CH_Y, CH_Z, 5.0, GOLD)
Cx("F-Stecker Tuelle", 104.0, 122.0, CH_Y, CH_Z, 4.6, BLACK)

# --- Dupont-Kabel (Buchse-Buchse) an 90-Grad-Stiftleisten ---
DUP = {"schwarz": [20, 20, 20, 255], "weiss": [245, 245, 245, 255], "lila": [140, 60, 200, 255], "blau": [30, 90, 230, 255],
       "gruen": [20, 170, 60, 255], "gelb": [250, 210, 0, 255], "orange": [255, 130, 0, 255], "rot": [220, 20, 30, 255],
       "braun": [120, 70, 30, 255]}
def pi_pin(n):   # Pin n der geraden 40-pol. Leiste: Fuss der Dupont-Buchse (steckt senkrecht von oben)
    k = (n - 1) // 2
    return (BX + 7.87 + k * 2.54, BY + (51.23 if n % 2 else 53.77), BZ1 + 2.5)
mcx = MOD_X0 + MOD_DX / 2
# 11-pol. Leiste: Reihenfolge angenommen (Beschriftung auf deiner Platine pruefen!)
SI_LEISTE = ["RIN", "LIN", "Vin", "GND", "3Vo", "GP2", "GP1", "SDA", "SCL", "CS", "RST"]   # laut Platine, ab Klinkenbuchse
SI = {n: i for i, n in enumerate(SI_LEISTE)}
def si_pin(name):   # Si4713: gerade Leiste an der Hinterkante, Buchse steckt von oben
    return (MOD_X0 - 3.5 + 7.27 + SI[name] * 2.54, CH_Y - 15.0 + 16.0, MOD_Z + 1.6 + 2.5)
OL = {"VCC": 0, "GND": 1, "SCL": 2, "SDA": 3}
def ol_pin(name):   # OLED: VCC GND SCK SDA, abgewinkelt nach hinten
    return (OX - 3.64 + OL[name] * 2.54, ROW_Y + 16.0, OLED_PCB_Z - 1.3)
IRP = {"S": -1, "+": 0, "-": 1}
def ir_pin(name):   # KY-022: Leiste zeigt nach innen (-x)
    return (EX - W - 1 - 19.3 - 1.0, IR_Y + IRP[name] * 2.54, irz + 2.9)
KABEL = [   # (Farbe, von, nach, Bezeichnung)
    ("rot",    pi_pin(1),  si_pin("Vin"), "Pi 1 (3,3 V) -> Si4713 Vin"),
    ("schwarz", pi_pin(6), si_pin("GND"), "Pi 6 (GND) -> Si4713 GND"),
    ("blau",   pi_pin(3),  si_pin("SDA"), "Pi 3 (SDA) -> Si4713 SDA"),
    ("gelb",   pi_pin(5),  si_pin("SCL"), "Pi 5 (SCL) -> Si4713 SCL"),
    ("gruen",  pi_pin(29), si_pin("RST"), "Pi 29 (GPIO 5) -> Si4713 RST"),
    ("orange", pi_pin(17), ol_pin("VCC"), "Pi 17 (3,3 V) -> OLED VCC"),
    ("schwarz", pi_pin(9), ol_pin("GND"), "Pi 9 (GND) -> OLED GND"),
    ("lila",   pi_pin(15), ol_pin("SDA"), "Pi 15 (GPIO 22, SDA Bus 3) -> OLED SDA"),
    ("braun",  pi_pin(13), ol_pin("SCL"), "Pi 13 (GPIO 27, SCL Bus 3) -> OLED SCK"),
    ("weiss",  pi_pin(16), ir_pin("S"),   "Pi 16 (GPIO 23) -> IR S"),
    ("rot",    pi_pin(18), ir_pin("+"),   "Pi 18 (GPIO 24 = 3,3 V) -> IR +"),
    ("schwarz", pi_pin(20), ir_pin("-"),  "Pi 20 (GND) -> IR -"),
]
J2 = (BX + 22.8, BY + 5.75, BZ1 + 3.0)  # J2 (2 Loetaugen fuer externen Power-Taster) neben der RTC-Buchse J5 (BAT)
KABEL += [("weiss", (J2[0], J2[1] - 1.27, J2[2]), (TA_X - 2.0, 22.0, TA_Z), "J2 -> Taster (Polung egal)"),
          ("weiss", (J2[0], J2[1] + 1.27, J2[2]), (TA_X + 2.0, 22.0, TA_Z), "J2 -> Taster (Polung egal)")]

def kabel_mesh(punkte, r=0.7):
    teile = []
    for a, b in zip(punkte[:-1], punkte[1:]):
        a, b = np.array(a, float), np.array(b, float)
        if np.linalg.norm(b - a) < 1e-6: continue
        teile.append(trimesh.creation.cylinder(radius=r, segment=[a, b], sections=10))
        teile.append(trimesh.creation.icosphere(subdivisions=1, radius=r).apply_translation(b))
    return trimesh.util.concatenate(teile)
def stecker(p, richtung):   # schwarze Dupont-Buchse 2,5 x 2,5 x 14 entlang 'richtung'
    d = np.array(richtung, float); L = 14.0
    c = np.array(p, float) + d * L / 2
    ext = [L if abs(d[0]) > 0.5 else 2.5, L if abs(d[1]) > 0.5 else 2.5, L if abs(d[2]) > 0.5 else 2.5]
    m = tbox(extents=ext); m.apply_translation(c); return m, tuple(np.array(p) + d * L)
kabel_teile = []
for i, (farbe, a, b, txt) in enumerate(KABEL):
    da = (0, 0, 1)                                             # Pi-Leiste und J2: Stifte senkrecht nach oben
    if txt.startswith("Pi") or txt.startswith("J2"):
        pass
    db = {"Si": (0, 0, 1), "OL": (0, 1, 0), "IR": (-1, 0, 0)}
    ziel = "Si" if "Si4713" in txt else "OL" if "OLED" in txt else "IR" if "IR" in txt else None
    sa, ea = stecker(a, da)
    kabel_teile.append((f"Buchse {farbe}: {txt}", sa, [15, 15, 15, 255]))
    if ziel:
        sb, eb = stecker(b, db[ziel]); kabel_teile.append((f"Buchse {farbe}: {txt}", sb, [15, 15, 15, 255]))
    else:
        eb = b
    zr = 31.0 + (i % 6) * 0.9
    pts = [ea, (ea[0] + da[0] * 4, ea[1] + da[1] * 4, ea[2]), (ea[0] + da[0] * 4, ea[1] + da[1] * 4, zr),
           (eb[0], eb[1], zr), eb]
    kabel_teile.append((f"Kabel {farbe}: {txt}", kabel_mesh(pts), DUP[farbe]))

# --- 3,5-mm-Klinkenkabel (Winkelstecker) DAC -> Si4713 und Antennen-Koax F-Stecker -> Si4713 ANT/GND ---
SX0 = MOD_X0 - 3.5                       # Modul-Ursprung (x)
jack = (SX0 - 0.8, CH_Y - 15.0 + 4.5, MOD_Z + 1.6 + 2.6)     # Buchsenoeffnung am Modul (zeigt nach -x)
dac = (BX + 79.6 + 50.6, BY + 29.1 - 4.5, BZ1 + 4.1)          # gruene Klinke am DAC (zeigt nach +x)
SCHWARZ = [25, 25, 28, 255]
def stecker35(p, richtung, name):   # gerader 3,5-mm-Stecker (Metallhuelse wie Foto)
    d = np.array(richtung, float); p = np.array(p, float)
    teile = [trimesh.creation.cylinder(radius=1.75, segment=[p, p - d * 6], sections=16),
             trimesh.creation.cylinder(radius=3.6, segment=[p, p + d * 22], sections=20)]
    return (name, trimesh.util.concatenate(teile), [200, 202, 206, 255]), tuple(p + d * 22)
KL = "Kabel schwarz: Klinkenkabel 3,5 mm: DAC (gruen) -> Si4713 Audio"
st1, k1 = stecker35(dac, (1, 0, 0), KL)
st2, k2 = stecker35(jack, (-1, 0, 0), KL)
kabel_teile += [st1, st2]
# 1-m-Kabel als Rolle am Boden zwischen Soundkarte und Daempfern (wie im Foto)
cx_, cy_, rr = 128.0, 58.0, 17.0
rolle = [k1, (k1[0] + 6, k1[1] + 4, F + 6)]
for i in range(0, 3 * 24 + 1):
    a_ = 2 * math.pi * i / 24 - math.pi / 2
    rolle.append((cx_ + rr * math.cos(a_) * (1 + 0.04 * (i // 24)), cy_ + rr * math.sin(a_) * (1 + 0.04 * (i // 24)), F + 2.2 + 0.4 * (i % 2)))
rolle += [(cx_ - 20, cy_ + 10, F + 3), (k2[0] - 6, k2[1] - 2, k2[2] - 3), k2]
kabel_teile.append((KL, kabel_mesh(rolle, 1.6), SCHWARZ))
KABEL.append(("schwarz", None, None, "Klinkenkabel 3,5 mm: DAC (gruen) -> Si4713 Audio"))
# Antennen-Koax: vom Ende der Kette (F-Stecker-Tuelle) in einer Schlaufe zum ANT-Loetpunkt am Modulende (+x, vorne)
KO = "Kabel braun: Antennen-Koax: F-Stecker -> Si4713 ANT (Seele) / GND (Schirm)"
ant = (SX0 + 36.5, CH_Y - 15.0 + 2.7, MOD_Z + 1.9)
koax = [(104.0, CH_Y, CH_Z), (98.0, CH_Y, CH_Z - 1), (90.0, CH_Y - 4, CH_Z - 8), (84.0, CH_Y - 14, MOD_Z + 6),
        (100.0, CH_Y - 20, MOD_Z + 4), (ant[0] + 2, ant[1] - 6, ant[2] + 3), ant]
kabel_teile.append((KO, kabel_mesh(koax, 1.3), [120, 80, 60, 255]))
KABEL.append(("braun", None, None, "Antennen-Koax: F-Stecker -> Si4713 ANT (Seele) / GND (Schirm)"))

# --- Gehaeuse: vereinfachen und als eigene Teile ---
def gehaeuse(p, ziel):
    m = trimesh.load(p, process=False); m.merge_vertices(digits_vertex=4)
    v, f = fast_simplification.simplify(np.asarray(m.vertices, np.float32), np.asarray(m.faces, np.int32), target_reduction=1 - ziel / len(m.faces))
    return trimesh.Trimesh(v, f, process=False)
base = gehaeuse('Gehaeuse_V7_Unterteil.stl', 45000)
lid = gehaeuse('Gehaeuse_V7_Deckel.stl', 45000)
txt = trimesh.load('Gehaeuse_V7_Deckel_Schrift.stl', process=False)
for m in (lid, txt):   # Deckel in Einbaulage: y und z spiegeln
    m.vertices[:, 1] = EY - m.vertices[:, 1]; m.vertices[:, 2] = EZ + 2.0 - m.vertices[:, 2]; m.invert()

scene = trimesh.Scene()
META = []
def put(name, m, col, gruppe):
    m = m.copy(); m.visual = trimesh.visual.ColorVisuals(m)
    i = len(META); META.append(dict(g=gruppe, n=name, c="#%02x%02x%02x" % tuple(col[:3])))
    scene.add_geometry(m, node_name=f"n{i}", geom_name=f"g{i}")
put("Unterteil", base, [70, 70, 74, 255], "gehaeuse")
sd = trimesh.load('Gehaeuse_V7_Seitendeckel.stl', process=False)
fy0, fz0 = BY + 5.5, BZ0 - 4.5
X, Y, Z = sd.vertices[:, 0].copy(), sd.vertices[:, 1].copy(), sd.vertices[:, 2].copy()
sd.vertices = np.column_stack([Z - 1.0, fy0 - 1.2 + X, fz0 - 1.2 + Y])
put("Seitendeckel (Rastdeckel Pi-Fenster)", sd, [55, 55, 60, 255], "teil")
put("Deckel", lid, [22, 22, 24, 255], "deckel")
put("Schrift", txt, WHITE, "deckel")
for name, m, col in parts:
    put(name, m, col, "teil")
for name, m, col in kabel_teile:
    put(name, m, col, "kabel")
import json
json.dump([dict(farbe=f, text=t) for f, _, _, t in KABEL], open('../../twin/kabel.json', 'w'), ensure_ascii=False)
json.dump(META, open('../../twin/meta.json', 'w'), ensure_ascii=False)
scene.export('../../twin/aether_v7.glb')
from trimesh.exchange.gltf import export_gltf
open('../../twin/aether_v7.json', 'wb').write(export_gltf(scene, embed_buffers=True)['model.gltf'])
print("ok", len(parts), "Teile")
