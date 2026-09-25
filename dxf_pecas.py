# Extrai do DXF do Promob as peças (1 camada = 1 peça) com bounding box e faces, e salva em JSON.
# Uso: python dxf_pecas.py arquivo.dxf saida.json
import sys, json
import ezdxf
sys.stdout.reconfigure(encoding='utf-8')
doc = ezdxf.readfile(sys.argv[1])
pecas = {}
for e in doc.modelspace():
    t = e.dxftype()
    if t == '3DFACE':
        vs = [(v.x, v.y, v.z) for v in (e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx2, e.dxf.vtx3)]
    elif t == 'POLYLINE':
        try: vs = [tuple(v.dxf.location) for v in e.vertices]
        except Exception: continue
    else:
        continue
    p = pecas.setdefault(e.dxf.layer, {'bb': [1e18] * 3 + [-1e18] * 3, 'faces': []})
    for v in vs:
        for i in range(3):
            p['bb'][i] = min(p['bb'][i], v[i]); p['bb'][i + 3] = max(p['bb'][i + 3], v[i])
    if t == '3DFACE': p['faces'].append([[round(c, 1) for c in v] for v in vs])
out = []
for L, p in pecas.items():
    b = p['bb']
    out.append({'layer': L, 'bb': [round(x, 1) for x in b], 'dim': [round(b[i + 3] - b[i], 1) for i in range(3)], 'faces': p['faces']})
json.dump(out, open(sys.argv[2], 'w'), separators=(',', ':'))
print('pecas', len(out))
