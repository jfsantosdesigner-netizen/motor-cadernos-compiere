# GERADOR DE CADERNO v2 — Compiere. Um comando: python gerar_caderno.py config.json
# XML/listagem -> DXF (posição real) -> vistas automáticas -> listagem por vista + balões -> elevações com cotas -> PDF + QUALIDADE
import sys, os, re, json, subprocess, xml.etree.ElementTree as ET
from collections import OrderedDict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import pymupdf as fz, geo
from motor_lista import listagem_de_pdf

cfg = json.load(open(sys.argv[1], encoding='utf-8'))
AREA = fz.Rect(19, 142, 823, 577); IN = 7
RED = (0.545, 0, 0); CR = (0.9, 0, 0); PRETO = (0, 0, 0)
BRANCO = (1, 1, 1); MADEIRA = (0.80, 0.63, 0.42); CINZA = (0.93, 0.93, 0.93)
MM = 72 / 25.4
ESC = [25, 30, 40, 50, 75, 100, 125, 150]
FV = {'x+': (1, 0), 'x-': (-1, 0), 'y+': (0, 1), 'y-': (0, -1)}
AREA_IN = fz.Rect(AREA.x0 + IN, AREA.y0 + IN, AREA.x1 - IN, AREA.y1 - IN)   # regra: nada encosta no quadro

def fmt(v):
    v = round(v * 2) / 2
    return str(int(round(v))) if abs(v - round(v)) < 0.01 else ('%.1f' % v).replace('.', ',')

# ---------------- entrada ----------------
def modelo(it):
    refs = it.find('REFERENCES')
    if refs is None: return ''
    for tag in ('MODEL', 'COR', 'MAT'):
        e = refs.find(tag)
        if e is not None and e.get('REFERENCE'): return e.get('REFERENCE')
    return ''

QT = {}
def ler_xml(path):
    root = ET.parse(path).getroot()
    mods, comps, cores, pux, ferr = OrderedDict(), OrderedDict(), {}, OrderedDict(), OrderedDict()
    for cat in root.iter('CATEGORY'):
        items = cat.find('ITEMS')
        if items is None: continue
        cn = (cat.get('DESCRIPTION') or '').upper()
        for it in items.findall('ITEM'):
            a = it.attrib; U = a.get('ID', '').upper(); d = a.get('DESCRIPTION', ''); m = modelo(it)
            if not m:
                for ch in it.iter('ITEM'):
                    if re.search(r'lat|bas', ch.get('ID', ''), re.I) and modelo(ch): m = modelo(ch); break
            if 'EURONOBRE' in cn or 'PUX' in U: pux[d.split('(')[0].strip()] = 1; continue
            if 'FERRAG' in cn: ferr[d.strip()] = 1; continue
            if 'ACESS' in cn or U.startswith('ACE') or U.startswith('EUR_'): continue
            if '_POR_' in U:
                if m: cores.setdefault('porta', OrderedDict())[m] = 1
                continue
            desc = re.sub(r'\s+\d+(?:[.,]\d+)?x\d+(?:[.,]\d+)?x\d+(?:[.,]\d+)?mm\s*$', '', d).strip()
            dim = 'x'.join(fmt(float(a[k])) for k in ('WIDTH', 'HEIGHT', 'DEPTH'))
            qq = int(float(a.get('QUANTITY') or 1)); QT[(desc, dim)] = QT.get((desc, dim), 0) + qq
            if U.startswith(('PAI', 'COM_COZ_DIV')):
                comps[(desc, dim)] = 1
                if m: cores.setdefault('tamp', OrderedDict())[m] = 1
            else:
                mods[(desc, dim)] = 1
                if m: cores.setdefault('caixa', OrderedDict())[m] = 1
    return list(mods) + list(comps), cores, list(pux), list(ferr)

linhas_xml, cores, puxs, ferrs = ler_xml(cfg['xml'])
if cfg.get('listagem_pdf'):
    linhas = []
    for pg in cfg['listagem_pags']:
        for d, dm, _ in listagem_de_pdf(cfg['listagem_pdf'], pg):
            if (d, dm) not in linhas: linhas.append((d, dm))
else:
    linhas = linhas_xml

pj = cfg['pecas_json']
if not os.path.exists(pj):
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'dxf_pecas.py'), cfg['dxf'], pj], check=True)
P = geo.carregar(pj)

import math
def _n(a, b, c):
    if len(set((a, b, c))) < 3: return (0, 0, 1)
    e1 = [b[k] - a[k] for k in range(3)]; e2 = [c[k] - a[k] for k in range(3)]
    n = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]); m = math.sqrt(sum(x * x for x in n)) or 1
    return tuple(x / m for x in n)
def preparar(P):
    # REGRA: imagem limpa - cada peça é desenhada como caixa reta (só as bordas, sem triangulação)
    for p_ in P:
        x0, y0, z0, x1, y1, z1 = p_['bb']
        c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        F = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (3, 2, 6, 7), (0, 3, 7, 4), (1, 2, 6, 5)]
        N = [(0, 0, -1), (0, 0, 1), (0, -1, 0), (0, 1, 0), (-1, 0, 0), (1, 0, 0)]
        p_['fq'] = [[[c[i] for i in f_], n_, [True] * 4] for f_, n_ in zip(F, N)]
preparar(P)

# ===== CORES REAIS: XML (cor de cada peça) -> pasta MATERIAIS (textura) -> cor média =====
import unicodedata as _ud, collections as _col, xml.etree.ElementTree as _ET2
def _norm(t):
    t = _ud.normalize('NFKD', t).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()
_MD = os.path.dirname(os.path.abspath(__file__))
_MAT = cfg.get('materiais') or r'C:\CLAUDE\MATERIAIS'
_MI = os.path.join(_MD, 'materiais_index.json')
_MC = os.path.join(_MD, 'materiais_cores.json')  # [caminho relativo a MATERIAIS, nome, [r,g,b]]: cores prontas, dispensa a pasta MATERIAIS
_rgbx = {}
if os.path.exists(_MC):
    _idx = []
    for rel_, st_, rgb_ in json.load(open(_MC, encoding='utf-8')):
        _idx.append([os.path.join(_MAT, rel_), st_]); _rgbx[_idx[-1][0]] = rgb_
elif os.path.exists(_MI): _idx = json.load(open(_MI, encoding='utf-8'))
else:
    _idx = []
    for d_, ds_, fs_ in os.walk(_MAT):
        for f_ in fs_:
            if f_.lower().endswith(('.jpg', '.jpeg', '.png')): _idx.append([os.path.join(d_, f_), _norm(os.path.splitext(f_)[0])])
    json.dump(_idx, open(_MI, 'w', encoding='utf-8'))
_CC = os.path.join(_MD, 'cores_cache.json')
_cc = json.load(open(_CC, encoding='utf-8')) if os.path.exists(_CC) else {}
_PREF = ('duratex', 'arauco', 'guararapes', 'berneck', 'eucatex', 'masisa', 'stelben')
def cor_material(nome):
    if not nome: return None
    if nome in _cc: return tuple(_cc[nome][0]) if _cc[nome] else None
    tk = _norm(nome).split(); best = None
    for cand in ([tk] + ([tk[:-1]] if len(tk) > 1 else [])):
        n = ' '.join(cand)
        for path_, st in _idx:
            ws = st.split()
            if st == n: sc = 100
            elif all(t in ws for t in cand): sc = 60 - len(ws)
            else: continue
            pl = path_.lower(); sc += sum(5 for w in _PREF if w in pl) + (2 if '\\fabrica\\' in pl else 0)
            if best is None or sc > best[0]: best = (sc, path_)
        if best: break
    rgb = tuple(_rgbx[best[1]]) if best and _rgbx.get(best[1]) else None
    if best and not rgb:
        try:
            px = fz.Pixmap(best[1])
            if px.colorspace is None or px.colorspace.n != 3: px = fz.Pixmap(fz.csRGB, px)
            if px.alpha: px = fz.Pixmap(px, 0)
            sm = px.samples; npx = len(sm) // 3; st_ = max(1, npx // 6000); r = g = b = c = 0
            for i_ in range(0, npx, st_): r += sm[3 * i_]; g += sm[3 * i_ + 1]; b += sm[3 * i_ + 2]; c += 1
            rgb = (r / c / 255, g / c / 255, b / c / 255)
        except Exception: rgb = None
    _cc[nome] = [list(rgb), best[1]] if rgb else None
    json.dump(_cc, open(_CC, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    return rgb
_dm = {}; _ord = {}
for e in _ET2.parse(cfg['xml']).iter('ITEM'):
    m_ = next((g for ch in e if ch.tag != 'ITEM' for g in ch if g.tag == 'MODEL'), None)
    if m_ is None or not m_.get('REFERENCE'): continue
    try: k_ = tuple(sorted(round(float(e.get(a))) for a in ('WIDTH', 'HEIGHT', 'DEPTH')))
    except Exception: continue
    _dm.setdefault(k_, _col.Counter())[m_.get('REFERENCE')] += 1
    if e.get('COMPONENT') == 'Y' and e.get('UNIQUEPARENTID') == '-2': _ord.setdefault(k_, []).append(m_.get('REFERENCE'))
# Peças soltas de MESMA medida e cores diferentes (ex.: 2 tamponamentos 2350x18x70, um Preto e um Chumbo):
# o DXF traz as camadas na ordem inversa do XML -> casa pela ordem.
_fixa = {}; _gp = {}
for p_ in P: _gp.setdefault(tuple(sorted(round(x) for x in p_['dim'])), []).append(p_)
for k_, refs_ in _ord.items():
    g_ = _gp.get(k_, [])
    if len(set(refs_)) > 1 and len(g_) == len(refs_):
        for p_, r_ in zip(sorted(g_, key=lambda t: t['i']), reversed(refs_)): _fixa[p_['i']] = r_
_nc = 0; _usadas = _col.Counter()
for p_ in P:
    k_ = tuple(sorted(round(x) for x in p_['dim'])); c_ = _dm.get(k_)
    if p_['i'] in _fixa: c_ = _col.Counter({_fixa[p_['i']]: 1})
    if not c_:
        for dd in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (-1, 0, 0), (0, -1, 0), (0, 0, -1)):
            c_ = _dm.get(tuple(sorted(a + b for a, b in zip(k_, dd))))
            if c_: break
    if c_:
        nm_ = c_.most_common(1)[0][0]; rgb = cor_material(nm_)
        if rgb: p_['rgb'] = rgb; _nc += 1; _usadas[nm_] += 1
print('CORES: %d pecas coloridas pelo MATERIAIS (medidas no XML: %d)' % (_nc, len(_dm)))
for nm_, q_ in _usadas.most_common(): print('   %-22s %4d pecas <- %s' % (nm_, q_, os.path.relpath(_cc[nm_][1], _MAT)))
for nm_ in [k for k, v in _cc.items() if not v]: print('   SEM TEXTURA:', nm_)
inst = geo.casar(P, linhas, None if cfg.get('listagem_pdf') else QT)
paredes = geo.definir_paredes(inst, P)
PW = {w['id']: w for w in paredes}
grupos = geo.agrupar_vistas2(paredes)
nao_achados = [(d, dm) for n, (d, dm) in enumerate(linhas, 1) if not any(i['n'] == n for i in inst)]

# vistas: liga cada grupo à imagem 3D do config pela peça de referência
V = []
livres = list(grupos)
for cv in cfg['vistas']:
    g = next((g for g in livres if any(cv['ref'] in f"{i['desc']} {i['dim']}" for w in g for i in PW[w]['itens'])), None)
    if g: livres.remove(g); V.append(dict(cv, paredes=sorted(g, key=lambda w: -len(PW[w]['itens']))))
letras = 'ABCDEFGHIJKL'
# REGRA (João): UMA VISTA POR PAREDE (frontal 2D de verdade, listagem e cotas pegam todos os móveis daquela parede).
# Ordem: segue a sequência dos grupos (paredes vizinhas juntas); dentro do grupo, a parede maior primeiro.
# Ex.: cozinha em dois "L" -> A (parede maior), B (a perninha do L), C (outra parede maior), D (a outra perninha).
_larg = lambda w: max(max(i['bb'][3] for i in PW[w]['itens']) - min(i['bb'][0] for i in PW[w]['itens']),
                      max(i['bb'][4] for i in PW[w]['itens']) - min(i['bb'][1] for i in PW[w]['itens']))
for g in livres:
    for w in sorted(g, key=lambda w: -_larg(w)):
        V.append(dict(letra=letras[len(V)], img3d=None, paredes=[w]))

# listagem de cada vista: módulos primeiro, depois componentes; mesmo item = mesma linha
for v in V:
    its = [i for w in v['paredes'] for i in PW[w]['itens']]
    ordem = sorted(its, key=lambda i: (i['tipo'] != 'mod', i['n']))
    chaves = []
    for i in ordem:
        k = (i['desc'], i['dim'])
        if k not in chaves: chaves.append(k)
    v['linhas'] = [(d, dm, '') for d, dm in chaves]
    for i in its: i['num_' + v['letra']] = chaves.index((i['desc'], i['dim'])) + 1
if nao_achados:
    V[0]['linhas'] += [(d, dm, '*') for d, dm in nao_achados]

# ---------------- geometria de elevação ----------------
def uu(x, y, f): return x * f[1] - y * f[0]

def geom_parede(w):
    f = FV[w['key']]; faces = []; boxes = []
    for it in w['itens']:
        cor = MADEIRA if it['tipo'] == 'comp' else BRANCO
        for pi in it['pecas']:
            for fc in P[pi]['faces']:
                pts = [(uu(v[0], v[1], f), v[2]) for v in fc]
                dep = sum(v[0] * f[0] + v[1] * f[1] for v in fc) / 4
                faces.append((dep, pts, cor))
        u0, z0, u1, z1 = geo.caixa_elev(it['bb'], f)
        boxes.append(dict(it=it, u0=u0, z0=z0, u1=u1, z1=z1))
    faces.sort(key=lambda t: -t[0])
    umin = min(b['u0'] for b in boxes); umax = max(b['u1'] for b in boxes); zmax = max(b['z1'] for b in boxes)
    return dict(w=w, f=f, faces=faces, boxes=boxes, umin=umin, umax=umax, zmax=zmax)

def area2(pts):
    return abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2

def desenhar(page, G, ox, fy, k, baloes=None, letra=None):
    X = lambda u: ox + (u - G['umin']) * k
    Y = lambda z: fy - z * k
    sh = page.new_shape()
    for dep, pts, cor in G['faces']:
        q = [(X(u), Y(z)) for u, z in pts]
        if area2(q) < 0.15: continue
        sh.draw_polyline(q + [q[0]]); sh.finish(color=cor, fill=cor, width=0.45, closePath=True)
        for a_, b_ in zip(q, q[1:] + q[:1]):
            if abs(a_[0] - b_[0]) < 0.35 or abs(a_[1] - b_[1]) < 0.35: sh.draw_line(a_, b_)
        sh.finish(color=(0.2, 0.2, 0.2), width=0.3)
    sh.draw_line((X(G['umin']) - 6, fy), (X(G['umax']) + 6, fy)); sh.finish(color=PRETO, width=0.9)
    sh.commit()
    if baloes:
        for b in G['boxes']:
            n = b['it'].get('num_' + letra)
            if not n: continue
            cx, cy = X((b['u0'] + b['u1']) / 2), Y((b['z0'] + b['z1']) / 2)
            s = str(n); wv = fz.get_text_length(s, 'hebo', 6.5) + 4
            r = fz.Rect(cx - wv / 2, cy - 5, cx + wv / 2, cy + 5)
            page.draw_rect(r, color=PRETO, fill=(1, 1, 0), width=0.4)
            page.insert_text((cx - wv / 2 + 2, cy + 2.4), s, fontname='hebo', fontsize=6.5)

def _tick(sh, x, y):
    sh.draw_line((x - 2.2, y + 2.2), (x + 2.2, y - 2.2))

def _txt(page, pos, s, fs, rotate=0, fundo=False):
    if fundo:
        tw = fz.get_text_length(s, 'helv', fs)
        r = fz.Rect(pos[0] - 0.8, pos[1] - fs * 0.8, pos[0] + tw + 0.8, pos[1] + 1) if not rotate else fz.Rect(pos[0] - fs * 0.8, pos[1] - tw - 0.8, pos[0] + 1, pos[1] + 0.8)
        page.draw_rect(r, color=None, fill=(1, 1, 1))
    page.insert_text(pos, s, fontname='helv', fontsize=fs, rotate=rotate)

def cadeia_h(page, us, yl, yobj, X, fs=6.5, fundo=False):
    us = _uniq(us)
    if len(us) < 2: return
    sh = page.new_shape()
    for u in us:
        sh.draw_line((X(u), yobj), (X(u), yl + (2.5 if yl < yobj else -2.5))); sh.finish(color=CR, width=0.25)
    sh.draw_line((X(us[0]), yl), (X(us[-1]), yl)); sh.finish(color=CR, width=0.5)
    for u in us: _tick(sh, X(u), yl)
    sh.finish(color=CR, width=0.6); sh.commit()
    for a, b in zip(us, us[1:]):
        s = fmt(b - a); tw = fz.get_text_length(s, 'helv', fs)
        _txt(page, ((X(a) + X(b)) / 2 - tw / 2, yl - 1.8), s, fs, fundo=fundo)

def cadeia_v(page, zs, xl, xobj, Y, fs=6.5, esquerda=True, fundo=False):
    zs = _uniq(zs)
    if len(zs) < 2: return
    sh = page.new_shape()
    for z in zs:
        if xobj is not None:
            sh.draw_line((xobj, Y(z)), (xl + (2.5 if xl > xobj else -2.5), Y(z))); sh.finish(color=CR, width=0.25)
    sh.draw_line((xl, Y(zs[0])), (xl, Y(zs[-1]))); sh.finish(color=CR, width=0.5)
    for z in zs: _tick(sh, xl, Y(z))
    sh.finish(color=CR, width=0.6); sh.commit()
    for a, b in zip(zs, zs[1:]):
        s = fmt(b - a); tw = fz.get_text_length(s, 'helv', fs)
        _txt(page, (xl - 1.8, (Y(a) + Y(b)) / 2 + tw / 2), s, fs, rotate=90, fundo=fundo)

def _uniq(vals, tol=2.0):
    out = []
    for v in sorted(vals):
        if not out or v - out[-1] > tol: out.append(v)
    return out

CORTE = 1100
def cotar(page, G, ox, fy, k):
    X = lambda u: ox + (u - G['umin']) * k
    Y = lambda z: fy - z * k
    bx = G['boxes']
    mb = [b for b in bx if b['it']['tipo'] == 'mod'] or bx
    mu0, mu1 = min(b['u0'] for b in mb), max(b['u1'] for b in mb)
    cad = mb
    sup = [b for b in cad if b['z1'] > CORTE]
    inf = [b for b in cad if b['z0'] < CORTE]
    ytop = Y(G['zmax'])
    if sup:
        us = [v for b in sup for v in (b['u0'], b['u1'])]
        cadeia_h(page, us, ytop - 13, ytop - 2, X)
        if len(_uniq(us)) > 2: cadeia_h(page, [min(us), max(us)], ytop - 26, ytop - 2, X)
    if inf:
        us = [v for b in inf for v in (b['u0'], b['u1'])]
        cadeia_h(page, us, fy + 13, fy + 2, X)
        if len(_uniq(us)) > 2: cadeia_h(page, [min(us), max(us)], fy + 26, fy + 2, X)
    xr, xl = X(G['umax']), X(G['umin'])
    dir_ = [b for b in mb if b['u1'] >= G['umax'] - 700]
    esq = [b for b in mb if b['u0'] <= G['umin'] + 700]
    cadeia_v(page, [0] + [v for b in dir_ for v in (b['z0'], b['z1'])], xr + 14, xr + 2, Y)
    cadeia_v(page, [0] + [v for b in esq for v in (b['z0'], b['z1'])], xl - 14, xl - 2, Y)
    cadeia_v(page, [0, max(b['z1'] for b in mb)], xl - 28, xl - 2, Y)
    # REGRA (João): cotas INTERNAS dentro do móvel, vão por vão.
    #  - horizontal: largura livre entre lateral/divisória/divisória/lateral
    #  - vertical: altura livre entre prateleiras (de uma prateleira à outra, onde entram gavetas etc.)
    f_ = G['f']
    prof = lambda bb: (bb[3] - bb[0]) if f_[0] else (bb[4] - bb[1])
    for b in bx:
        it = b['it']
        if it['tipo'] != 'mod' or b['z1'] - b['z0'] < 350: continue
        vert, hor = [], []
        for pi in it['pecas']:
            bb = P[pi]['bb']; pu0, pz0, pu1, pz1 = geo.caixa_elev(bb, G['f'])
            if prof(bb) < 150: continue                      # portas, frentes, tamponamentos, ferragens
            if pu1 - pu0 <= 30 and pz1 - pz0 >= 300: vert.append((pu0, pu1))
            elif 12 <= pz1 - pz0 <= 30 and pu1 - pu0 >= 150: hor.append((pu0, pz0, pu1, pz1))
        vert = sorted(vert)
        vaos = [(a[1], c[0]) for a, c in zip(vert, vert[1:]) if c[0] - a[1] > 100]
        for cu0, cu1 in vaos:
            larg = cu1 - cu0
            niv = sorted((z0_, z1_) for u0_, z0_, u1_, z1_ in hor if u0_ <= cu0 + 10 and u1_ >= cu1 - 10)
            gaps = [(a[1], c[0]) for a, c in zip(niv, niv[1:]) if c[0] - a[1] > 40]
            xv = X(cu0 + larg * 0.5)
            for g0, g1 in gaps: cadeia_v(page, [g0, g1], xv, None, Y, fs=5.5, fundo=True)
            zt = (gaps[-1][1] if gaps else b['z1']) - 70
            cadeia_h(page, [cu0, cu1], Y(zt), Y(zt), X, fs=5.5, fundo=True)

# ---------------- pranchas ----------------
lay = fz.open(cfg['layout'])
img = fz.open(cfg['imagens']) if cfg.get('imagens') else None
def nova_prancha(doc, n, titulo):
    p = doc.new_page(width=lay[0].rect.width, height=lay[0].rect.height)
    p.show_pdf_page(p.rect, lay, 0)
    p.draw_rect(fz.Rect(300, 117, 540, 141), color=None, fill=BRANCO)
    p.draw_rect(fz.Rect(712, 52, 816, 96), color=None, fill=BRANCO)
    d = cfg['dados']
    for x, y, t in ((224, 33, d['cliente']), (234, 59, d['ambiente']), (285, 85, d['projetista']), (239, 111, d['arquiteta'])):
        p.insert_text((x, y), t, fontname='hebo', fontsize=10)
    p.insert_text((419.5 - fz.get_text_length(titulo, 'hebo', 16) / 2, 135), titulo, fontname='hebo', fontsize=16, color=RED)
    p.insert_text((764 - fz.get_text_length('PRANCHA', 'hebo', 18) / 2, 62), 'PRANCHA', fontname='hebo', fontsize=18)
    s = '%02d' % n
    p.insert_text((764 - fz.get_text_length(s, 'hebo', 18) / 2, 85), s, fontname='hebo', fontsize=18)
    return p

def regiao(pno):
    pg = img[pno - 1]
    rs = [fz.Rect(i['bbox']) for i in pg.get_image_info() if i['width'] > 1000]
    r = fz.Rect(rs[0])
    for x in rs[1:]: r |= x
    r = fz.Rect(r.x0 + 3, r.y0 + 3, r.x1 - 3, r.y1 - 3)
    import numpy as np
    pix = pg.get_pixmap(clip=r, dpi=60)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]
    ys, xs = np.where((a < 235).any(axis=2))
    if len(xs):
        k = r.width / pix.w
        r = fz.Rect(r.x0 + xs.min() * k, r.y0 + ys.min() * k, r.x0 + (xs.max() + 1) * k, r.y0 + (ys.max() + 1) * k)
    return r

def encaixa(p, pno, alvo):
    r = regiao(pno); f = min(alvo.width / r.width, alvo.height / r.height)
    w, h = r.width * f, r.height * f
    t = fz.Rect(alvo.x0 + (alvo.width - w) / 2, alvo.y0 + (alvo.height - h) / 2, 0, 0); t.x1, t.y1 = t.x0 + w, t.y0 + h
    p.show_pdf_page(t, img, pno - 1, clip=r); return t

def tabela(p, linhas, x0, y0, largura=248):
    fs, lh = 7.2, 10.5
    cols = [x0, x0 + 24, x0 + 168, x0 + largura]
    sh = p.new_shape()
    sh.draw_rect(fz.Rect(x0, y0, x0 + largura, y0 + lh)); sh.finish(color=PRETO, fill=(1, 1, 0), width=0.5)
    for i in range(len(linhas)):
        r = fz.Rect(x0, y0 + lh * (i + 1), x0 + largura, y0 + lh * (i + 2))
        sh.draw_rect(r); sh.finish(color=PRETO, fill=(0.85, 0.85, 0.85) if i % 2 else BRANCO, width=0.4)
    for c in cols[1:-1]:
        sh.draw_line((c, y0), (c, y0 + lh * (len(linhas) + 1))); sh.finish(color=PRETO, width=0.4)
    sh.commit()
    for t, a, b in (('Item', cols[0], cols[1]), ('Descrição', cols[1], cols[2]), ('Dimensão', cols[2], cols[3])):
        p.insert_text(((a + b) / 2 - fz.get_text_length(t, 'helv', fs) / 2, y0 + lh - 2.8), t, fontname='helv', fontsize=fs)
    for i, (d, dm, m) in enumerate(linhas, 1):
        y = y0 + lh * (i + 1) - 2.8
        s = str(i) + m
        p.insert_text(((cols[0] + cols[1]) / 2 - fz.get_text_length(s, 'helv', fs) / 2, y), s, fontname='helv', fontsize=fs)
        while fz.get_text_length(d, 'helv', fs) > cols[2] - cols[1] - 6: d = d[:-1]
        p.insert_text((cols[1] + 3, y), d, fontname='helv', fontsize=fs)
        p.insert_text(((cols[2] + cols[3]) / 2 - fz.get_text_length(dm, 'helv', fs) / 2, y), dm, fontname='helv', fontsize=fs)
    return y0 + lh * (len(linhas) + 1)

def escala_para(larg_mm, alt_mm, W, H):
    for S in ESC:
        k = MM / S
        if larg_mm * k <= W and alt_mm * k <= H: return S, k
    return ESC[-1], MM / ESC[-1]

import math
def _render3d_old0(page, rect, pids, letra=None, ang=32, elev=20):
    its = [i for w in pids for i in PW[w]['itens']]
    U = list(its[0]['bb'])
    for i in its: U = geo.uniao(U, i['bb'])
    E = [U[0] - 80, U[1] - 80, U[2] - 80, U[3] + 80, U[4] + 80, U[5] + 80]
    f = FV[PW[pids[0]]['key']]; sg = 1
    if len(pids) > 1:
        f2 = FV[PW[pids[1]]['key']]; sg = 1 if f[0] * f2[1] - f[1] * f2[0] >= 0 else -1
    a = math.radians(ang * sg); hx = f[0] * math.cos(a) - f[1] * math.sin(a); hy = f[0] * math.sin(a) + f[1] * math.cos(a)
    e = math.radians(elev); d = (hx * math.cos(e), hy * math.cos(e), -math.sin(e))
    rn = math.hypot(hy, hx); r = (hy / rn, -hx / rn, 0.0)
    up = (r[1] * d[2] - r[2] * d[1], r[2] * d[0] - r[0] * d[2], r[0] * d[1] - r[1] * d[0])
    dot = lambda a_, b_: a_[0] * b_[0] + a_[1] * b_[1] + a_[2] * b_[2]
    cor = {}
    for i in inst:
        for pi in i['pecas']: cor[pi] = MADEIRA if i['tipo'] == 'comp' else (0.97, 0.97, 0.97)
    L = (0.35, -0.45, 0.82); nl = math.sqrt(dot(L, L)); fcs = []
    for p_ in P:
        b = p_['bb']
        if not (b[0] >= E[0] and b[1] >= E[1] and b[2] >= E[2] and b[3] <= E[3] and b[4] <= E[4] and b[5] <= E[5]): continue
        base = cor.get(p_['i'], (0.80, 0.80, 0.83))
        for fc in p_['faces']:
            uq = []
            for v in fc:
                v = tuple(v)
                if not uq or max(abs(v[k] - uq[-1][k]) for k in range(3)) > 1e-6: uq.append(v)
            if len(uq) > 1 and max(abs(uq[0][k] - uq[-1][k]) for k in range(3)) < 1e-6: uq.pop()
            if len(uq) < 3: continue
            e1 = [uq[1][k] - uq[0][k] for k in range(3)]; e2 = [uq[2][k] - uq[0][k] for k in range(3)]
            nm = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
            nn = math.sqrt(dot(nm, nm)) or 1
            fs_ = 0.72 + 0.28 * abs(dot(nm, L)) / nn / nl
            fcs.append((sum(dot(v, d) for v in uq) / len(uq), [(dot(v, r), dot(v, up)) for v in uq], tuple(min(1, x * fs_) for x in base), len(uq)))
    if not fcs: return
    xs = [x for _, q, _, _ in fcs for x, _ in q]; ys = [y for _, q, _, _ in fcs for _, y in q]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k = min((rect.width - 16) / (x1 - x0), (rect.height - 16) / (y1 - y0))
    ox = rect.x0 + (rect.width - (x1 - x0) * k) / 2; oy = rect.y0 + (rect.height - (y1 - y0) * k) / 2
    T = lambda x, y: (ox + (x - x0) * k, oy + (y1 - y) * k)
    fcs.sort(key=lambda t: -t[0])
    sh = page.new_shape()
    for dep, q, c_, nv in fcs:
        Q = [T(x, y) for x, y in q]
        if area2(Q) < 0.1: continue
        sh.draw_polyline(Q + [Q[0]]); sh.finish(color=c_, fill=c_, width=0.4, closePath=True)
        ed = list(zip(Q, Q[1:] + Q[:1]))
        if nv == 3:
            ed.sort(key=lambda s_: (s_[0][0] - s_[1][0]) ** 2 + (s_[0][1] - s_[1][1]) ** 2); ed = ed[:2]
        for a_, b_ in ed: sh.draw_line(a_, b_)
        sh.finish(color=(0.25, 0.25, 0.25), width=0.3)
    sh.commit()
    if letra:
        for i in its:
            nb = i.get('num_' + letra)
            if not nb: continue
            b = i['bb']; c3 = ((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2)
            cx, cy = T(dot(c3, r), dot(c3, up)); t_ = str(nb); wv = fz.get_text_length(t_, 'hebo', 7) + 4
            page.draw_rect(fz.Rect(cx - wv / 2, cy - 5.5, cx + wv / 2, cy + 5.5), color=PRETO, fill=(1, 1, 0), width=0.4)
            page.insert_text((cx - wv / 2 + 2, cy + 2.5), t_, fontname='hebo', fontsize=7)

# v3-limpo
def geom_parede(w):
    f = FV[w['key']]; faces = []; boxes = []
    for it in w['itens']:
        cor = MADEIRA if it['tipo'] == 'comp' else BRANCO
        for pi in it['pecas']:
            for uq, nv, ft in P[pi]['fq']:
                faces.append((sum(v[0] * f[0] + v[1] * f[1] for v in uq) / len(uq), [(uu(v[0], v[1], f), v[2]) for v in uq], P[pi].get('rgb', cor), ft))
        u0, z0, u1, z1 = geo.caixa_elev(it['bb'], f)
        boxes.append(dict(it=it, u0=u0, z0=z0, u1=u1, z1=z1))
    umin_ = min(b['u0'] for b in boxes); umax_ = max(b['u1'] for b in boxes); zmax_ = max(b['z1'] for b in boxes)
    Cc = (sum((x['it']['bb'][0] + x['it']['bb'][3]) / 2 for x in boxes) / len(boxes), sum((x['it']['bb'][1] + x['it']['bb'][4]) / 2 for x in boxes) / len(boxes))
    wf = []
    for p_ in P:   # REGRA: parede atrás dos móveis na elevação 2D (só referência, não é cotada)
        b = p_['bb']
        if not (min(p_['dim'][0], p_['dim'][1]) >= 80 and p_['dim'][2] >= 1800 and max(p_['dim'][0], p_['dim'][1]) >= 800): continue
        if ((b[0] + b[3]) / 2 - Cc[0]) * f[0] + ((b[1] + b[4]) / 2 - Cc[1]) * f[1] < -150: continue
        u0_, z0_, u1_, z1_ = geo.caixa_elev(b, f)
        if u1_ < umin_ - 400 or u0_ > umax_ + 400: continue
        u0_ = max(u0_, umin_ - 150); u1_ = min(u1_, umax_ + 150); z1_ = min(z1_, zmax_ + 100)
        if u1_ - u0_ < 5: continue
        wf.append((1e9, [(u0_, 0), (u1_, 0), (u1_, z1_), (u0_, z1_)], (0.9, 0.9, 0.9), [True] * 4))
    faces.sort(key=lambda t: -t[0]); faces = wf + faces
    return dict(w=w, f=f, faces=faces, boxes=boxes, umin=min(b['u0'] for b in boxes), umax=max(b['u1'] for b in boxes), zmax=max(b['z1'] for b in boxes))

def desenhar(page, G, ox, fy, k, baloes=None, letra=None):
    X = lambda u: ox + (u - G['umin']) * k
    Y = lambda z: fy - z * k
    sh = page.new_shape()
    for dep, pts, cor, ft in G['faces']:
        q = [(X(u), Y(z)) for u, z in pts]
        if area2(q) < 0.15: continue
        sh.draw_polyline(q + [q[0]]); sh.finish(color=cor, fill=cor, width=0.45, closePath=True)
        for (a_, b_), f_ in zip(zip(q, q[1:] + q[:1]), ft):
            if f_: sh.draw_line(a_, b_)
        sh.finish(color=(0.2, 0.2, 0.2), width=0.3)
    sh.draw_line((X(G['umin']) - 6, fy), (X(G['umax']) + 6, fy)); sh.finish(color=PRETO, width=0.9)
    sh.commit()

def render3d(page, rect, pids, letra=None, ang=15, elev=12, abertas=False):
    its = [i for w in pids for i in PW[w]['itens']]
    U = list(its[0]['bb'])
    for i in its: U = geo.uniao(U, i['bb'])
    E = [U[0] - 80, U[1] - 80, U[2] - 80, U[3] + 80, U[4] + 80, U[5] + 80]
    f = FV[PW[pids[0]]['key']]; sg = 1
    # REGRA: câmera sempre na FRENTE dos móveis (lado das portas)
    _ip = set(pi for i in inst for pi in i['pecas']); Cm = ((U[0] + U[3]) / 2, (U[1] + U[4]) / 2)
    _mb = [i['bb'] for i in inst if i['tipo'] == 'mod']
    _dr = [q for q in P if q['i'] not in _ip and q['dim'][2] >= 400 and min(q['dim'][0], q['dim'][1]) <= 26 and not any(all(q['bb'][k] >= m_[k] - 2 for k in range(3)) and all(q['bb'][k + 3] <= m_[k + 3] + 2 for k in range(3)) for m_ in _mb) and all(q['bb'][k] >= U[k] - 80 for k in range(3)) and all(q['bb'][k + 3] <= U[k + 3] + 80 for k in range(3))]
    if _dr:
        dx_ = sum((q['bb'][0] + q['bb'][3]) / 2 for q in _dr) / len(_dr) - Cm[0]; dy_ = sum((q['bb'][1] + q['bb'][4]) / 2 for q in _dr) / len(_dr) - Cm[1]
        if f[0] * dx_ + f[1] * dy_ > 0: f = (-f[0], -f[1])
    if len(pids) > 1:
        f2 = FV[PW[pids[1]]['key']]; sg = 1 if f[0] * f2[1] - f[1] * f2[0] >= 0 else -1
    a = math.radians(ang * sg); hx = f[0] * math.cos(a) - f[1] * math.sin(a); hy = f[0] * math.sin(a) + f[1] * math.cos(a)
    e = math.radians(elev); d = (hx * math.cos(e), hy * math.cos(e), -math.sin(e))
    rn = math.hypot(hy, hx); r = (hy / rn, -hx / rn, 0.0)
    up = (r[1] * d[2] - r[2] * d[1], r[2] * d[0] - r[0] * d[2], r[0] * d[1] - r[1] * d[0])
    dot = lambda a_, b_: a_[0] * b_[0] + a_[1] * b_[1] + a_[2] * b_[2]
    cor = {}; ocup = set()
    for i in inst:
        for pi in i['pecas']: cor[pi] = MADEIRA if i['tipo'] == 'comp' else (0.97, 0.97, 0.97); ocup.add(pi)
    dentro = [p_ for p_ in P if all(p_['bb'][k] >= E[k] for k in range(3)) and all(p_['bb'][k + 3] <= E[k + 3] for k in range(3))]
    rot = {}; portas = []
    if abertas:
        mods = [i for i in its if i['tipo'] == 'mod']
        for p_ in dentro:
            if p_['i'] in ocup or p_['dim'][2] < 400: continue
            for m in mods:
                fm = FV[PW[m['parede']]['key']]; ax = 0 if fm[0] else 1
                if p_['dim'][ax] > 26 or p_['dim'][1 - ax] < 150: continue
                front = m['bb'][ax] if fm[ax] > 0 else m['bb'][ax + 3]
                back = p_['bb'][ax + 3] if fm[ax] > 0 else p_['bb'][ax]
                if abs(back - front) > 45: continue
                a0, a1 = m['bb'][1 - ax], m['bb'][4 - ax]; d0, d1 = p_['bb'][1 - ax], p_['bb'][4 - ax]
                if min(a1, d1) - max(a0, d0) < 0.5 * (d1 - d0): continue
                hinge = d0 if (d0 - a0) <= (a1 - d1) else d1
                pv = (back, hinge) if ax == 0 else (hinge, back)
                cx, cy = (p_['bb'][0] + p_['bb'][3]) / 2, (p_['bb'][1] + p_['bb'][4]) / 2
                best = None
                for sg_ in (1, -1):
                    t = math.radians(95 * sg_); c_, s_ = math.cos(t), math.sin(t)
                    vx = (cx - pv[0]) * c_ - (cy - pv[1]) * s_; vy = (cx - pv[0]) * s_ + (cy - pv[1]) * c_
                    if vx * (-fm[0]) + vy * (-fm[1]) > 0: best = (pv[0], pv[1], c_, s_)
                if best: rot[p_['i']] = best; portas.append((p_, fm, ax, best))
                break
        for p_ in dentro:
            if p_['i'] in ocup or p_['i'] in rot or max(p_['dim']) >= 400: continue
            for d_, fm, ax, tr in portas:
                b = p_['bb']; db = d_['bb']
                if b[1 - ax] >= db[1 - ax] - 5 and b[4 - ax] <= db[4 - ax] + 5 and b[2] >= db[2] - 5 and b[5] <= db[5] + 5 and \
                   ((fm[ax] > 0 and b[ax] >= db[ax] - 90 and b[ax + 3] <= db[ax + 3] + 2) or (fm[ax] < 0 and b[ax + 3] <= db[ax + 3] + 90 and b[ax] >= db[ax] - 2)):
                    rot[p_['i']] = tr; break
    def tf(v, tr):
        if not tr: return v
        px, py, c_, s_ = tr; x, y = v[0] - px, v[1] - py
        return (px + x * c_ - y * s_, py + x * s_ + y * c_, v[2])
    L = (0.35, -0.45, 0.82); nl = math.sqrt(dot(L, L)); fcs = []
    for p_ in dentro:
        base = cor.get(p_['i'], (0.80, 0.80, 0.83)); tr = rot.get(p_['i'])
        for uq, nv, ft in p_['fq']:
            vs = [tf(v, tr) for v in uq]; nm = _n(vs[0], vs[1], vs[2])
            fs_ = 0.72 + 0.28 * abs(dot(nm, L)) / nl
            fcs.append((sum(dot(v, d) for v in vs) / len(vs), [(dot(v, r), dot(v, up)) for v in vs], tuple(min(1, x * fs_) for x in base), ft))
    Cc = ((U[0] + U[3]) / 2, (U[1] + U[4]) / 2); wf = []
    for p_ in P:   # REGRA: paredes aparecem para referência
        b = p_['bb']
        if not (min(p_['dim'][0], p_['dim'][1]) >= 80 and p_['dim'][2] >= 1800 and max(p_['dim'][0], p_['dim'][1]) >= 800): continue
        if b[3] < E[0] - 400 or b[0] > E[3] + 400 or b[4] < E[1] - 400 or b[1] > E[4] + 400: continue
        if ((b[0] + b[3]) / 2 - Cc[0]) * d[0] + ((b[1] + b[4]) / 2 - Cc[1]) * d[1] < -150: continue
        for uq, nv, ft in p_['fq']:
            nm = _n(uq[0], uq[1], uq[2]); fs_ = 0.8 + 0.2 * abs(dot(nm, L)) / nl
            wf.append((sum(dot(v, d) for v in uq) / len(uq), [(dot(v, r), dot(v, up)) for v in uq], (0.9 * fs_,) * 3, ft))
    fcs.sort(key=lambda t: -t[0]); wf.sort(key=lambda t: -t[0]); fcs = wf + fcs
    if not fcs: return
    xs = [x for _, q, _, _ in fcs for x, _ in q]; ys = [y for _, q, _, _ in fcs for _, y in q]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k = min((rect.width - 16) / (x1 - x0), (rect.height - 16) / (y1 - y0))
    ox = rect.x0 + (rect.width - (x1 - x0) * k) / 2; oy = rect.y0 + (rect.height - (y1 - y0) * k) / 2
    T = lambda x, y: (ox + (x - x0) * k, oy + (y1 - y) * k)
    sh = page.new_shape()
    for dep, q, c_, ft in fcs:
        Q = [T(x, y) for x, y in q]
        if area2(Q) < 0.1: continue
        sh.draw_polyline(Q + [Q[0]]); sh.finish(color=c_, fill=c_, width=0.5, closePath=True)
        for (a_, b_), f_ in zip(zip(Q, Q[1:] + Q[:1]), ft):
            if f_: sh.draw_line(a_, b_)
        sh.finish(color=(0.2, 0.2, 0.2), width=0.35)
    sh.commit()
    if letra:
        for i in its:
            nb = i.get('num_' + letra)
            if not nb: continue
            b = i['bb']; c3 = ((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2)
            cx, cy = T(dot(c3, r), dot(c3, up)); t_ = str(nb); wv = fz.get_text_length(t_, 'hebo', 7) + 4
            page.draw_rect(fz.Rect(cx - wv / 2, cy - 5.5, cx + wv / 2, cy + 5.5), color=PRETO, fill=(1, 1, 0), width=0.4)
            page.insert_text((cx - wv / 2 + 2, cy + 2.5), t_, fontname='hebo', fontsize=7)


# ===== REGRAS FIXAS (João): LISTAGEM = 3D FRONTAL, PORTAS FECHADAS, COM PAREDES | COTAS = 2D FRONTAL, PORTAS ABERTAS, COM PAREDES, SÓ MÓDULOS + PRATELEIRAS =====
PAREDES_PECAS = [p_ for p_ in P if p_['dim'][2] >= 2000 and min(p_['dim'][0], p_['dim'][1]) >= 80 and max(p_['dim'][0], p_['dim'][1]) >= 1000]
def caixa_faces(b):
    x0, y0, z0, x1, y1, z1 = b
    V_ = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    return [[V_[a] for a in fc] for fc in [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]]
def paredes_recorte(R):
    out = []
    for p_ in PAREDES_PECAS:
        b = p_['bb']; c = [max(b[k], R[k]) for k in range(3)] + [min(b[k + 3], R[k + 3]) for k in range(3)]
        if all(c[k + 3] - c[k] > 1 for k in range(3)): out.append(c)
    return out

def geom_parede(w):
    f = FV[w['key']]; faces = []; boxes = []
    dep = lambda vs: sum(v[0] * f[0] + v[1] * f[1] for v in vs) / len(vs)
    for it in w['itens']:
        cor = MADEIRA if it['tipo'] == 'comp' else BRANCO
        for pi in it['pecas']:
            sd_ = sorted(P[pi]['dim'])
            if sd_[1] < 50 or sd_[0] > 60: continue  # REGRA: só MDF (sem dobradiças/suportes/cabideiros)
            for uq, nv, ft in P[pi]['fq']:
                faces.append((dep(uq), [(uu(v[0], v[1], f), v[2]) for v in uq], P[pi].get('rgb', cor), ft))
        u0, z0, u1, z1 = geo.caixa_elev(it['bb'], f)
        boxes.append(dict(it=it, u0=u0, z0=z0, u1=u1, z1=z1))
    Ub = list(w['itens'][0]['bb'])
    for it in w['itens']: Ub = geo.uniao(Ub, it['bb'])
    R = [Ub[0] - 100, Ub[1] - 100, 0, Ub[3] + 100, Ub[4] + 100, Ub[5] + 100]
    if f[0] > 0: R[3] += 300
    if f[0] < 0: R[0] -= 300
    if f[1] > 0: R[4] += 300
    if f[1] < 0: R[1] -= 300
    for b in paredes_recorte(R):
        for fc in caixa_faces(b):
            faces.append((dep(fc), [(uu(v[0], v[1], f), v[2]) for v in fc], (0.9, 0.9, 0.9), [True] * 4))
    umin_ = min(b['u0'] for b in boxes); umax_ = max(b['u1'] for b in boxes); zmax_ = max(b['z1'] for b in boxes)
    Cc = (sum((x['it']['bb'][0] + x['it']['bb'][3]) / 2 for x in boxes) / len(boxes), sum((x['it']['bb'][1] + x['it']['bb'][4]) / 2 for x in boxes) / len(boxes))
    wf = []
    for p_ in P:   # REGRA: parede atrás dos móveis na elevação 2D (só referência, não é cotada)
        b = p_['bb']
        if not (min(p_['dim'][0], p_['dim'][1]) >= 80 and p_['dim'][2] >= 1800 and max(p_['dim'][0], p_['dim'][1]) >= 800): continue
        if ((b[0] + b[3]) / 2 - Cc[0]) * f[0] + ((b[1] + b[4]) / 2 - Cc[1]) * f[1] < -150: continue
        u0_, z0_, u1_, z1_ = geo.caixa_elev(b, f)
        if u1_ < umin_ - 400 or u0_ > umax_ + 400: continue
        u0_ = max(u0_, umin_ - 150); u1_ = min(u1_, umax_ + 150); z1_ = min(z1_, zmax_ + 100)
        if u1_ - u0_ < 5: continue
        wf.append((1e9, [(u0_, 0), (u1_, 0), (u1_, z1_), (u0_, z1_)], (0.9, 0.9, 0.9), [True] * 4))
    faces.sort(key=lambda t: -t[0]); faces = wf + faces
    return dict(w=w, f=f, faces=faces, boxes=boxes, umin=min(b['u0'] for b in boxes), umax=max(b['u1'] for b in boxes), zmax=max(b['z1'] for b in boxes))

def _ordem_pecas(fcs, bbs, cam):
    # Ordem de desenho POR PEÇA (pintor): A antes de B quando B está na frente de A.
    # Frente/trás pelo eixo de menor sobreposição das caixas (dobradiça/cabideiro atrás da porta fica atrás).
    import heapq
    fundo = sorted([f_ for f_ in fcs if f_[5] < 0], key=lambda t: -t[1])
    por = {}
    for f_ in fcs:
        if f_[5] >= 0: por.setdefault(f_[5], []).append(f_)
    ids = list(por)
    tela = {}
    for i_ in ids:
        xs_ = [x for f_ in por[i_] for x, _ in f_[2]]; ys_ = [y for f_ in por[i_] for _, y in f_[2]]
        tela[i_] = (min(xs_), min(ys_), max(xs_), max(ys_))
    ctr = {i_: [(bbs[i_][k] + bbs[i_][k + 3]) / 2 for k in range(3)] for i_ in ids}
    dist = {i_: math.dist(ctr[i_], cam) for i_ in ids}
    def frente(a, b):  # 1: a na frente de b | -1: b na frente de a | 0: indefinido
        A, B = bbs[a], bbs[b]
        ov = sorted((min(A[k + 3], B[k + 3]) - max(A[k], B[k]), k) for k in range(3))
        for o_, k in ov:
            ca, cb = ctr[a][k], ctr[b][k]
            if abs(ca - cb) < 1e-6: continue
            if cam[k] > max(ca, cb) or cam[k] < min(ca, cb):
                return 1 if abs(cam[k] - ca) < abs(cam[k] - cb) else -1
            if o_ > 0.5: break
        return 0
    depois = {i_: [] for i_ in ids}; grau = {i_: 0 for i_ in ids}
    for n_, a in enumerate(ids):
        ta = tela[a]
        for b in ids[n_ + 1:]:
            tb = tela[b]
            if ta[2] <= tb[0] or tb[2] <= ta[0] or ta[3] <= tb[1] or tb[3] <= ta[1]: continue
            r_ = frente(a, b)
            if r_ > 0: depois[b].append(a); grau[a] += 1
            elif r_ < 0: depois[a].append(b); grau[b] += 1
    hp = [(-dist[i_], i_) for i_ in ids if grau[i_] == 0]; heapq.heapify(hp)
    feito = set(); out = list(fundo)
    while len(feito) < len(ids):
        if not hp:
            i_ = max((j for j in ids if j not in feito), key=lambda j: dist[j]); grau[i_] = 0
        else: _, i_ = heapq.heappop(hp)
        if i_ in feito: continue
        feito.add(i_); out += sorted(por[i_], key=lambda t: -t[1])
        for j in depois[i_]:
            grau[j] -= 1
            if grau[j] == 0 and j not in feito: heapq.heappush(hp, (-dist[j], j))
    return out

def render3d(page, rect, pids, letra=None, **kw):
    its = [i for w in pids for i in PW[w]['itens']]
    U = list(its[0]['bb'])
    for i in its: U = geo.uniao(U, i['bb'])
    E = [U[0] - 80, U[1] - 80, U[2] - 80, U[3] + 80, U[4] + 80, U[5] + 80]
    f = FV[PW[pids[0]]['key']]; a = 0.0
    if len(pids) > 1:
        f2 = FV[PW[pids[1]]['key']]; a = math.radians(22 if f[0] * f2[1] - f[1] * f2[0] >= 0 else -22)
    hx = f[0] * math.cos(a) - f[1] * math.sin(a); hy = f[0] * math.sin(a) + f[1] * math.cos(a)
    e = math.radians(9); fw = (hx * math.cos(e), hy * math.cos(e), -math.sin(e))
    rn = math.hypot(hy, hx); r = (hy / rn, -hx / rn, 0.0)
    up = (r[1] * fw[2] - r[2] * fw[1], r[2] * fw[0] - r[0] * fw[2], r[0] * fw[1] - r[1] * fw[0])
    dot = lambda a_, b_: a_[0] * b_[0] + a_[1] * b_[1] + a_[2] * b_[2]
    tc = ((U[0] + U[3]) / 2, (U[1] + U[4]) / 2, (U[2] + U[5]) / 2)
    D = max(max(U[3] - U[0], U[4] - U[1], U[5] - U[2]) * 1.9, 4200)  # parede pequena: câmera não chega perto demais (sem distorção)
    cam = (tc[0] - fw[0] * D, tc[1] - fw[1] * D, tc[2] - fw[2] * D)
    cor = {}
    for i in inst:
        for pi in i['pecas']: cor[pi] = MADEIRA if i['tipo'] == 'comp' else (0.97, 0.97, 0.97)
    src = []; shell = []
    for p_ in P:
        b = p_['bb']
        sd_ = sorted(p_['dim'])
        if sd_[1] < 50 or sd_[0] > 60: continue  # REGRA: 3D só com MDF (chapas); suportes, dobradiças, cabideiros, pés = fora
        if all(b[k] >= E[k] for k in range(3)) and all(b[k + 3] <= E[k + 3] for k in range(3)):
            base = p_.get('rgb') or cor.get(p_['i'], (0.80, 0.80, 0.83))
            for uq, nv, ft in p_['fq']: src.append((uq, base, ft, 1, len(shell)))
            shell.append(b)
    R = [U[0] - 700, U[1] - 700, 0, U[3] + 700, U[4] + 700, U[5] + 150]
    for b in paredes_recorte(R):
        for fc in caixa_faces(b): src.append((fc, (0.94, 0.94, 0.94), [True] * 4, 0, -1))
    L = (0.35, -0.45, 0.82); nl = math.sqrt(dot(L, L))
    def pj(v):
        rel = (v[0] - cam[0], v[1] - cam[1], v[2] - cam[2]); z = dot(rel, fw)
        return (dot(rel, r) / z, dot(rel, up) / z, z)
    fcs = []
    for vs, base, ft, gr, pc in src:
        pp = [pj(v) for v in vs]
        if min(t[2] for t in pp) < 50: continue
        nm = _n(vs[0], vs[1], vs[2]); fs_ = 0.72 + 0.28 * abs(dot(nm, L)) / nl
        fcs.append((gr, sum(t[2] for t in pp) / len(pp), [(t[0], t[1]) for t in pp], tuple(min(1, x * fs_) for x in base), ft, pc))
    if not fcs: return
    fcs = _ordem_pecas(fcs, shell, cam)
    xs = [x for f_ in fcs for x, _ in f_[2]]; ys = [y for f_ in fcs for _, y in f_[2]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k = min((rect.width - 16) / (x1 - x0), (rect.height - 16) / (y1 - y0))
    ox = rect.x0 + (rect.width - (x1 - x0) * k) / 2; oy = rect.y0 + (rect.height - (y1 - y0) * k) / 2
    T = lambda x, y: (ox + (x - x0) * k, oy + (y1 - y) * k)
    sh = page.new_shape()
    for gr_, dep_, q, c_, ft, _pc in fcs:
        Q = [T(x, y) for x, y in q]
        if area2(Q) < 0.1: continue
        sh.draw_polyline(Q + [Q[0]]); sh.finish(color=c_, fill=c_, width=0.5, closePath=True)
        for (a_, b_), f_ in zip(zip(Q, Q[1:] + Q[:1]), ft):
            if f_: sh.draw_line(a_, b_)
        sh.finish(color=(0.2, 0.2, 0.2), width=0.35)
    sh.commit()
    if letra:
        for i in its:
            nb = i.get('num_' + letra)
            if not nb: continue
            b = i['bb']; fi = FV[PW[i['parede']]['key']]; axi = 0 if fi[0] else 1
            c3 = [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2]
            c3[axi] = b[axi] if fi[axi] > 0 else b[axi + 3]
            t3 = pj(c3); cx, cy = T(t3[0], t3[1]); t_ = str(nb); wv = fz.get_text_length(t_, 'hebo', 7) + 4
            page.draw_rect(fz.Rect(cx - wv / 2, cy - 5.5, cx + wv / 2, cy + 5.5), color=PRETO, fill=(1, 1, 0), width=0.4)
            page.insert_text((cx - wv / 2 + 2, cy + 2.5), t_, fontname='hebo', fontsize=7)


import xml.etree.ElementTree as _ET
_todas = [e.get('DESCRIPTION', '') for e in _ET.parse(cfg['xml']).iter('ITEM')] if cfg.get('xml') else []
def _pega(rx):
    v = sorted(set(re.sub(r'\s+', ' ', x).strip() for x in _todas if re.search(rx, x, re.I)))
    return ', '.join(v[:3]) if v else 'Não possui'
# ---------------- montagem ----------------
doc = fz.open(); n = 0; relat = []
n += 1; p = nova_prancha(doc, n, 'CAPA')
(encaixa(p, cfg['capa_img'], fz.Rect(AREA_IN.x0, AREA_IN.y0 + 34, AREA_IN.x1, AREA_IN.y1)) if cfg.get('capa_img') else render3d(p, fz.Rect(AREA_IN.x0, AREA_IN.y0 + 34, AREA_IN.x1, AREA_IN.y1), [w['id'] for w in paredes]))
t = f"CADERNO DE {cfg['tipo_caderno']} - {cfg['dados']['ambiente'].upper()}"
p.insert_text((419.5 - fz.get_text_length(t, 'hebo', 18) / 2, AREA_IN.y0 + 22), t, fontname='hebo', fontsize=18, color=RED)

n += 1; p = nova_prancha(doc, n, 'CONTRATO')
ct = fz.open(cfg['contrato_fonte']); clip = fz.Rect(AREA.x0 + 2, 143, AREA.x1 - 2, 540)
p.show_pdf_page(clip, ct, 0, clip=clip)

# PRANCHA 3: especificações + planta do DXF com cotas e indicação das vistas
n += 1; p = nova_prancha(doc, n, 'PLANTA - ESPECIFICAÇÕES DO PROJETO')
esp = fz.Rect(AREA_IN.x0, AREA_IN.y0, AREA_IN.x0 + 225, AREA_IN.y1)
p.draw_rect(esp, color=PRETO, width=0.6)
confere = cfg.get('xml_confere', True)
# REGRA (João): especificações no modelo fixo, preenchidas com o que está no XML (nome exato). Sem item no projeto = em branco.
def _espec(xml):
    lim = lambda t: re.sub(r'[^\w)\]]+$', '', re.sub(r'\s+', ' ', t or '')).strip()
    root_ = ET.parse(xml).getroot()
    cor_, esp_ = {}, {}
    def add(cl, c, e):
        cor_.setdefault(cl, _col.Counter())[c] += 1
        esp_.setdefault(cl, set()).add(e)
    for it in root_.iter('ITEM'):
        its_ = it.find('ITEMS')
        if its_ is None: continue
        ch = [c for c in its_.findall('ITEM') if re.match(r'Chapa .+ Espessura', c.get('DESCRIPTION', ''))]
        if not ch: continue
        m_ = re.match(r'Chapa (.+?) Espessura ([\d.,]+)\s*mm', ch[0].get('DESCRIPTION'))
        if not m_: continue
        c, e = m_.group(1).strip(), fmt(float(m_.group(2).replace(',', '.')))
        I, D = (it.get('ID') or '').lower(), (it.get('DESCRIPTION') or '')
        if re.search(r'(^|_)por_', I): add('porta', c, e)
        elif '_gav' in I: continue                                   # corpo da gaveta
        elif re.search(r'tamponamento', D, re.I): add('tamp', c, e)
        elif re.search(r'afastador', D, re.I): add('caixa', c, e)
        elif re.search(r'painel|tampo', D, re.I) or re.search(r'(^|_)(tam|tampo)(_|$)', I): add('painel', c, e)
        elif '_pra' in I or re.match(r'prat', D, re.I): add('prat', c, e)
        elif '_fun' in I: esp_.setdefault('fundo', set()).add(e)
        else: add('caixa', c, e)
    todos_ = [(it.get('DESCRIPTION') or '', it) for it in root_.iter('ITEM')]
    nomes = lambda rx: list(OrderedDict((lim(d), 1) for d, _ in todos_ if re.search(rx, d, re.I)))
    pux_n, pux_c = [], []
    for d, it in todos_:
        if re.match(r'puxador', d, re.I):
            rf = {g.tag: g.get('REFERENCE') for g in (it.find('REFERENCES') or [])}
            n_ = lim(d); lg = rf.get('LARGURA')
            if lg and lg + 'mm' not in n_: n_ += f' - {lg}mm'
            if n_ not in pux_n: pux_n.append(n_)
            a_ = lim(rf.get('DESC_ACA_PER', ''))
            if a_ and a_ not in pux_c: pux_c.append(a_)
    esp_nome = lambda d: re.sub(r'\s*[\d.,]+\s*mm$', '', d).strip()
    especiais = list(OrderedDict((esp_nome(lim(d)), 1) for d, it in todos_ if it.get('COMPONENT') == 'Y' and re.search(r'pist|articulad|aventos|basculant|trilho|cabideiro tubo|lixeira|cesto|porta.?tempero|sapateira|calceiro|gaveteiro aramado', d, re.I)))
    cor = lambda k: ', '.join(c for c, _ in cor_.get(k, _col.Counter()).most_common())
    mm = lambda k: ' e '.join(f'{e}mm' for e in sorted(esp_.get(k, ()), key=lambda t: float(t.replace(',', '.'))))
    cx = mm('caixa') + (f" (fundo {mm('fundo')})" if esp_.get('fundo') else '')
    return [('ESPECIFICAÇÕES DO PROJETO', None), ('CORES E ACABAMENTOS:', None),
            ('Caixa Módulos (Interno)', cor('caixa')), ('Portas e Frentes', cor('porta')), ('Tamponamentos', cor('tamp')),
            ('Painéis e Tampos', cor('painel')), ('Puxadores', ', '.join(pux_c)), ('Portas de Vidro', ', '.join(nomes(r'vidro|espelho'))),
            ('FERRAGENS E ACESSÓRIOS:', None),
            ('Dobradiças', ', '.join(nomes(r'^dobradi'))), ('Corrediças', ', '.join(nomes(r'corredi'))),
            ('Puxadores', ', '.join(pux_n)), ('Ferragens especiais', ', '.join(especiais)),
            ('ESPESSURAS:', None),
            ('Caixa Módulos (Interno)', cx), ('Prateleiras internas', mm('prat')), ('Portas e Frentes', mm('porta')),
            ('Tamponamentos', mm('tamp')), ('Painéis e Tampos e perfil', mm('painel'))]
itens_esp = _espec(cfg['xml'])
if not confere:
    itens_esp = [(r_, v_ if v_ is None or 'mm' in v_ else 'CONFERIR') for r_, v_ in itens_esp]
_FH, _FB = fz.Font('helv'), fz.Font('hebo')
def _quebra(t, larg, fs):
    ls, cur = [], ''
    for w_ in t.split(' '):
        tt = (cur + ' ' + w_).strip()
        if cur and _FB.text_length(tt, fs) > larg: ls.append(cur); cur = w_
        else: cur = tt
    return ls + ([cur] if cur else [])
y = esp.y0 + 14
for rot, v in itens_esp:
    if v is None:
        if y > esp.y0 + 20: y += 4
        p.insert_text((esp.x0 + 6, y), rot, fontname='hebo', fontsize=8.5, color=RED if y == esp.y0 + 14 else PRETO)
        y += 14; continue
    rt = rot + ': '; rw = _FH.text_length(rt, 7.3) + 1.5
    p.insert_text((esp.x0 + 6, y), rt, fontname='helv', fontsize=7.3)
    ls = _quebra(v, esp.width - 12 - rw, 7.3) if v else []
    if len(ls) > 1: ls = _quebra(v, esp.width - 18, 7.3); y += 9.5; x_ = esp.x0 + 12
    else: x_ = esp.x0 + 6 + rw
    for l_ in ls:
        p.insert_text((x_, y), l_, fontname='hebo', fontsize=7.3, color=(0.7, 0, 0) if v == 'CONFERIR' else PRETO); y += 9.5
    y += 3.5 if ls else 13
if not confere:
    p.insert_text((esp.x0 + 6, esp.y1 - 8), 'XML da pasta é de outra versão: exportar o atual', fontname='helv', fontsize=6.5, color=(0.7, 0, 0))
# planta
pr = fz.Rect(esp.x1 + 8, AREA_IN.y0, AREA_IN.x1, AREA_IN.y1)
todos = [pi for it in inst for pi in it['pecas']]
xs0 = min(P[i]['bb'][0] for i in todos); xs1 = max(P[i]['bb'][3] for i in todos)
ys0 = min(P[i]['bb'][1] for i in todos); ys1 = max(P[i]['bb'][4] for i in todos)
S, k = escala_para(xs1 - xs0, ys1 - ys0, pr.width - 110, pr.height - 90)
ox = pr.x0 + (pr.width - (xs1 - xs0) * k) / 2; oy = pr.y0 + (pr.height - (ys1 - ys0) * k) / 2
PX = lambda x: ox + (x - xs0) * k
PY = lambda y_: oy + (ys1 - y_) * k
cor_de = {}
for it in inst:
    for pi in it['pecas']: cor_de[pi] = MADEIRA if it['tipo'] == 'comp' else BRANCO
fcs = []
for p_ in P:
    b = p_['bb']
    if b[3] < xs0 - 300 or b[0] > xs1 + 300 or b[4] < ys0 - 300 or b[1] > ys1 + 300 or b[2] > 2600: continue
    if p_['dim'][0] > 6000 or p_['dim'][1] > 6000: continue
    if p_['dim'][2] < 40 and p_['dim'][0] > 1200 and p_['dim'][1] > 1200: continue
    for uq, nv, ft in p_['fq']:
        q = [(PX(v[0]), PY(v[1])) for v in uq]
        if area2(q) < 0.2: continue
        fcs.append((max(v[2] for v in uq), q, cor_de.get(p_['i']), ft))
fcs.sort(key=lambda t: t[0])
sh = p.new_shape()
for z, q, cor, ft in fcs:
    q = [(min(max(a, pr.x0), pr.x1), min(max(b_, pr.y0), pr.y1)) for a, b_ in q]
    fill = cor or BRANCO
    sh.draw_polyline(q + [q[0]]); sh.finish(color=fill, fill=fill, width=0.4, closePath=True)
    for (a_, b_), f_ in zip(zip(q, q[1:] + q[:1]), ft):
        if f_: sh.draw_line(a_, b_)
    sh.finish(color=PRETO if cor is None else (0.3, 0.3, 0.3), width=0.5 if cor is None else 0.3)
sh.commit()
for w in paredes:          # cotas da planta: por parede, do lado de fora
    f = FV[w['key']]; its = w['itens']
    if w['key'][0] == 'x':
        vals = [v for i in its for v in (i['bb'][1], i['bb'][4])]
        xl = PX(w['plano']) + (14 if f[0] > 0 else -14)
        cadeia_v(p, vals, xl, None, PY, fs=6)
    else:
        vals = [v for i in its for v in (i['bb'][0], i['bb'][3])]
        yl = PY(w['plano']) + (14 if f[1] < 0 else -14)
        cadeia_h(p, vals, yl, yl, PX, fs=6)
for v in V:                # setas das vistas
    w = PW[v['paredes'][0]]; f = FV[w['key']]; its = w['itens']
    cx = sum((i['bb'][0] + i['bb'][3]) / 2 for i in its) / len(its); cy = sum((i['bb'][1] + i['bb'][4]) / 2 for i in its) / len(its)
    ex, ey = PX(cx) - f[0] * 30, PY(cy) + f[1] * 30
    sx, sy = ex - f[0] * 32, ey + f[1] * 32
    p.draw_line((sx, sy), (ex, ey), color=RED, width=1.4)
    p.draw_polyline([(ex + f[1] * 4 - f[0] * 7, ey + f[0] * 4 + f[1] * 7), (ex, ey), (ex - f[1] * 4 - f[0] * 7, ey - f[0] * 4 + f[1] * 7)], color=RED, width=1.4)
    p.draw_circle((sx - f[0] * 8, sy + f[1] * 8), 7, color=RED, fill=BRANCO, width=1)
    p.insert_text((sx - f[0] * 8 - 3.5, sy + f[1] * 8 + 3.5), v['letra'], fontname='hebo', fontsize=10, color=RED)
lab = f'PLANTA BAIXA - ESC. 1:{S}'
p.insert_text((pr.x0 + pr.width / 2 - fz.get_text_length(lab, 'hebo', 8) / 2, pr.y1 - 3), lab, fontname='hebo', fontsize=8)

# PRANCHA 4: visão geral
n += 1; p = nova_prancha(doc, n, 'VISÃO GERAL DOS MÓVEIS')
com_img = V
m = len(com_img); a = AREA_IN
_nc = 1 if m == 1 else 2 if m <= 4 else 3; _nr = -(-m // _nc)
cel = [fz.Rect(a.x0 + (i % _nc) * a.width / _nc, a.y0 + (i // _nc) * a.height / _nr, a.x0 + (i % _nc + 1) * a.width / _nc, a.y0 + (i // _nc + 1) * a.height / _nr) for i in range(m)]
for v, c in zip(com_img, cel):
    (encaixa(p, v['img3d'], fz.Rect(c.x0 + 4, c.y0 + 16, c.x1 - 4, c.y1 - 4)) if v.get('img3d') else render3d(p, fz.Rect(c.x0 + 4, c.y0 + 16, c.x1 - 4, c.y1 - 4), v['paredes']))
    p.insert_text((c.x0 + 6, c.y0 + 11), f"VISTA {v['letra']}", fontname='hebo', fontsize=10, color=RED)
for j in range(1, _nc): p.draw_line((a.x0 + j * a.width / _nc, AREA.y0), (a.x0 + j * a.width / _nc, AREA.y1), color=PRETO, width=0.6)
for j in range(1, _nr): p.draw_line((AREA.x0, a.y0 + j * a.height / _nr), (AREA.x1, a.y0 + j * a.height / _nr), color=PRETO, width=0.6)

# por vista: listagem (tabela + balões na elevação + 3D) e cotas
for v in V:
    GS = [geom_parede(PW[w]) for w in v['paredes']]
    n += 1; p = nova_prancha(doc, n, f"MÓDULOS E PAINÉIS - VISTA {v['letra']}")
    yb = tabela(p, v['linhas'], AREA_IN.x0, AREA_IN.y0)
    if nao_achados and v is V[0]:
        p.insert_text((AREA_IN.x0, yb + 9), '* não localizado no DXF - conferir', fontname='helv', fontsize=6, color=(0.7, 0, 0))
    render3d(p, fz.Rect(AREA_IN.x0 + 258, AREA_IN.y0, AREA_IN.x1, AREA_IN.y1), v['paredes'], letra=v['letra'])
    # cotas
    n += 1; p = nova_prancha(doc, n, f"MEDIDAS E ALTURAS - VISTA {v['letra']}")
    nc = len(GS); cw = AREA_IN.width / nc
    zm = max(G['zmax'] for G in GS)
    S, k = min((escala_para(G['umax'] - G['umin'], zm, cw - 95, AREA_IN.height - 105) for G in GS), key=lambda t: t[1])
    fy = AREA_IN.y0 + 42 + zm * k
    for j, G in enumerate(GS):
        cx0 = AREA_IN.x0 + j * cw
        ox = cx0 + (cw - (G['umax'] - G['umin']) * k) / 2
        desenhar(p, G, ox, fy, k)
        cotar(p, G, ox, fy, k)
        lab = f"VISTA {v['letra']}{j + 1 if nc > 1 else ''} - ESC. 1:{S}"
        p.insert_text((cx0 + cw / 2 - fz.get_text_length(lab, 'hebo', 8.5) / 2, min(fy + 44, AREA_IN.y1 - 2)), lab, fontname='hebo', fontsize=8.5)
        if j: p.draw_line((cx0, AREA.y0), (cx0, AREA.y1), color=PRETO, width=0.6)


# ===== CAPA (design fixo: quadro externo + logo + cliente + EXECUTIVO - AMBIENTE) =====
_W, _H = doc[0].rect.width, doc[0].rect.height
doc.delete_page(0); cp = doc.new_page(0, width=_W, height=_H)
_lp = fz.open(cfg['layout'])[0]
_rs = [d_['rect'] for d_ in _lp.get_drawings() if d_['rect'].width > _W * 0.8 and d_['rect'].height > _H * 0.8]
fr = max(_rs, key=lambda r: r.width * r.height) if _rs else fz.Rect(17, 17, _W - 17, _H - 17)
AC = (0.78, 0.56, 0.29); CZ = (0.30, 0.30, 0.32); cx = (fr.x0 + fr.x1) / 2
cp.draw_rect(fz.Rect(fr.x0, fr.y0, fr.x0 + 10, fr.y1), color=None, fill=AC)
cp.draw_rect(fr, color=PRETO, width=1.2)
_lg = cfg.get('logo') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'LOGO.png')
yb = fr.y0 + 200
if _lg and os.path.exists(_lg):
    _im = fz.Pixmap(_lg); lw = 340; lh = lw * _im.height / _im.width
    cp.insert_image(fz.Rect(cx - lw / 2, fr.y0 + 90, cx + lw / 2, fr.y0 + 90 + lh), filename=_lg); yb = fr.y0 + 90 + lh
y = yb + 40
cp.draw_line((cx - 45, y), (cx + 45, y), color=AC, width=2)
_nm = cfg['dados']['cliente'].upper(); fs_ = 32
while fz.get_text_length(_nm, 'hebo', fs_) > fr.width - 140: fs_ -= 1
cp.insert_text((cx - fz.get_text_length(_nm, 'hebo', fs_) / 2, y + 50), _nm, fontname='hebo', fontsize=fs_, color=CZ)
_sb = 'EXECUTIVO - ' + cfg['dados']['ambiente'].upper()
cp.insert_text((cx - fz.get_text_length(_sb, 'helv', 16) / 2, y + 82), _sb, fontname='helv', fontsize=16, color=AC)
try:
    doc.save(cfg['saida'], garbage=3, deflate=True)
except Exception:
    import time as _t; cfg['saida'] = os.path.splitext(cfg['saida'])[0] + _t.strftime('_%H%M%S') + '.pdf'; doc.save(cfg['saida'], garbage=3, deflate=True)

# ---------------- QUALIDADE (nível 1, por script) ----------------
esperado = 4 + 2 * len(V)
q = [f"# QUALIDADE — {cfg['dados']['cliente']} / {cfg['dados']['ambiente']} (gerado por script)", '',
     f"- {'APROVADO' if n == esperado else 'REPROVADO'} | nº de pranchas {n} = 4 + 2 x {len(V)} vistas",
     f"- {'APROVADO' if not nao_achados else 'INCERTO'} | itens localizados no DXF: {len(linhas) - len(nao_achados)}/{len(linhas)}"]
for d, dm in nao_achados: q.append(f"  - INCERTO: {d} {dm} (não localizado; listado com * na vista {V[0]['letra']})")
q.append(f"- {'APROVADO' if confere else 'INCERTO'} | XML confere com o projeto" + ('' if confere else ' — exportar XML atual'))
for v in V: q.append(f"- Vista {v['letra']}: paredes {', '.join(v['paredes'])} | {len(v['linhas'])} linhas de listagem")
q += [f"  {v['letra']}{i}: {d} {dm}{m_}" for v in V for i, (d, dm, m_) in enumerate(v['linhas'], 1)]
open(os.path.splitext(cfg['saida'])[0] + '_QUALIDADE.md', 'w', encoding='utf-8').write('\n'.join(q))
print('\n'.join(q))
for i in range(len(doc)):
    doc[i].get_pixmap(dpi=80).save(os.path.join(os.path.dirname(cfg['saida']), f'_prev_{i + 1}.png'))
print('OK', cfg['saida'])
