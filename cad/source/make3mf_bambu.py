"""Bambu-Studio-3MF: ein Objekt aus mehreren Teilen, jedes Teil mit fester AMS-Position (Filament 1-4),
auf der Druckplatte (256 x 256) zentriert."""
import struct, zipfile, sys, json
def lade(p):
    d = open(p, 'rb').read(); n = struct.unpack('<I', d[80:84])[0]
    V, vid, F = [], {}, []
    for i in range(n):
        t = struct.unpack('<12f', d[84 + i * 50:84 + i * 50 + 48])[3:]
        ids = []
        for j in range(3):
            q = tuple(round(c, 4) for c in t[j*3:j*3+3])
            if q not in vid: vid[q] = len(V); V.append(q)
            ids.append(vid[q])
        if len(set(ids)) == 3: F.append(ids)
    return V, F
def baue(out, objname, teile):   # teile: [(stl, name, filament)]
    meshes = [lade(p) for p, _, _ in teile]
    xs = [v[0] for V, _ in meshes for v in V]; ys = [v[1] for V, _ in meshes for v in V]
    tx, ty = 128 - (min(xs) + max(xs)) / 2, 128 - (min(ys) + max(ys)) / 2
    objs = []
    for i, ((V, F), (_, name, _)) in enumerate(zip(meshes, teile)):
        vs = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in V)
        ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in F)
        objs.append(f'<object id="{i + 1}" name="{name}" type="model"><mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh></object>')
    n = len(teile)
    comp = "".join(f'<component objectid="{i + 1}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>' for i in range(n))
    model = ('<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><metadata name="Application">AETHER-CAD</metadata><resources>'
             + "".join(objs) + f'<object id="{n + 1}" name="{objname}" type="model"><components>{comp}</components></object>'
             f'</resources><build><item objectid="{n + 1}" transform="1 0 0 0 1 0 0 0 1 {tx:.3f} {ty:.3f} 0" printable="1"/></build></model>')
    parts = "".join(f'<part id="{i + 1}" subtype="normal_part"><metadata key="name" value="{name}"/>'
                    f'<metadata key="extruder" value="{fil}"/></part>' for i, (_, name, fil) in enumerate(teile))
    cfg = (f'<?xml version="1.0" encoding="UTF-8"?><config><object id="{n + 1}"><metadata key="name" value="{objname}"/>'
           f'<metadata key="extruder" value="{teile[0][2]}"/>{parts}</object>'
           f'<plate><metadata key="plater_id" value="1"/><model_instance><metadata key="object_id" value="{n + 1}"/>'
           f'<metadata key="instance_id" value="0"/></model_instance></plate></config>')
    ct = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
          '<Default Extension="config" ContentType="text/xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ct); z.writestr('_rels/.rels', rels)
        z.writestr('3D/3dmodel.model', model); z.writestr('Metadata/model_settings.config', cfg)
    print(out, "ok")
if __name__ == "__main__":
    baue("AETHER_V7_Deckel_P1S.3mf", "AETHER Deckel",
         [("Gehaeuse_V7_Deckel.stl", "Deckel schwarz", 3), ("Gehaeuse_V7_Deckel_Schrift.stl", "Schrift + Welle weiss", 2)])
    baue("AETHER_V7_Unterteil_P1S.3mf", "AETHER Unterteil", [("Gehaeuse_V7_Unterteil.stl", "Unterteil schwarz", 3)])
    baue("AETHER_V7_Seitendeckel_P1S.3mf", "AETHER Seitendeckel", [("Gehaeuse_V7_Seitendeckel.stl", "Seitendeckel schwarz", 3)])
