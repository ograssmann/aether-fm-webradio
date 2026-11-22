"""Minimal BSP-based CSG (port of Evan Wallace's csg.js, MIT licence)."""
import math

EPS = 1e-5


class V:
    __slots__ = ("x", "y", "z")

    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def __add__(s, o): return V(s.x + o.x, s.y + o.y, s.z + o.z)
    def __sub__(s, o): return V(s.x - o.x, s.y - o.y, s.z - o.z)
    def __mul__(s, k): return V(s.x * k, s.y * k, s.z * k)
    def __neg__(s): return V(-s.x, -s.y, -s.z)
    def dot(s, o): return s.x * o.x + s.y * o.y + s.z * o.z
    def cross(s, o): return V(s.y * o.z - s.z * o.y, s.z * o.x - s.x * o.z, s.x * o.y - s.y * o.x)
    def length(s): return math.sqrt(s.dot(s))
    def unit(s):
        l = s.length()
        return s * (1.0 / l)
    def lerp(s, o, t): return s + (o - s) * t


class Plane:
    __slots__ = ("n", "w")

    def __init__(self, n, w):
        self.n, self.w = n, w

    @staticmethod
    def from_points(a, b, c):
        n = (b - a).cross(c - a).unit()
        return Plane(n, n.dot(a))

    def flip(self):
        self.n = -self.n
        self.w = -self.w

    def split(self, poly, cop_front, cop_back, front, back):
        COP, FR, BK, SP = 0, 1, 2, 3
        ptype = 0
        types = []
        for v in poly.verts:
            t = self.n.dot(v) - self.w
            ty = BK if t < -EPS else (FR if t > EPS else COP)
            ptype |= ty
            types.append(ty)
        if ptype == COP:
            (cop_front if self.n.dot(poly.plane.n) > 0 else cop_back).append(poly)
        elif ptype == FR:
            front.append(poly)
        elif ptype == BK:
            back.append(poly)
        else:
            f, b = [], []
            n = len(poly.verts)
            for i in range(n):
                j = (i + 1) % n
                ti, tj = types[i], types[j]
                vi, vj = poly.verts[i], poly.verts[j]
                if ti != BK:
                    f.append(vi)
                if ti != FR:
                    b.append(vi)
                if (ti | tj) == SP:
                    t = (self.w - self.n.dot(vi)) / self.n.dot(vj - vi)
                    v = vi.lerp(vj, t)
                    f.append(v)
                    b.append(v)
            if len(f) >= 3:
                front.append(Poly(f, poly.plane))
            if len(b) >= 3:
                back.append(Poly(b, poly.plane))


class Poly:
    __slots__ = ("verts", "plane")

    def __init__(self, verts, plane=None):
        self.verts = verts
        self.plane = plane or Plane.from_points(verts[0], verts[1], verts[2])

    def clone(self):
        return Poly(list(self.verts), Plane(self.plane.n, self.plane.w))

    def flip(self):
        self.verts.reverse()
        self.plane = Plane(-self.plane.n, -self.plane.w)


class Node:
    def __init__(self, polys=None):
        self.plane = None
        self.front = None
        self.back = None
        self.polys = []
        if polys:
            self.build(polys)

    def invert(self):
        for p in self.polys:
            p.flip()
        self.plane = Plane(-self.plane.n, -self.plane.w)
        if self.front: self.front.invert()
        if self.back: self.back.invert()
        self.front, self.back = self.back, self.front

    def clip_polys(self, polys):
        if not self.plane:
            return list(polys)
        front, back = [], []
        for p in polys:
            self.plane.split(p, front, back, front, back)
        if self.front:
            front = self.front.clip_polys(front)
        if self.back:
            back = self.back.clip_polys(back)
        else:
            back = []
        return front + back

    def clip_to(self, bsp):
        self.polys = bsp.clip_polys(self.polys)
        if self.front: self.front.clip_to(bsp)
        if self.back: self.back.clip_to(bsp)

    def all_polys(self):
        out = list(self.polys)
        if self.front: out += self.front.all_polys()
        if self.back: out += self.back.all_polys()
        return out

    def build(self, polys):
        stack = [(self, polys)]
        while stack:
            node, ps = stack.pop()
            if not ps:
                continue
            if not node.plane:
                node.plane = Plane(ps[0].plane.n, ps[0].plane.w)
            front, back = [], []
            for p in ps:
                node.plane.split(p, node.polys, node.polys, front, back)
            if front:
                if not node.front:
                    node.front = Node()
                stack.append((node.front, front))
            if back:
                if not node.back:
                    node.back = Node()
                stack.append((node.back, back))


class Solid:
    def __init__(self, polys):
        self.polys = polys

    def clone(self):
        return Solid([p.clone() for p in self.polys])

    def union(self, o):
        a, b = Node(self.clone().polys), Node(o.clone().polys)
        a.clip_to(b); b.clip_to(a); b.invert(); b.clip_to(a); b.invert()
        a.build(b.all_polys())
        return Solid(a.all_polys())

    def subtract(self, o):
        a, b = Node(self.clone().polys), Node(o.clone().polys)
        a.invert(); a.clip_to(b); b.clip_to(a); b.invert(); b.clip_to(a); b.invert()
        a.build(b.all_polys()); a.invert()
        return Solid(a.all_polys())

    # ---------- export ----------
    def triangles(self):
        for p in self.polys:
            v = p.verts
            for i in range(1, len(v) - 1):
                yield p.plane.n, v[0], v[i], v[i + 1]

    def write_stl(self, path, name="part"):
        import struct
        tris = list(self.triangles())
        with open(path, "wb") as f:
            f.write(name.encode().ljust(80, b" ")[:80])
            f.write(struct.pack("<I", len(tris)))
            for n, a, b, c in tris:
                f.write(struct.pack("<12fH", n.x, n.y, n.z, a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z, 0))
        return len(tris)


def box(x0, y0, z0, x1, y1, z1):
    c = [V(x0, y0, z0), V(x1, y0, z0), V(x1, y1, z0), V(x0, y1, z0),
         V(x0, y0, z1), V(x1, y0, z1), V(x1, y1, z1), V(x0, y1, z1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
    return Solid([Poly([c[i] for i in f]) for f in faces])


def cyl(p0, p1, r, seg=48):
    """Cylinder from point p0 to p1 (tuples), radius r."""
    s, e = V(*p0), V(*p1)
    ray = e - s
    axz = ray.unit()
    is_y = abs(axz.y) > 0.5
    axx = V(1 if is_y else 0, 0 if is_y else 1, 0).cross(axz).unit()
    axy = axx.cross(axz).unit()
    polys = []

    def pt(stack, i):
        a = i * 2 * math.pi / seg
        out = axx * math.cos(a) + axy * math.sin(a)
        return s + ray * stack + out * r

    for i in range(seg):
        a0, a1 = pt(0, i), pt(0, i + 1)
        b0, b1 = pt(1, i), pt(1, i + 1)
        polys.append(Poly([s, a0, a1]))
        polys.append(Poly([a1, a0, b0, b1]))
        polys.append(Poly([e, b1, b0]))
    return Solid(polys)


def union_all(solids):
    out = solids[0]
    for s in solids[1:]:
        out = out.union(s)
    return out


def write_stl_clean(solid, path, name="part", eps=1e-4, cell=4.0):
    """Exports with T-junctions repaired (watertight mesh)."""
    import struct
    from collections import defaultdict
    # 1. eindeutige Punkte
    def k(v): return (round(v.x / eps), round(v.y / eps), round(v.z / eps))
    pts = {}
    for p in solid.polys:
        for v in p.verts:
            pts.setdefault(k(v), v)
    grid = defaultdict(list)
    for key, v in pts.items():
        grid[(int(v.x // cell), int(v.y // cell), int(v.z // cell))].append(v)

    def on_edge(a, b):
        d = b - a
        L2 = d.dot(d)
        if L2 < 1e-12:
            return []
        lo = [min(a.x, b.x), min(a.y, b.y), min(a.z, b.z)]
        hi = [max(a.x, b.x), max(a.y, b.y), max(a.z, b.z)]
        found = []
        for i in range(int(lo[0] // cell), int(hi[0] // cell) + 1):
            for j in range(int(lo[1] // cell), int(hi[1] // cell) + 1):
                for m in range(int(lo[2] // cell), int(hi[2] // cell) + 1):
                    for v in grid.get((i, j, m), ()):
                        t = (v - a).dot(d) / L2
                        if t <= 1e-6 or t >= 1 - 1e-6:
                            continue
                        q = a + d * t
                        if (v - q).length() < 5e-4:
                            found.append((t, v))
        found.sort(key=lambda x: x[0])
        return [v for _, v in found]

    tris = []
    for p in solid.polys:
        vs = p.verts
        ring = []
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            ring.append(a)
            ring.extend(on_edge(a, b))
        n = p.plane.n
        if len(ring) == 3:
            tris.append((n, ring[0], ring[1], ring[2]))
            continue
        c = ring[0] * 0
        for v in ring:
            c = c + v
        c = c * (1.0 / len(ring))
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            if (a - c).cross(b - c).length() > 1e-9:
                tris.append((n, c, a, b))
    with open(path, "wb") as f:
        f.write(name.encode().ljust(80, b" ")[:80])
        f.write(struct.pack("<I", len(tris)))
        for n, a, b, cc in tris:
            f.write(struct.pack("<12fH", n.x, n.y, n.z, a.x, a.y, a.z, b.x, b.y, b.z, cc.x, cc.y, cc.z, 0))
    return len(tris)
