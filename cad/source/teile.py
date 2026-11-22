"""Detaillierte Bauteil-Modelle fuer den digitalen Zwilling (lokale Koordinaten in mm, Platinenunterseite z = 0).
Jede Funktion liefert eine Liste (name, trimesh, rgba)."""
import numpy as np, trimesh, random
from shapely.geometry import box as sbox, Point
from trimesh.creation import box as tbox, cylinder as tcyl, extrude_polygon

C = dict(pcb_g=[24, 110, 58, 255], pcb_p=[105, 45, 150, 255], pcb_b=[25, 70, 160, 255], pcb_k=[22, 22, 24, 255],
         silver=[196, 199, 204, 255], dark=[38, 38, 42, 255], black=[18, 18, 20, 255], gold=[214, 176, 70, 255],
         beige=[226, 214, 186, 255], white=[236, 236, 230, 255], blue=[30, 110, 220, 255], glass=[10, 12, 16, 255],
         red=[230, 30, 40, 255], green=[40, 200, 80, 255], pink=[240, 120, 170, 255], lime=[120, 200, 70, 255])

def B(n, x0, y0, z0, x1, y1, z1, col):
    m = tbox(extents=[x1 - x0, y1 - y0, z1 - z0]); m.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return (n, m, C[col] if isinstance(col, str) else col)
def CZ(n, x, y, z0, z1, r, col, sec=24):
    m = tcyl(radius=r, height=z1 - z0, sections=sec); m.apply_translation([x, y, (z0 + z1) / 2]); return (n, m, C[col])
def CX(n, x0, x1, y, z, r, col, sec=24):
    m = tcyl(radius=r, height=x1 - x0, sections=sec)
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])); m.apply_translation([(x0 + x1) / 2, y, z]); return (n, m, C[col])
def CY(n, x, y0, y1, z, r, col, sec=24):
    m = tcyl(radius=r, height=y1 - y0, sections=sec)
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])); m.apply_translation([x, (y0 + y1) / 2, z]); return (n, m, C[col])
def pcb(n, w, h, t, r, holes, col):
    poly = sbox(0, 0, w, h).buffer(-r).buffer(r, resolution=6)
    for x, y, d in holes:
        poly = poly.difference(Point(x, y).buffer(d / 2, resolution=8))
    return (n, extrude_polygon(poly, t), C[col])
def smd(n, area, k, z, seed, avoid=()):
    """k kleine SMD-Teile (Kondensatoren/Widerstaende) zufaellig in area=(x0,y0,x1,y1), nicht in 'avoid'-Rechtecken."""
    rnd = random.Random(seed); out = []
    while len(out) < k:
        x = rnd.uniform(area[0], area[2]); y = rnd.uniform(area[1], area[3])
        if any(a[0] - 1 < x < a[2] + 1 and a[1] - 1 < y < a[3] + 1 for a in avoid): continue
        w, h = rnd.choice([(1.0, 0.5), (1.6, 0.8), (2.0, 1.25), (0.6, 0.3)])
        if rnd.random() < 0.5: w, h = h, w
        col = rnd.choice(["dark", "dark", "beige", "silver"])
        out.append(B(n, x, y, z, x + w, y + h, z + rnd.uniform(0.3, 0.8), col))
    return out
def winkel_pins(n, pts, richtung, z, lang=6.0):
    """90-Grad-Stifte: Pins (0,64 mm) von pts aus in 'richtung' (+x,-x,+y,-y), gold."""
    out = []
    dx, dy = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}[richtung]
    for (x, y, zz) in pts:
        x1, y1 = x + dx * lang, y + dy * lang
        out.append(B(n, min(x, x1) - 0.32 * (dx == 0), min(y, y1) - 0.32 * (dy == 0), zz - 0.32,
                     max(x, x1) + 0.32 * (dx == 0), max(y, y1) + 0.32 * (dy == 0), zz + 0.32, "gold"))
    return out

def raspberry_pi5():
    T = 1.6; L = []
    hole = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]
    L.append(pcb("Pi 5 Platine", 85, 56, T, 3.0, [(x, y, 2.75) for x, y in hole], "pcb_g"))
    for x, y in hole:   # Kupferringe
        ring = trimesh.creation.annulus(r_min=1.4, r_max=3.0, height=0.06, sections=24); ring.apply_translation([x, y, T + 0.03])
        L.append(("Pi Befestigungsloch", ring, C["gold"]))
    z = T
    L.append(B("Pi USB-C (Strom)", 6.75, -1.2, z, 15.65, 6.1, z + 3.2, "silver"))
    L.append(B("Pi USB-C Oeffnung", 7.6, -1.25, z + 0.7, 14.8, -1.15, z + 2.5, "black"))
    for i, cx in enumerate((25.8, 39.2)):
        L.append(B(f"Pi micro-HDMI {i}", cx - 3.3, -0.6, z, cx + 3.3, 7.4, z + 3.0, "silver"))
        L.append(B(f"Pi micro-HDMI {i}", cx - 2.6, -0.65, z + 0.6, cx + 2.6, -0.55, z + 2.4, "black"))
    L.append(B("Pi UART (JST)", 31.0, 0.8, z, 34.6, 4.6, z + 4.0, "white"))
    for i, cx in enumerate((46.2, 51.8)):
        L.append(B(f"Pi CAM/DISP {i}", cx - 1.8, 1.5, z, cx + 1.8, 17.5, z + 2.4, "beige"))
        L.append(B(f"Pi CAM/DISP {i}", cx - 1.9, 1.5, z + 2.4, cx + 1.9, 17.5, z + 2.9, "dark"))
    L.append(B("Pi SoC BCM2712", 21.0, 12.2, z, 36.6, 27.8, z + 1.5, "silver"))
    L.append(B("Pi RAM", 27.0, 31.0, z, 39.0, 45.0, z + 1.2, "black"))
    L.append(B("Pi RP1", 53.0, 28.0, z, 62.0, 37.0, z + 1.0, "black"))
    L.append(B("Pi PMIC", 15.0, 10.0, z, 20.0, 15.0, z + 0.9, "black"))
    L.append(B("Pi WLAN-Modul", 5.0, 40.0, z, 17.0, 48.0, z + 1.8, "silver"))
    L.append(B("Pi PCIe (FPC)", 0.5, 21.0, z, 4.3, 37.0, z + 2.2, "beige"))
    L.append(B("Pi Power-Knopf", 0.2, 15.5, z, 3.2, 19.5, z + 1.8, "dark"))
    L.append(CZ("Pi Power-Knopf", 1.7, 17.5, z + 1.8, z + 2.3, 0.9, "silver"))
    L.append(B("Pi LED rot (PWR)", 0.4, 9.0, z, 1.6, 10.0, z + 0.6, "red"))
    L.append(B("Pi LED gruen (ACT)", 0.4, 11.0, z, 1.6, 12.0, z + 0.6, "green"))
    L.append(B("Pi RTC-Batterie (J5)", 17.5, 3.5, z, 20.5, 8.0, z + 3.0, "white"))
    L.append(B("Pi J2 Power-Taster (2 Stifte nachgeruestet)", 21.6, 3.3, z, 24.0, 8.2, z + 2.5, "black"))
    L += [B("Pi J2 Stift", 22.5, y - 0.32, z + 2.5, 23.1, y + 0.32, z + 8.5, "gold") for y in (4.48, 7.02)]
    L.append(B("Pi PoE-Stifte", 55.0, 4.5, z, 60.0, 9.5, z + 2.5, "black"))
    L += winkel_pins("Pi PoE-Stifte", [(56.3 + i * 2.54, 5.8 + j * 2.54, z + 2.5) for i in range(2) for j in range(2)], "+y", z, 0)
    L.append(B("Pi Luefter-Anschluss (FAN)", 62.5, 44.5, z, 68.0, 49.0, z + 3.2, "white"))
    L.append(B("Pi Ethernet", 64.3, 2.6, z, 87.4, 18.6, z + 13.6, "silver"))
    L.append(B("Pi Ethernet Buchse", 87.35, 4.6, z + 1.5, 87.45, 16.6, z + 11.5, "black"))
    for cy, tongue in ((29.1, "blue"), (47.0, "black")):
        L.append(B("Pi USB-A " + ("3.0" if tongue == "blue" else "2.0"), 69.6, cy - 7.3, z, 87.6, cy + 7.3, z + 16.0, "silver"))
        for k in (0, 1):
            zz = z + 1.6 + k * 7.0
            L.append(B("Pi USB-A Oeffnung", 87.55, cy - 6.0, zz, 87.65, cy + 6.0, zz + 5.0, "black"))
            L.append(B("Pi USB-A Zunge", 80.0, cy - 5.6, zz + 2.6, 87.66, cy + 5.6, zz + 4.4, tongue))
    # 40-pol. Stiftleiste, abgewinkelt nach hinten (+y)
    # 40-pol. Stiftleiste, gerade (Serie): Stifte senkrecht nach oben, 8,5 mm ueber der Platine
    L.append(B("Pi GPIO-Leiste", 6.6, 49.95, z, 58.4, 55.05, z + 2.5, "black"))
    for n in range(1, 41):
        k = (n - 1) // 2; x = 7.87 + k * 2.54; y = 51.23 if n % 2 else 53.77
        L.append(B("Pi GPIO-Stift", x - 0.32, y - 0.32, z + 2.5, x + 0.32, y + 0.32, z + 8.5, "gold"))
    L.append(B("Pi microSD-Halter", 0.0, 21.0, -1.4, 12.5, 35.0, 0.0, "silver"))
    L.append(B("Pi microSD-Karte", -2.5, 22.5, -1.2, 11.0, 33.5, -0.5, [40, 40, 120, 255]))
    L += smd("Pi SMD", (4, 4, 62, 48), 70, z, 5, avoid=[(6, -2, 17, 8), (21, 12, 37, 28), (27, 31, 39, 45), (53, 28, 62, 37),
            (22, -1, 43, 8), (44, 1, 54, 18), (5, 40, 17, 48), (6, 49, 59, 55), (0, 9, 4, 38), (55, 4, 60, 10), (17, 3, 21, 8)])
    return L

def active_cooler():
    L = []; z0 = 1.6 + 1.5
    L.append(B("Active Cooler Grundplatte", 14.0, 6.0, z0, 58.0, 44.0, z0 + 1.5, [70, 72, 78, 255]))
    for i in range(14):
        x = 15.0 + i * 3.0
        L.append(B("Active Cooler Rippen", x, 6.0, z0 + 1.5, x + 1.0, 28.0, z0 + 7.5, [80, 82, 88, 255]))
    L.append(B("Active Cooler Luefter-Gehaeuse", 30.0, 26.0, z0 + 1.5, 58.0, 44.0, z0 + 7.5, "black"))
    L.append(CZ("Active Cooler Luefter", 44.0, 35.0, z0 + 7.5, z0 + 7.7, 7.5, "dark"))
    return L

def si4713_modul():
    """Lila FM-Modul 40 x 18 mm (wie Foto): Loecher Ø3 an der Hinterkante (y = 15, Abstand 33),
    gerade 11-pol. Stiftleiste zwischen den Loechern, Klinkenbuchse vorne am -x-Ende, ANT-Loetpunkt vorne am +x-Ende."""
    L = []; T = 1.6
    L.append(pcb("Si4713 FM-Modul", 40, 18, T, 1.5, [(3.5, 15.0, 3.1), (36.5, 15.0, 3.1)], "pcb_p"))
    L.append(B("Si4713 Klinkenbuchse 3,5 mm", 0.0, 1.0, T, 12.0, 8.0, T + 5.2, "black"))
    L.append(CX("Si4713 Klinkenbuchse", -0.8, 0.0, 4.5, T + 2.6, 2.6, "black"))
    L.append(B("Si4713 ANT-Loetpunkt", 35.0, 1.2, T, 38.0, 4.2, T + 0.3, "gold"))
    L.append(B("Si4713 Chip", 22.0, 5.0, T, 25.0, 8.0, T + 0.8, "black"))
    L.append(B("Si4713 Quarz", 27.5, 7.0, T, 30.7, 9.5, T + 0.9, "silver"))
    L.append(B("Si4713 Spannungsregler", 15.0, 4.0, T, 18.0, 6.5, T + 1.1, "black"))
    L.append(B("Si4713 Stiftleiste (11-pol.)", 6.0, 14.7, T, 33.94, 17.3, T + 2.5, "black"))
    L += [B("Si4713 Stift", 7.27 + i * 2.54 - 0.32, 16.0 - 0.32, T + 2.5, 7.27 + i * 2.54 + 0.32, 16.0 + 0.32, T + 8.5, "gold") for i in range(11)]
    L += smd("Si4713 SMD", (13, 1, 34, 12), 14, T, 11, avoid=[(22, 5, 25, 8), (27.5, 7, 30.7, 9.5), (15, 4, 18, 6.5), (35, 1, 38, 4.2)])
    return L

def oled_13():
    """1,3"-OLED: Platine 35,4 x 33,5, Loecher Ø2,2 (30,4 x 28,4), Stiftleiste oben (y max), Glas mittig."""
    L = []; T = 1.2; w, h = 35.4, 33.5
    hx, hy = (w - 30.4) / 2, (h - 28.4) / 2
    L.append(pcb("OLED Platine", w, h, T, 1.0, [(hx, hy, 2.2), (w - hx, hy, 2.2), (hx, h - hy, 2.2), (w - hx, h - hy, 2.2)], "pcb_b"))
    L.append(B("OLED Glas", 0.5, 5.2, T, 34.9, 28.0, T + 1.4, [40, 44, 52, 255]))
    L.append(B("OLED Anzeigeflaeche", 3.0, 9.0, T + 1.41, 32.4, 23.7, T + 1.45, "glass"))
    L.append(B("OLED Flexkabel", 0.0, 9.0, -0.3, 1.2, 24.0, T + 1.4, [190, 140, 40, 255]))
    L.append(B("OLED Stiftleiste (90 Grad)", 12.8, 30.4, -2.6, 22.6, 32.9, 0.0, "black"))
    L += winkel_pins("OLED Stift", [(14.06 + i * 2.54, 31.6, -1.3) for i in range(4)], "+y", 0, 6.0)
    return L

def ky022():
    """IR-Empfaenger KY-022: Platine 15 x 19,3 (lokal: Linsenseite bei x = 19,3), Empfaenger stehend, Stifte bei x = 0 nach -x."""
    L = []; T = 1.6
    L.append(pcb("IR Platine (KY-022)", 19.3, 15.0, T, 0.8, [(17.1, 2.0, 3.0), (17.1, 13.0, 3.0)], "pcb_k"))
    L.append(B("IR Empfaenger (Abschirmung)", 11.0, 4.0, T, 15.2, 11.0, T + 8.5, "silver"))
    L.append(CX("IR Empfaenger Linse", 15.2, 16.4, 7.5, T + 5.9, 2.1, "black", 20))
    L.append(B("IR LED", 6.0, 11.5, T, 7.6, 12.3, T + 0.6, "red"))
    L.append(B("IR Widerstand", 6.0, 2.5, T, 7.6, 3.3, T + 0.5, "dark"))
    L.append(B("IR Stiftleiste (90 Grad)", 0.0, 3.6, T, 2.6, 11.4, T + 2.6, "black"))
    L += winkel_pins("IR Stift", [(0.0, 7.5 + k * 2.54, T + 1.3) for k in (-1, 0, 1)], "-x", T, 6.0)
    return L

def sabrent_dac():
    """USB-Soundkarte (Sabrent): Stecker bei x = 0..12, Koerper bis x = 50, Klinken an der Stirnseite."""
    L = []
    L.append(B("DAC USB-Stecker", 0.0, -6.0, -2.25, 12.0, 6.0, 2.25, "silver"))
    L.append(B("DAC Gehaeuse (Sabrent)", 12.0, -10.5, -5.5, 50.0, 10.5, 5.5, "black"))
    for y, ring in ((-4.5, "lime"), (4.5, "pink")):
        L.append(CX("DAC Klinke " + ("Kopfhoerer" if ring == "lime" else "Mikrofon"), 50.0, 50.6, y, 0.0, 3.2, ring))
        L.append(CX("DAC Klinke", 50.0, 50.7, y, 0.0, 1.8, "black"))
    return L

def place(L, dx, dy, dz, rotz=0.0, flipz=False):
    out = []
    for n, m, c in L:
        m = m.copy()
        if rotz: m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rotz), [0, 0, 1]))
        m.apply_translation([dx, dy, dz]); out.append((n, m, c))
    return out
