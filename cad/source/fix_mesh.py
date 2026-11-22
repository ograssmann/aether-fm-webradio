"""Schliesst kleine Loecher (offene Kanten) in einer STL: Randschleifen suchen und mit Dreiecksfaecher fuellen."""
import struct, sys, collections
def lade(p):
    d = open(p, 'rb').read(); n = struct.unpack('<I', d[80:84])[0]
    return [struct.unpack('<12f', d[84 + i * 50:84 + i * 50 + 48])[3:] for i in range(n)]
def fix(p):
    T = lade(p); k = lambda a: tuple(round(c, 4) for c in a)
    V, vid, F = [], {}, []
    for t in T:
        ids = []
        for j in range(3):
            q = k(t[j*3:j*3+3])
            if q not in vid: vid[q] = len(V); V.append(t[j*3:j*3+3])
            ids.append(vid[q])
        if len(set(ids)) == 3: F.append(ids)
    E = collections.Counter((a, b) for f in F for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])))
    offen = [(a, b) for (a, b), c in E.items() if E.get((b, a), 0) < c]
    nxt = collections.defaultdict(list)
    for a, b in offen: nxt[a].append(b)
    used, neu = set(), 0
    for a, b in offen:
        if (a, b) in used: continue
        loop = [a]; used.add((a, b)); cur = b
        while cur != a and len(loop) < 1000:
            loop.append(cur)
            c = [x for x in nxt[cur] if (cur, x) not in used]
            if not c: break
            used.add((cur, c[0])); cur = c[0]
        if cur == a and len(loop) >= 3:
            for i in range(1, len(loop) - 1):
                F.append([loop[0], loop[i + 1], loop[i]]); neu += 1
    with open(p, 'wb') as f:
        f.write(b'fixed'.ljust(80, b' ')); f.write(struct.pack('<I', len(F)))
        for fa in F:
            f.write(struct.pack('<3f', 0, 0, 0))
            for i in fa: f.write(struct.pack('<3f', *V[i]))
            f.write(b'\0\0')
    print(p, "offene Kanten:", len(offen), "-> Fuell-Dreiecke:", neu)
for p in sys.argv[1:]: fix(p)
