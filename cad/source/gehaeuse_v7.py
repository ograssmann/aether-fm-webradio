"""Gehäuse V7 (Waermeeinsaetze M2 fuer alle Schrauben, Kette hoch auf Klemm-Wiegen, Si4713 unter der Kette, grosses Seitenfenster am Pi) – basiert auf V6 (geraeumiger: 215 x 95,5 x 42; Daempfer-Kette laengs an der Rueckwand in Saetteln mit Kabelbinder,
Si4713-Modul direkt hinter der Kette; OLED auf Saeulen vom Boden hinter Deckelfenster; IR hinter rechter Seitenwand, Taster in Frontwand; Deckel frei): Pi 5 + Si4713-Modul + Sabrent-USB-Soundkarte innen. Masse in mm."""
import json
from csg import box, cyl, union_all, write_stl_clean

W, F = 2.0, 3.0   # V7d: Boden 3 mm (weniger Material = weniger Verzug), innen flach
BOARD_X, BOARD_Y, BOARD_T = 85.0, 56.0, 1.6
GAP = 1.5
EX_TARGET, EZ_TARGET = 215.0, 42.0   # V6: laenger: Kette + Modul in einer Reihe, Platz fuer Soundkarte + 3,5-mm-Stecker
MODULE_ZONE = 34.0    # V6: 8 mm mehr Tiefe -> Platz zum Schrauben zwischen Pi und Modul/Kette
IH = EZ_TARGET - F
PAD, STAND = 8.0, 0.0   # V6c: Pi auf 8 mm hohen gedruckten Tuermchen (3 mm hoeher als V6b), Schrauben M2,5 von oben (keine Messingbolzen)
HOLES = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]
MOD_DX = 33.0   # Abstand der zwei Modul-Befestigungslöcher (aus Foto, bitte nachmessen)
# V7: Gewinde-Einschmelzmuttern (ein Typ fuer alles, gemessen ca. 3,2 mm aussen -> M2)
INS_D, INS_T, BOSS_R = 3.2, 6.0, 3.4      # V7g: Bohrung Ø 3,2 (gedruckt ca. 3,0) und 6 mm tief - 2,9/5 war zu eng und zu kurz
INS_FASE, INS_RAUM_D, INS_RAUM_T = 0.5, 3.6, 1.5   # Einfuehrung oben Ø 3,6 x 0,5; Freiraum unten Ø 3,6 x 1,5 fuer verdraengtes PLA

IX = EX_TARGET - 2 * W
IY = GAP + BOARD_Y + MODULE_ZONE
EX, EY, EZ = IX + 2 * W, IY + 2 * W, F + IH
BX, BY = W + GAP, W + GAP
BZ0 = F + PAD + STAND
BZ1 = BZ0 + BOARD_T

# ----- Design: abgerundete Ecken, Fase unten, Zierfuge, Waben mit Verlauf -----
import math
R_ECK, FASE = 8.0, 0.8
from csg import Solid, Poly, V
def rrect(x0, y0, x1, y1, z0, z1, r, seg=10):
    """Abgerundetes Rechteck als ein konvexes Prisma (keine Naehte). seg = Segmente pro Viertelkreis."""
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg); pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    polys = [Poly([V(x, y, z1) for x, y in pts]), Poly([V(x, y, z0) for x, y in reversed(pts)])]
    n = len(pts)
    for i in range(n):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
        polys.append(Poly([V(ax, ay, z0), V(bx, by, z0), V(bx, by, z1), V(ax, ay, z1)]))
    return Solid(polys)
def waben(mitte, halb, pitch, rmax, rmin, achse, wand, dr=0.0, off=(0.0, 0.0)):
    """Wabenfeld mit Verlauf: Loecher in der Mitte gross, zum Rand klein. achse 'z' (Boden/Deckel) oder 'x' (Seitenwand)."""
    (cu, cv), (hu, hv) = mitte, halb
    out = []
    du, dv = pitch * math.sqrt(3) / 2, pitch
    i = 0
    u = cu - hu
    while u <= cu + hu + 1e-6:
        v = cv - hv + (pitch / 2 if i % 2 else 0)
        while v <= cv + hv + 1e-6:
            d = math.hypot((u - cu) / hu, (v - cv) / hv)
            if d <= 1.0:
                r = rmin + (rmax - rmin) * (1 - d * d)
                if achse == 'z':
                    out.append(cyl((u + off[0], v + off[1], wand[0]), (u + off[0], v + off[1], wand[1]), r + dr, 6))
                else:   # Seitenwand: u = z, v = y
                    out.append(cyl((wand[0], v, u), (wand[1], v, u), r, 6))
            v += dv
        u += du; i += 1
    return out
FASE_B = 0.4   # V7d: kleine Fase unten, damit die Ecken voll auf der Platte haften
outer = rrect(FASE_B, FASE_B, EX - FASE_B, EY - FASE_B, 0, FASE_B + 0.01, R_ECK - FASE_B).union(rrect(0, 0, EX, EY, FASE_B, EZ, R_ECK))
base = outer.subtract(rrect(W, W, EX - W, EY - W, F, EZ + 1, R_ECK - W))
# Zierfuge rundum 6 mm unter der Oberkante (1 mm breit, 0,6 mm tief)
FUGE_Z = EZ - 6.25
base = base.subtract(rrect(-1, -1, EX + 1, EY + 1, FUGE_Z - 0.5, FUGE_Z + 0.5, R_ECK + 1).subtract(
    rrect(0.6, 0.6, EX - 0.6, EY - 0.6, FUGE_Z - 1, FUGE_Z + 1, R_ECK - 0.6)))
CH_Y = EY - W - 14.0          # Achse Daempfer-Kette und Modul-Mitte (Reihe an der Rueckwand)
CH_Z = F + 22.0               # V7: Kette hoch, darunter hat das Si4713-Modul Platz
CH_R = 6.4                    # Radius Mulde in den Saetteln
SADDLES = [EX - 36.0]   # V7h: nur noch 1 Daempfer (10 dB) -> 1 Wiege darunter; vorne frei fuer den schwarzen F-Stecker
CLIP_D = 10.8                      # Innen-Ø der Klemmwiege = Daempferkoerper (bitte nachmessen)
CHAIN_L, PIGTAIL, MOD_L = 110.0, 5.0, 40.0    # Laenge Durchfuehrung+2 Daempfer+F-Stecker, Abstand zum Modul, Modul (Langloch +-6 mm zum Anpassen)
MOD_X0 = EX - W - CHAIN_L - 8.0 - 30.0   # V7g: Modul 30 mm weiter nach hinten, nicht mehr unter dem F-Stecker (war zu eng); Loecher bei MOD_X0 und +MOD_DX
MOD = [(MOD_X0, CH_Y), (MOD_X0 + MOD_DX, CH_Y)]
F_D = 10.0                    # F-Durchfuehrung (Superbat) in der rechten Stirnwand
TA_X, TA_Z, TA_D = EX - 20.0, F + 17.0, 12.2     # V6b: 12-mm-Metalltaster in der Frontwand rechts (an J2), Deckel frei
cuts = [
    cyl((EX - W - 1, CH_Y, CH_Z), (EX + 1, CH_Y, CH_Z), F_D / 2, 48),  # rechts: F-Durchfuehrung auf Kettenachse
]
cuts += waben((BX + 37, BY + 28), (22, 15), 5.5, 2.4, 1.1, 'z', (-1, F + 0.5))          # Boden unter dem Pi
cuts += waben((F + 18, BY + 29), (7.5, 17), 5.0, 1.9, 0.9, 'x', (EX - W - 1, EX + 1))    # rechte Seitenwand
# V6c: vorne nur USB-C (Langloch 13 x 8 mm, Mitte Pi-x 11,2 / Steckermitte 1,6 mm ueber Platine); HDMI bleibt zu
USBC_X, USBC_Z, USBC_B, USBC_H = BX + 11.2, BZ1 + 1.6, 16.0, 10.0
cuts += [box(USBC_X - USBC_B / 2 + USBC_H / 2, -1, USBC_Z - USBC_H / 2, USBC_X + USBC_B / 2 - USBC_H / 2, W + 1, USBC_Z + USBC_H / 2)]
cuts += [cyl((USBC_X + s * (USBC_B / 2 - USBC_H / 2), -1, USBC_Z), (USBC_X + s * (USBC_B / 2 - USBC_H / 2), W + 1, USBC_Z), USBC_H / 2, 32) for s in (-1, 1)]
# V6c: linke Wand: microSD-Schlitz direkt unter der Platine (Karte Pi-y 22-34) und LED-Schlitz direkt ueber der Platine
# V7: ein grosses Fenster an der Schmalseite: microSD (unter der Platine), Power-Knopf + LEDs (darueber) erreichbar
def rr_x(x0, x1, y0, y1, z0, z1, r, seg=8):
    pts = []
    for cy, cz, a0 in ((y1 - r, z0 + r, -90), (y1 - r, z1 - r, 0), (y0 + r, z1 - r, 90), (y0 + r, z0 + r, 180)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg); pts.append((cy + r * math.cos(a), cz + r * math.sin(a)))
    polys = [Poly([V(x1, y, z) for y, z in pts]), Poly([V(x0, y, z) for y, z in reversed(pts)])]
    for i in range(len(pts)):
        (ay, az), (by, bz) = pts[i], pts[(i + 1) % len(pts)]
        polys.append(Poly([V(x0, ay, az), V(x0, by, bz), V(x1, by, bz), V(x1, ay, az)]))
    return Solid(polys)
PI_FENSTER = (BY + 5.5, BY + 42.0, BZ0 - 4.5, BZ1 + 7.0)    # y0, y1, z0, z1 (Pi-y 5,5..42, frei von der Gehaeuse-Rundung)
cuts.append(rr_x(-1, W + 1, *PI_FENSTER, 3.0))
base = base.subtract(union_all(cuts))
# Pi-Tuermchen 5 mm, Ø 6, Kernloch fuer M2,5-Blechschraube (bzw. Gewinde M2,5 schneiden) von oben
def dome(pts, z_top, r=BOSS_R):
    return union_all([cyl((x, y, F - 0.5), (x, y, z_top), r, 32) for x, y in pts])
def einsatz(pts, z_top):
    """Loch fuer Gewinde-Einschmelzmutter M2: Bohrung + Einfuehrung oben + breiterer Freiraum unten (geschmolzenes PLA)."""
    teile = []
    for x, y in pts:
        boden = z_top - INS_T
        teile.append(cyl((x, y, boden), (x, y, z_top + 1), INS_D / 2, 24))                 # Bohrung fuer den Einsatz
        teile.append(cyl((x, y, z_top - INS_FASE), (x, y, z_top + 1), INS_RAUM_D / 2, 24))  # Einfuehrung
        unten = max(0.8, boden - INS_RAUM_T)                                                # mind. 0,8 mm Boden bleibt
        if unten < boden:
            teile.append(cyl((x, y, unten), (x, y, boden + 0.01), INS_RAUM_D / 2, 24))      # Freiraum unter dem Einsatz
    return union_all(teile)
PI_P = [(BX + x, BY + y) for x, y in HOLES]
base = base.union(dome(PI_P, F + PAD)).subtract(einsatz(PI_P, F + PAD))
# Saettel fuer die Daempfer-Kette: Mulde + Tunnel quer fuer einen Kabelbinder (bis 4,5 mm breit)
# V7b: offene V-Wiegen mit Kabelbinder-Tunnel (nimmt Daempfer-Ø ca. 9-13 mm auf, Kabelbinder bis 4,8 mm breit)
def v_prisma(x0, x1, yc, z_spitze, z_oben, halb):
    pts = [(yc - halb, z_oben), (yc, z_spitze), (yc + halb, z_oben)]
    pts = [(yc - halb - 0.01, z_oben + 5), (yc - halb, z_oben), (yc, z_spitze), (yc + halb, z_oben), (yc + halb + 0.01, z_oben + 5)]
    polys = [Poly([V(x1, y, z) for y, z in pts]), Poly([V(x0, y, z) for y, z in reversed(pts)])]
    for i in range(len(pts)):
        (ay, az), (by, bz) = pts[i], pts[(i + 1) % len(pts)]
        polys.append(Poly([V(x0, ay, az), V(x0, by, bz), V(x1, by, bz), V(x1, ay, az)]))
    return Solid(polys)
CR = CLIP_D / 2
V_SPITZE = CH_Z - CR * math.sqrt(2)        # 90-Grad-V: Achse liegt bei Nenn-Ø genau auf CH_Z
V_OBEN = CH_Z - 1.0                        # Wiege endet unter der Achse -> oben offen
V_HALB = V_OBEN - V_SPITZE                 # halbe V-Breite oben
for sx in SADDLES:
    sad = box(sx - 4, CH_Y - V_HALB - 2.5, F - 0.5, sx + 4, CH_Y + V_HALB + 2.5, V_OBEN)
    sad = sad.subtract(v_prisma(sx - 5, sx + 5, CH_Y, V_SPITZE, V_OBEN, V_HALB))
    sad = sad.subtract(box(sx - 2.5, CH_Y - V_HALB - 4, V_SPITZE - 3.6, sx + 2.5, CH_Y + V_HALB + 4, V_SPITZE - 1.6))   # Kabelbinder-Tunnel
    sad = sad.subtract(box(sx - 5, CH_Y - V_HALB + 1.0, F + 3.0, sx + 5, CH_Y + V_HALB - 1.0, V_SPITZE - 5.5))          # Fenster spart Material
    base = base.union(sad)
# V7: Si4713-Modul auf 2 Domen mit Einsaetzen unter dem Kettenende
MOD_Z = F + 5.0
MOD_P = [(MOD_X0, CH_Y), (MOD_X0 + MOD_DX, CH_Y)]
base = base.union(dome(MOD_P, MOD_Z)).subtract(einsatz(MOD_P, MOD_Z))

# Deckel (Druckorientierung: Platte unten, Lippe oben)
c, LT, LH = 0.2, 1.6, 5.0
lid = rrect(FASE, FASE, EX - FASE, EY - FASE, 0, FASE + 0.01, R_ECK - FASE).union(rrect(0, 0, EX, EY, FASE, 2.0, R_ECK))  # Fase oben (Druck: unten)
lip = rrect(W + c, W + c, EX - W - c, EY - W - c, 1.99, 2 + LH, R_ECK - W - c).subtract(
      rrect(W + c + LT, W + c + LT, EX - W - c - LT, EY - W - c - LT, 1, 2 + LH + 1, R_ECK - W - c - LT))
lid = lid.union(lip)
# Rastverbindung: Wulst aussen an der Lippe (lange Seiten), Rille innen in der Wand
RZ, RH, RD = 3.0, 1.0, 0.6            # Wulst-Mitte 3 mm unter Oberkante, 1 mm hoch, 0.6 mm vorstehend
x0, x1 = EX * 0.15, EX * 0.85
lz0, lz1 = 2 + RZ - RH / 2, 2 + RZ + RH / 2
ridges = [box(x0, W + c - RD, lz0, x1, W + c + 0.01, lz1),
          box(x0, EY - W - c - 0.01, lz0, x1, EY - W - c + RD, lz1)]
lid = lid.union(union_all(ridges))
gz0, gz1 = EZ - RZ - 0.7, EZ - RZ + 0.7
grooves = [box(x0 - 2, W - 0.9, gz0, x1 + 2, W + 0.01, gz1),
           box(x0 - 2, EY - W - 0.01, gz0, x1 + 2, EY - W + 0.9, gz1)]
base = base.subtract(union_all(grooves))
# ----- V6: 1,3"-OLED im Deckel, vorne links ueber dem flachen Teil des Pi (Druckkoordinaten: y gespiegelt) -----
def py(y): return EY - y
ROW_Y = 24.0                       # montiert: OLED-Mitte 24 mm hinter der Frontkante
OX = EX - 45.0                     # vorne rechts ueber dem Kabelbogen (dort keine hohen Bauteile)
OLED_HX, OLED_HY = 30.4, 28.4      # Lochabstand Befestigungsloecher (gemessen 14.11.)
WIN_W, WIN_H = 31.0, 16.5          # Sichtfenster (aktive Flaeche 29,4 x 14,7)
O_BOSS_H, O_BOSS_R, O_PILOT_R = 2.2, 2.6, 0.8
oh = [(OX + sx * OLED_HX / 2, py(ROW_Y) + sy * OLED_HY / 2) for sx in (-1, 1) for sy in (-1, 1)]
# V6b: OLED NICHT am Deckel, sondern auf 4 Saeulen vom Boden (Deckel bleibt frei abnehmbar)
GLAS_H = 1.8                       # Glas+Rahmen ueber der Platine (nachmessen)
OLED_PCB_Z = EZ - 0.3 - GLAS_H - 1.6   # Unterseite Platine: Glas 0,3 mm unter dem Deckel
oh_b = [(OX + sx * OLED_HX / 2, ROW_Y + sy * OLED_HY / 2) for sx in (-1, 1) for sy in (-1, 1)]
posts = [cyl((x, y, F - 0.5), (x, y, OLED_PCB_Z), BOSS_R, 32) for x, y in oh_b]
# Fuesse + Stege am Boden (nur unten, damit Stiftleiste/Dupont frei bleiben)
for sy in (-1, 1):
    y = ROW_Y + sy * OLED_HY / 2
    posts.append(box(OX - OLED_HX / 2, y - 1.2, F - 0.5, OX + OLED_HX / 2, y + 1.2, F + 8))
for sx in (1,):                    # nur rechter Quersteg: links Platz fuer den Winkelstecker der Soundkarte
    x = OX + sx * OLED_HX / 2
    posts.append(box(x - 1.2, ROW_Y - OLED_HY / 2, F - 0.5, x + 1.2, ROW_Y + OLED_HY / 2, F + 8))
base = base.union(union_all(posts))
base = base.subtract(einsatz(oh_b, OLED_PCB_Z))
lid = lid.subtract(box(OX - WIN_W / 2, py(ROW_Y) - WIN_H / 2, -1, OX + WIN_W / 2, py(ROW_Y) + WIN_H / 2, 3))
# ===== Zweifarbig: Akzentlage (weiss/grau) im Deckel ab Z = AKZENT (Druck: Deckel kopfueber) =====
AKZENT = 0.6        # alles, was 0,6 mm tief ins Deckel-Schwarz geht, zeigt die Akzentfarbe
lid = lid.subtract(box(OX - WIN_W / 2 - 1.2, py(ROW_Y) - WIN_H / 2 - 1.2, -1, OX + WIN_W / 2 + 1.2, py(ROW_Y) + WIN_H / 2 + 1.2, AKZENT))  # Akzent-Rahmen ums Display
# Waben mit Verlauf + Versatz: Oberflaechen-Wabe groesser und verschoben -> Akzent-Sichel (wie Lichtkante) in jeder Wabe
W_MITTE, W_HALB = (42, py(56)), (38, 26)     # V6e: gross, hinter der Signal-Welle, ueber Pi und Lueftergegend
lid = lid.subtract(union_all(waben(W_MITTE, W_HALB, 5.5, 2.2, 0.9, 'z', (-1, 3))))
lid = lid.subtract(union_all(waben(W_MITTE, W_HALB, 5.5, 2.2, 0.9, 'z', (-1, AKZENT), dr=0.3, off=(0.3, 0.2))))
# V6c: IR-Empfaenger (KY-022, Empfaenger stehend, Linse seitlich) hinter der rechten Seitenwand, Fenster in der Wand
IR_Y, IR_LINSE_Z = 60.0, F + 23.0                 # Linsenmitte (montiert)
IR_LINSE_H, IR_LOCH_DX, IR_RAND = 6.0, 11.1, 2.2  # Linsenmitte ueber Platine, Lochabstand, Lochreihe -> Platinenkante
IR_PCB_Z = IR_LINSE_Z - IR_LINSE_H - 1.6          # Unterseite Platine
IR_KANTE_X = EX - W - 1.0                         # Platinenkante (Linsenseite) 1 mm vor der Wand
ir_h = [(IR_KANTE_X - IR_RAND, IR_Y + sy * IR_LOCH_DX / 2) for sy in (-1, 1)]
ir_posts = [cyl((x, y, F - 0.5), (x, y, IR_PCB_Z), BOSS_R, 32) for x, y in ir_h]
ir_posts.append(box(ir_h[0][0] - 1.2, ir_h[0][1], F - 0.5, ir_h[0][0] + 1.2, ir_h[1][1], F + 8))
base = base.union(union_all(ir_posts))
base = base.subtract(einsatz(ir_h, IR_PCB_Z))
IR_FW, IR_FH = 16.0, 10.0   # Fenster breit x hoch (Linse ca. 9 mm hinter Aussenwand -> ca. +-40 Grad seitlich)
base = base.subtract(union_all([box(EX - W - 1, IR_Y - IR_FW / 2 + IR_FH / 2, IR_LINSE_Z - IR_FH / 2, EX + 1, IR_Y + IR_FW / 2 - IR_FH / 2, IR_LINSE_Z + IR_FH / 2)]
    + [cyl((EX - W - 1, IR_Y + sy * (IR_FW / 2 - IR_FH / 2), IR_LINSE_Z), (EX + 1, IR_Y + sy * (IR_FW / 2 - IR_FH / 2), IR_LINSE_Z), IR_FH / 2, 40) for sy in (-1, 1)]))
# Taster im Deckel
base = base.subtract(cyl((TA_X, -1, TA_Z), (TA_X, W + 1, TA_Z), TA_D / 2, 48))
# V6d: Clip fuer das Dupont-Buendel (Kanal laengs x, 10 mm breit, 9 mm hoch, Rastnasen oben)
def clip(cx, cy, b=10.0, h=9.0, l=8.0, t=1.6):
    teile = []
    for s in (-1, 1):
        y0 = cy + s * b / 2
        teile.append(box(cx - l / 2, min(y0, y0 + s * t), F - 0.5, cx + l / 2, max(y0, y0 + s * t), F + h))
        teile.append(box(cx - l / 2, min(y0, y0 - s * 1.0), F + h - 1.2, cx + l / 2, max(y0, y0 - s * 1.0), F + h))   # Nase 1 mm
    return union_all(teile)
CLIP_POS = (160.0, 60.0)
base = base.union(clip(*CLIP_POS))
# V6d: 4 Vertiefungen fuer Klebe-Gummifuesse Ø 10 mm (1 mm tief)
FUSS = [(14.0, 14.0), (EX - 14.0, 14.0), (14.0, EY - 14.0), (EX - 14.0, EY - 14.0)]
# V7d: keine Vertiefungen mehr fuer die Fuesse (sie nahmen den Ecken die Haftung) - Klebefuesse direkt aufkleben
print("Modul:", MOD_P, "OLED x:", OX, "IR y/z (rechte Wand):", IR_Y, IR_LINSE_Z, "Taster x/z (Front):", TA_X, TA_Z, "Kette y/z:", round(CH_Y, 1), CH_Z, "Saettel x:", SADDLES)

# V6d: Schrift als buendige Einlage (eigenes Teil fuer Bambu Studio: Tasche im Deckel + passender Schriftkoerper)
from schrift import text_solid
NAME, NAME_H, NAME_X, NAME_Y = "\u00c6THER 102.3", 5.0, 120.0, ROW_Y
tasche, _ = text_solid(NAME, NAME_X, NAME_Y, NAME_H, -1.0, AKZENT, spiegel_y=EY)
schrift, _ = text_solid(NAME, NAME_X, NAME_Y, NAME_H, 0.0, AKZENT, spiegel_y=EY)
# Signal-Welle, die in den Namen laeuft (Sinus mit wachsender Amplitude, Linie 0,8 mm) - ebenfalls Einlage
def linie(pts, b, z0, z1):
    from schrift import _prism
    L, R = [], []
    for i, (x, y) in enumerate(pts):
        xa, ya = pts[max(i - 1, 0)]; xb, yb = pts[min(i + 1, len(pts) - 1)]
        dx, dy = xb - xa, yb - ya; n = math.hypot(dx, dy); nx, ny = -dy / n * b / 2, dx / n * b / 2
        L.append((x + nx, y + ny)); R.append((x - nx, y - ny))
    return _prism(L + R[::-1], z0, z1)
WELLE_X0, WELLE_X1, LAMBDA = 14.0, NAME_X - 28.5, 6.0
WELLE = []
for i in range(201):
    x = WELLE_X0 + (WELLE_X1 - WELLE_X0) * i / 200
    t = (x - WELLE_X0) / (WELLE_X1 - WELLE_X0)
    WELLE.append((x, py(NAME_Y + 2.6 * t * t * math.sin(2 * math.pi * (x - WELLE_X0) / LAMBDA))))
tasche = tasche.union(linie(WELLE, 0.8, -1.0, AKZENT))
schrift = schrift.union(linie(WELLE, 0.8, 0.0, AKZENT))
lid = lid.subtract(tasche)
write_stl_clean(schrift, "Gehaeuse_V7_Deckel_Schrift.stl", "Schrift")
# ----- V7c: Rastdeckel fuer das Pi-Fenster (eigenes Druckteil, Druck: Aussenseite unten) -----
# Druckkoordinaten: X = Fensterbreite (y), Y = Fensterhoehe (z), Z = 0 Aussenflaeche -> + nach innen
FW, FH = PI_FENSTER[1] - PI_FENSTER[0], PI_FENSTER[3] - PI_FENSTER[2]
RAND, FL, SP = 1.2, 1.0, 0.15            # Flanschrand, Flanschdicke, Spiel im Fenster
def wedge_y(y0, y1, pts):                # Prisma laengs Y aus Polygon (x, z)
    polys = [Poly([V(x, y1, z) for x, z in pts]), Poly([V(x, y0, z) for x, z in reversed(pts)])]
    for i in range(len(pts)):
        (ax, az), (bx, bz) = pts[i], pts[(i + 1) % len(pts)]
        polys.append(Poly([V(ax, y0, az), V(bx, y0, bz), V(bx, y1, bz), V(ax, y1, az)]))
    return Solid(polys)
x0, y0 = RAND, RAND
klappe = rrect(0, 0, FW + 2 * RAND, FH + 2 * RAND, 0, FL, 3.0 + RAND)                       # Flansch aussen
ring = rrect(x0 + SP, y0 + SP, x0 + FW - SP, y0 + FH - SP, FL - 0.01, FL + W, 3.0 - SP)      # Kragen im Fenster
ring = ring.subtract(rrect(x0 + SP + 1.0, y0 + SP + 1.0, x0 + FW - SP - 1.0, y0 + FH - SP - 1.0, FL - 0.5, FL + W + 1, 2.0))
klappe = klappe.union(ring)
yc = y0 + FH / 2
def wedge_x(x0_, x1_, pts):              # Prisma laengs X aus Polygon (y, z)
    polys = [Poly([V(x1_, y, z) for y, z in pts]), Poly([V(x0_, y, z) for y, z in reversed(pts)])]
    for i in range(len(pts)):
        (ay, az), (by, bz) = pts[i], pts[(i + 1) % len(pts)]
        polys.append(Poly([V(x0_, ay, az), V(x0_, by, bz), V(x1_, by, bz), V(x1_, ay, az)]))
    return Solid(polys)
xc = x0 + FW / 2
for s, ya in ((1, y0 + SP), (-1, y0 + FH - SP)):          # 2 Rasthaken an den Laengsseiten (oben/unten), frei von der Pi-Platine
    yi = ya + s * 1.0
    arm = box(xc - 4, min(yi, yi + s * 1.2), FL, xc + 4, max(yi, yi + s * 1.2), FL + W + 2.6)
    pts = [(yi, FL + W + 0.15), (yi - s * 0.7, FL + W + 0.15), (yi, FL + W + 2.4)]
    nase = wedge_x(xc - 4, xc + 4, pts if s < 0 else pts[::-1])
    klappe = klappe.union(arm).union(nase)
    for xs in (xc - 4.6, xc + 4.0):                       # Schlitze neben dem Arm -> Arm federt
        klappe = klappe.subtract(box(xs, min(yi - s * 0.01, yi + s * 1.3), FL + W - 0.6, xs + 0.6, max(yi - s * 0.01, yi + s * 1.3), FL + W + 3))
klappe = klappe.subtract(box(-1, (FH + 2 * RAND) / 2 - 4, -1, 1.6, (FH + 2 * RAND) / 2 + 4, 0.6))   # Griffmulde an der vorderen Schmalseite
write_stl_clean(klappe, "Gehaeuse_V7_Seitendeckel.stl", "Seitendeckel")
n1 = write_stl_clean(base, "Gehaeuse_V7_Unterteil.stl", "Unterteil")
n2 = write_stl_clean(lid, "Gehaeuse_V7_Deckel.stl", "Deckel")
print(json.dumps(dict(aussen=[round(EX,1), round(EY,1), EZ], tris=[n1, n2])))
