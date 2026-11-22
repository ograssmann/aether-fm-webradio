"""STL -> STEP (AP214, faceted B-rep). Koplanare Dreiecke werden zu ebenen Flaechen (mit Loechern) zusammengefasst."""
import struct, sys, collections, math

def load(p):
    d = open(p, 'rb').read(); n = struct.unpack('<I', d[80:84])[0]; T = []
    for i in range(n):
        v = struct.unpack('<12f', d[84 + i * 50:84 + i * 50 + 48]); T.append((v[3:6], v[6:9], v[9:12]))
    return T

def key(v): return tuple(round(c, 4) for c in v)

def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def convert(stl, step, name):
    T = load(stl)
    V, vid, tris = [], {}, []
    for t in T:
        ids = []
        for v in t:
            k = key(v)
            if k not in vid: vid[k] = len(V); V.append(k)
            ids.append(vid[k])
        if len(set(ids)) < 3: continue
        n = cross(sub(V[ids[1]], V[ids[0]]), sub(V[ids[2]], V[ids[0]]))
        L = math.sqrt(sum(c * c for c in n))
        if L < 1e-9: continue
        n = tuple(c / L for c in n)
        d = sum(n[i] * V[ids[0]][i] for i in range(3))
        tris.append((ids, n, d))
    # Gruppen: gleiche Ebene + ueber Kanten verbunden
    pk = lambda n, d: (round(n[0], 3), round(n[1], 3), round(n[2], 3), round(d, 2))
    edge_tris = collections.defaultdict(list)
    for i, (ids, n, d) in enumerate(tris):
        for a, b in ((ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[0])):
            edge_tris[frozenset((a, b))].append(i)
    seen = [False] * len(tris); groups = []
    for i in range(len(tris)):
        if seen[i]: continue
        p = pk(tris[i][1], tris[i][2]); stack = [i]; seen[i] = True; g = []
        while stack:
            j = stack.pop(); g.append(j); ids = tris[j][0]
            for a, b in ((ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[0])):
                for k in edge_tris[frozenset((a, b))]:
                    if not seen[k] and pk(tris[k][1], tris[k][2]) == p:
                        seen[k] = True; stack.append(k)
        groups.append(g)
    out = []; nid = [0]
    def ent(s):
        nid[0] += 1; out.append(f"#{nid[0]}={s};"); return nid[0]
    pts = {}
    def P(i):
        if i not in pts:
            x, y, z = V[i]; pts[i] = ent(f"CARTESIAN_POINT('',({x:.4f},{y:.4f},{z:.4f}))")
        return pts[i]
    faces = []
    for g in groups:
        n = tris[g[0]][1]
        E = collections.Counter()
        for j in g:
            ids = tris[j][0]
            for a, b in ((ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[0])): E[(a, b)] += 1
        bnd = [(a, b) for (a, b) in E if (b, a) not in E]
        nxt = collections.defaultdict(list)
        for a, b in bnd: nxt[a].append(b)
        used = set(); loops = []
        for a, b in bnd:
            if (a, b) in used: continue
            loop = [a]; used.add((a, b)); cur = b
            while cur != a:
                loop.append(cur)
                cand = [c for c in nxt[cur] if (cur, c) not in used]
                if not cand: break
                used.add((cur, cand[0])); cur = cand[0]
            if len(loop) >= 3: loops.append(loop)
        if not loops: continue
        # Flaeche je Loop (projiziert auf Ebene), groesste = Aussenrand
        ax = max(range(3), key=lambda i: abs(n[i])); u, w = [i for i in range(3) if i != ax]
        def area(l):
            return abs(sum(V[l[i]][u] * V[l[(i+1) % len(l)]][w] - V[l[(i+1) % len(l)]][u] * V[l[i]][w] for i in range(len(l)))) / 2
        loops.sort(key=area, reverse=True)
        bounds = []
        for k, l in enumerate(loops):
            pl = ent("POLY_LOOP('',(" + ",".join(f"#{P(i)}" for i in l) + "))")
            bounds.append(ent(f"{'FACE_OUTER_BOUND' if k == 0 else 'FACE_BOUND'}('',#{pl},.T.)"))
        faces.append(ent("FACE('',(" + ",".join(f"#{b}" for b in bounds) + "))"))
    shell = ent("CLOSED_SHELL('',(" + ",".join(f"#{f}" for f in faces) + "))")
    brep = ent(f"FACETED_BREP('{name}',#{shell})")
    o = ent("CARTESIAN_POINT('',(0.,0.,0.))"); dz = ent("DIRECTION('',(0.,0.,1.))"); dx = ent("DIRECTION('',(1.,0.,0.))")
    ax2 = ent(f"AXIS2_PLACEMENT_3D('',#{o},#{dz},#{dx})")
    lu = ent("(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.))")
    au = ent("(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))")
    su = ent("(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT())")
    unc = ent(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-04),#{lu},'distance_accuracy_value','')")
    ctx = ent(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{unc}))GLOBAL_UNIT_ASSIGNED_CONTEXT((#{lu},#{au},#{su}))REPRESENTATION_CONTEXT('',''))")
    rep = ent(f"FACETED_BREP_SHAPE_REPRESENTATION('{name}',(#{ax2},#{brep}),#{ctx})")
    appc = ent("APPLICATION_CONTEXT('automotive_design')")
    ent(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#{appc})")
    pc = ent(f"PRODUCT_CONTEXT('',#{appc},'mechanical')")
    prod = ent(f"PRODUCT('{name}','{name}','',(#{pc}))")
    pdfw = ent(f"PRODUCT_DEFINITION_FORMATION('','',#{prod})")
    pdc = ent(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{appc},'design')")
    pd = ent(f"PRODUCT_DEFINITION('design','',#{pdfw},#{pdc})")
    pds = ent(f"PRODUCT_DEFINITION_SHAPE('','',#{pd})")
    ent(f"SHAPE_DEFINITION_REPRESENTATION(#{pds},#{rep})")
    ppc = ent(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,(#{prod}))")
    hdr = ("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('" + name + "'),'2;1');\n"
           f"FILE_NAME('{name}.step','2026-11-14T00:00:00',(''),(''),'stl2step','','');\n"
           "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\nENDSEC;\nDATA;\n")
    open(step, 'w').write(hdr + "\n".join(out) + "\nENDSEC;\nEND-ISO-10303-21;\n")
    print(step, len(tris), "Dreiecke ->", len(faces), "Flaechen")

for stl, step, name in zip(sys.argv[1::3], sys.argv[2::3], sys.argv[3::3]):
    convert(stl, step, name)
