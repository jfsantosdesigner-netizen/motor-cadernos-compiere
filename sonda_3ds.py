# Sonda 3DS: lista objetos (nomes), materiais (nome + cor difusa + textura) e quais faces usam cada material.
import sys, struct, collections
sys.stdout.reconfigure(encoding='utf-8')
data = open(sys.argv[1], 'rb').read()
objs, mats = [], []
uso = collections.Counter()
def cstr(b, o):
    e = b.index(b'\x00', o); return b[o:e].decode('latin-1'), e + 1
def walk(o, end, ctx):
    while o + 6 <= end:
        cid, ln = struct.unpack_from('<HI', data, o)
        if ln < 6: break
        body, fim = o + 6, o + ln
        if cid in (0x4D4D, 0x3D3D, 0x4100):
            walk(body, fim, ctx)
        elif cid == 0x4000:
            nome, p = cstr(data, body); ctx = dict(ctx, obj=nome); objs.append([nome, 0, None]); walk(p, fim, ctx)
        elif cid == 0x4110:
            n = struct.unpack_from('<H', data, body)[0]
            vs = struct.unpack_from('<%df' % (3 * n), data, body + 2)
            xs, ys, zs = vs[0::3], vs[1::3], vs[2::3]
            objs[-1][2] = [round(min(xs)), round(min(ys)), round(min(zs)), round(max(xs)), round(max(ys)), round(max(zs))]
        elif cid == 0x4120:
            n = struct.unpack_from('<H', data, body)[0]; objs[-1][1] = n
            walk(body + 2 + 8 * n, fim, ctx)
        elif cid == 0x4130:
            m, p = cstr(data, body); k = struct.unpack_from('<H', data, p)[0]; uso[m] += k
            objs[-1].append(m)
        elif cid == 0xAFFF:
            mats.append({'nome': None, 'cor': None, 'tex': None}); walk(body, fim, ctx)
        elif cid == 0xA000:
            mats[-1]['nome'] = cstr(data, body)[0]
        elif cid == 0xA020:
            walk(body, fim, dict(ctx, dif=True))
        elif cid in (0x0011, 0x0012) and ctx.get('dif') and mats and mats[-1]['cor'] is None:
            mats[-1]['cor'] = tuple(data[body:body + 3]) if cid == 0x0011 else tuple(round(x * 255) for x in struct.unpack_from('<3f', data, body))
        elif cid == 0xA200:
            walk(body, fim, dict(ctx, tex=True))
        elif cid == 0xA300 and mats:
            mats[-1]['tex'] = cstr(data, body)[0]
        o = fim
walk(0, len(data), {})
print('OBJETOS', len(objs), '| MATERIAIS', len(mats))
for m in mats: print('  MAT', m, 'faces', uso.get(m['nome'], 0))
print('EXEMPLOS DE OBJETOS:')
for o in objs[:25]: print('  ', o)
nomes = collections.Counter(o[0].rstrip('0123456789') for o in objs)
print('PREFIXOS DE NOME', nomes.most_common(15))
