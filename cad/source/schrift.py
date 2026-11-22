"""Text -> CSG-Prismen (fuer vertiefte Schrift). Nutzt matplotlib TextPath (DejaVu Sans Bold)."""
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from csg import Solid, Poly, V, union_all


def _area(p):
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p))) / 2


def _inside(pt, poly):
    x, y = pt; c = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _earcut(p):
    """Ear clipping fuer ein einfaches Polygon (CCW). Liefert Dreiecke."""
    idx = list(range(len(p))); tris = []
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    guard = 0
    while len(idx) > 3 and guard < 100000:
        guard += 1; found = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = p[i0], p[i1], p[i2]
            if cross(a, b, c) <= 1e-12: continue
            ok = True
            for j in idx:
                if j in (i0, i1, i2): continue
                q = p[j]
                if cross(a, b, q) >= 0 and cross(b, c, q) >= 0 and cross(c, a, q) >= 0:
                    ok = False; break
            if ok:
                tris.append((a, b, c)); idx.pop(k); found = True; break
        if not found:
            idx.pop(0)   # degeneriert: Punkt verwerfen
    if len(idx) == 3: tris.append(tuple(p[i] for i in idx))
    return tris


def _prism(poly, z0, z1):
    if _area(poly) < 0: poly = poly[::-1]
    polys = []
    for a, b, c in _earcut(poly):
        polys.append(Poly([V(a[0], a[1], z1), V(b[0], b[1], z1), V(c[0], c[1], z1)]))
        polys.append(Poly([V(c[0], c[1], z0), V(b[0], b[1], z0), V(a[0], a[1], z0)]))
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        polys.append(Poly([V(a[0], a[1], z0), V(b[0], b[1], z0), V(b[0], b[1], z1), V(a[0], a[1], z1)]))
    return Solid(polys)


def text_solid(txt, cx, cy, hoehe, z0, z1, spiegel_y=None, sperren=0.0):
    """Text zentriert um (cx, cy), Versalhoehe ca. hoehe mm. spiegel_y: y -> spiegel_y - y (Deckel liegt beim Druck verkehrt)."""
    fp = FontProperties(family="DejaVu Sans", weight="bold")
    tp = TextPath((0, 0), txt, size=hoehe / 0.73, prop=fp)
    polys = [[(float(x), float(y)) for x, y in p[:-1]] for p in tp.to_polygons(closed_only=True) if len(p) > 3]
    # zusammenfallende Punkte entfernen
    clean = []
    for p in polys:
        q = [p[0]]
        for pt in p[1:]:
            if abs(pt[0] - q[-1][0]) + abs(pt[1] - q[-1][1]) > 1e-4: q.append(pt)
        if len(q) >= 3 and abs(_area(q)) > 1e-3: clean.append(q)
    xs = [x for p in clean for x, _ in p]; ys = [y for p in clean for _, y in p]
    dx, dy = cx - (min(xs) + max(xs)) / 2, cy - (min(ys) + max(ys)) / 2
    clean = [[(x + dx, y + dy) for x, y in p] for p in clean]
    if spiegel_y is not None:
        clean = [[(x, spiegel_y - y) for x, y in p] for p in clean]
    # Aussenkonturen und Loecher trennen (Loch = liegt in einer anderen Kontur)
    outers, holes = [], []
    for i, p in enumerate(clean):
        depth = sum(1 for j, o in enumerate(clean) if j != i and abs(_area(o)) > abs(_area(p)) and _inside(p[0], o))
        (holes if depth % 2 else outers).append(p)
    glyphs = []
    for o in outers:
        s = _prism(o, z0, z1)
        hs = [h for h in holes if _inside(h[0], o)]
        if hs:
            s = s.subtract(union_all([_prism(h, z0 - 0.5, z1 + 0.5) for h in hs]))
        glyphs.append(s)
    return union_all(glyphs), (max(xs) - min(xs), max(ys) - min(ys))
