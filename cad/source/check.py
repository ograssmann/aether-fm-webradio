import sys, trimesh
for p in sys.argv[1:]:
    m = trimesh.load(p, process=False)
    m.merge_vertices(digits_vertex=4)
    print(p, len(m.faces), "watertight:", m.is_watertight, "vol cm3:", round(m.volume/1000, 1))
