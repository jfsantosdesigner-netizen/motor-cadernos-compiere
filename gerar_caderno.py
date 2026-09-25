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
ESC = [15, 20, 25, 30, 40, 50, 75, 100, 125, 150]
ESC_COTA = [10, 12.5, 15, 20, 25, 30, 40, 50, 75, 100]   # v15: elevação de cotas usa a maior escala que cabe   # 1:15 e 1:20 só para móvel/parede pequena (ver escala_para)
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
            if re.match(r'\s*cunha', d, re.I): continue   # REGRA (v26, João): barrote/cunha não faz parte, lista só material
            if 'ACESS' in cn or U.startswith('ACE') or U.startswith('EUR_'): continue
            if '_POR_' in U or U.startswith('POR_'):   # REGRA (v26): porta avulsa do XML (POR_INF_CUR) = porta, não entra na listagem
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
# REGRA (v23, João): o motor procura as cores/texturas SOZINHO, primeiro na pasta MATERIAIS DENTRO do motor
# (C:\CLAUDE\motor vN\MATERIAIS); depois no caminho do config; por último C:\CLAUDE\MATERIAIS.
_MAT = next((c_ for c_ in (os.path.join(_MD, 'MATERIAIS'),
                           (cfg.get('materiais') if cfg.get('materiais') and os.path.isabs(cfg.get('materiais')) else os.path.join(_MD, cfg.get('materiais') or 'MATERIAIS')),
                           r'C:\CLAUDE\MATERIAIS') if os.path.isdir(c_)), os.path.join(_MD, 'MATERIAIS'))
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
def _parecido(a, b):
    # REGRA (v15): nome do XML com letra a mais/a menos ou cortado ("Metallic Sued" = "Metalic Suede")
    if a == b: return True
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)) and abs(len(a) - len(b)) <= 2: return True
    if abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 5: return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]: i += 1
    return a[i + 1:] == b[i + 1:] or a[i + 1:] == b[i:] or a[i:] == b[i + 1:]
def cor_material(nome):
    if not nome: return None
    if _cc.get(nome): return tuple(_cc[nome][0])   # 'sem textura' antigo não bloqueia nova busca
    tk = _norm(nome).split(); best = None
    for cand in ([tk] + ([tk[:-1]] if len(tk) > 1 else [])):
        n = ' '.join(cand)
        for path_, st in _idx:
            ws = st.split()
            if st == n: sc = 100
            elif all(t in ws for t in cand): sc = 60 - len(ws)
            elif len(ws) == len(cand) and all(any(_parecido(t, w_) for w_ in ws) for t in cand): sc = 40 - len(ws)
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
# ===== TEXTURAS REAIS (veio da madeira) no 3D: imagem do material aplicada em perspectiva em cada face =====
try:
    from PIL import Image as _Im, ImageDraw as _ImD
    import numpy as _np
except Exception:
    _Im = None
_TXD = os.path.join(_MD, 'texturas'); _txc = {}
def textura(nome):
    if _Im is None or not nome: return None
    if nome in _txc: return _txc[nome]
    im = None; ref = (_cc.get(nome) or [None, None])[1]
    if ref:
        fn = ref.replace('\\', '/').split('/')[-1].lower(); loc = os.path.join(_TXD, fn)
        try:
            if os.path.exists(loc): im = _Im.open(loc).convert('RGB')
            else:
                full = ref if os.path.exists(ref) else os.path.join(_MAT, ref.split('MATERIAIS', 1)[-1].lstrip('/\\'))
                if os.path.exists(full):
                    im = _Im.open(full).convert('RGB'); im.thumbnail((1024, 1024)); os.makedirs(_TXD, exist_ok=True); im.save(loc, quality=82)
        except Exception: im = None
    _txc[nome] = im; return im
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
        if rgb: p_['rgb'] = rgb; p_['mat'] = nm_; _nc += 1; _usadas[nm_] += 1
print('CORES: %d pecas coloridas pelo MATERIAIS (medidas no XML: %d)' % (_nc, len(_dm)))
TEX_FALTA = [m_ for m_ in _usadas if _cc.get(m_) and not os.path.exists(os.path.join(_MD, 'texturas', _cc[m_][1].replace('\\', '/').split('/')[-1].lower()))]
for nm_, q_ in _usadas.most_common(): print('   %-22s %4d pecas <- %s' % (nm_, q_, os.path.relpath(_cc[nm_][1], _MAT)))
_todas_mats = {r_ for c_ in _dm.values() for r_ in c_}
for nm_ in [k for k, v in _cc.items() if not v and k in _todas_mats]: print('   SEM TEXTURA:', nm_)
inst = geo.casar(P, linhas, None if cfg.get('listagem_pdf') else QT)
paredes = geo.definir_paredes(inst, P)
# REGRA: mesma parede com módulos de profundidades diferentes (ex.: armário raso 200 mm + balcão 600 mm)
# = UMA parede só. Junta paredes do mesmo lado com planos a até 600 mm e trechos que se tocam/sobrepõem.
def _juntar_paredes(paredes):
    mudou = True
    while mudou:
        mudou = False
        for a in paredes:
            for b in paredes:
                if a is b or a['key'] != b['key'] or abs(a['plano'] - b['plano']) > 600: continue
                ax = 1 if FV[a['key']][0] else 0
                ra = (min(i['bb'][ax] for i in a['itens']), max(i['bb'][ax + 3] for i in a['itens']))
                rb = (min(i['bb'][ax] for i in b['itens']), max(i['bb'][ax + 3] for i in b['itens']))
                if ra[1] < rb[0] - 100 or rb[1] < ra[0] - 100: continue
                sg = FV[a['key']][1 - ax]
                a['plano'] = max(a['plano'] * sg, b['plano'] * sg) * sg   # plano mais "no fundo"
                a['itens'] += b['itens']; paredes.remove(b); mudou = True; break
            if mudou: break
    for w in paredes:
        w['id'] = f"{w['key']}@{round(w['plano'])}"
        for it in w['itens']: it['parede'] = w['id']
    return paredes
paredes = _juntar_paredes(paredes)
# AMBIENTE (referência, NUNCA cotado): peças do DXF que não são móvel do XML nem parede/piso.
# Hoje: PEDRA / bancada / rodabanca = placa horizontal (15–100 mm) na altura da bancada (700–1100 mm).
# Desenhada com as faces reais do DXF (pedra em L sai em L).
_usadas = {pi for i in inst for pi in i['pecas']}
# REGRA (v26): peça do DXF que NÃO está na listagem e ocupa o MESMO lugar de uma peça listada (cópia do painel,
# ex.: painel usinado 1580 sobre o painel 1530 da lista) = duplicada -> não é desenhada (cobria o painel de cinza).
def _vol(b): return max(0, b[3] - b[0]) * max(0, b[4] - b[1]) * max(0, b[5] - b[2])
def _vol_int(A, B): return _vol([max(A[0], B[0]), max(A[1], B[1]), max(A[2], B[2]), min(A[3], B[3]), min(A[4], B[4]), min(A[5], B[5])]) if all(min(A[k + 3], B[k + 3]) > max(A[k], B[k]) for k in range(3)) else 0
_bb_list = [P[pi]['bb'] for pi in _usadas]
DUP_I = {p_['i'] for p_ in P if p_['i'] not in _usadas and _vol(p_['bb']) > 0 and sorted(p_['dim'])[1] >= 50
         and any(_vol_int(p_["bb"], b_) >= 0.8 * max(_vol(p_["bb"]), _vol(b_)) for b_ in _bb_list)}
if DUP_I: print('PEÇAS DUPLICADAS NO DXF (não desenhadas):', len(DUP_I))
PEDRA_COR = (0.16, 0.16, 0.17)
AMB = [p_ for p_ in P if p_['i'] not in _usadas and p_['faces'] and 15 <= p_['dim'][2] <= 100
       and max(p_['dim'][0], p_['dim'][1]) >= 500 and min(p_['dim'][0], p_['dim'][1]) >= 250 and 700 <= p_['bb'][2] <= 1100]
AMB_I = {p_['i'] for p_ in AMB}
# PAREDES REAIS do DXF (com vãos de janela/porta quando vierem): peça vertical, espessura 60–400 mm, não casada com móvel.
# PAREDES EM PEÇA ÚNICA (alguns DXF trazem a sala inteira numa camada): usa as FACES reais, nunca a caixa.
MALHA_PAR = [p_ for p_ in P if p_['i'] not in _usadas and p_['i'] not in AMB_I and p_['faces'] and p_['dim'][2] >= 1800
             and max(p_['dim'][0], p_['dim'][1]) >= 1000 and min(p_['dim'][0], p_['dim'][1]) > 400]
MALHA_I = {p_['i'] for p_ in MALHA_PAR}
for p_ in MALHA_PAR: p_['faces'] = [[tuple(v) for v in fc] for fc in p_['faces']]
# ELETROS / objetos do ambiente (geladeira, micro-ondas, forno, coifa, revestimento...): peça do DXF que não é móvel,
# parede, pedra, piso nem forro. Só referência (faces reais, cinza médio), NUNCA cotado.
ELETRO_COR = (0.72, 0.73, 0.76)
ELETROS = [p_ for p_ in P if p_['i'] not in _usadas and p_['i'] not in AMB_I and p_['i'] not in MALHA_I and p_['faces']
           and len(p_['faces']) >= 10 and sorted(p_['dim'])[0] >= 40 and sorted(p_['dim'])[1] >= 150 and max(p_['dim']) <= 2200 and p_['dim'][2] >= 100
           and p_['bb'][5] <= 2300 and not (60 <= min(p_['dim'][0], p_['dim'][1]) <= 400 and p_['dim'][2] >= 1800)]
# REGRA (João): blocos QUADRADOS (caixa simples, 12 faces) não entram — atrapalham a imagem. Fica objeto com forma
# real (> 12 faces); em cima da pedra, só o que for baixo (cuba, cooktop: até 300 mm acima da pedra).
_topo_pedra = [p_['bb'][5] for p_ in AMB]
def _eletro_ok(p_):
    if len(p_['faces']) <= 12: return False
    if p_['bb'][2] < 50 and p_['bb'][5] < 250: return False   # base/rodapé solto no chão não é eletro
    for t_ in _topo_pedra:
        if p_['bb'][2] <= t_ + 15 and p_['bb'][5] > t_ - 60: return p_['bb'][5] <= t_ + 300
    return True
ELETROS = [p_ for p_ in ELETROS if _eletro_ok(p_)]
ELETRO_I = {p_['i'] for p_ in ELETROS}
for p_ in ELETROS: p_['faces'] = [[tuple(v) for v in fc] for fc in p_['faces']]
print('AMBIENTE (eletros/objetos):', len(ELETROS), 'peças')
def _arestas(faces):
    # contorno nítido: aresta de borda ou quina (normais diferentes); diagonal de triangulação não aparece
    # só arestas RETAS de verdade (alinhadas a um eixo): quina de parede, vão de janela, borda da pedra.
    # Aresta inclinada = triangulação -> nunca aparece (evita riscos diagonais no desenho).
    reta = lambda a_, b_: sum(1 for k_ in range(3) if abs(a_[k_] - b_[k_]) > 1) <= 1
    ed = {}; nrm = [_n(fc[0], fc[1], fc[2]) for fc in faces]
    kk = lambda v: tuple(round(c, 0) for c in v)
    for i_, fc in enumerate(faces):
        for j_ in range(len(fc)):
            a_, b_ = kk(fc[j_]), kk(fc[(j_ + 1) % len(fc)])
            if a_ == b_: continue
            ed.setdefault(frozenset((a_, b_)), []).append(i_)
    out = []
    for i_, fc in enumerate(faces):
        fl = []
        for j_ in range(len(fc)):
            a_, b_ = kk(fc[j_]), kk(fc[(j_ + 1) % len(fc)])
            fs2 = ed.get(frozenset((a_, b_)), [])
            if a_ == b_ or not reta(a_, b_): fl.append(False); continue
            if len(fs2) < 2: fl.append(True); continue
            n1, n2 = nrm[fs2[0]], nrm[fs2[1]]
            fl.append(abs(sum(x * y for x, y in zip(n1, n2))) < 0.94)
        out.append(fl)
    return out
for p_ in AMB + ELETROS + MALHA_PAR:
    p_['faces'] = [[tuple(v) for v in fc] for fc in p_['faces']]; p_['ft'] = _arestas(p_['faces'])
PAR_DXF = [p_ for p_ in P if p_['i'] not in _usadas and p_['i'] not in {q['i'] for q in AMB} and p_['i'] not in ELETRO_I and 60 <= min(p_['dim'][0], p_['dim'][1]) <= 400
           and max(p_['dim'][0], p_['dim'][1]) >= 100 and p_['dim'][2] >= 100 and max(p_['dim'][0], p_['dim'][1]) < 20000
           and not (p_['bb'][2] < 50 and p_['dim'][2] < 1000)]   # peça baixa no chão (rodapé solto) não é parede
for p_ in AMB: p_['faces'] = [[tuple(v) for v in fc] for fc in p_['faces']]
print('AMBIENTE (pedra):', len(AMB), 'peças')
# ===== REGRAS ESPECIAIS (v18, PDF da Priscila) — só atuam quando o projeto tem esses móveis =====
def _sd(it): return sorted(parse_dim_(it['dim']))
def parse_dim_(dm):
    try: return [float(x) for x in re.findall(r'[\d.]+', dm.replace(',', '.'))[:3]]
    except Exception: return [0, 0, 0]
def _toca(a, b, tol=6): return geo.dist_caixas(a['bb'], b['bb']) <= tol
_comps = [i for i in inst if i['tipo'] == 'comp']
# 1) DIVISÓRIA RIPADA: 6+ ripas (espessura <= 30, largura 60-200, comprimento >= 500) na MESMA faixa de profundidade,
#    enfileiradas ao longo de um eixo. Vira um BLOCO PRÓPRIO (listagem + cotas só dela), fora das paredes.
DIVISORIAS = []
_rip = [i for i in _comps if (lambda d: d[0] <= 30 and 60 <= d[1] <= 200 and d[2] >= 500)(_sd(i))]
for axd in (0, 1):   # axd = eixo da profundidade (as ripas têm a largura de 150 nesse eixo)
    grp = {}
    for i in _rip:
        b = i['bb']
        if 60 <= b[axd + 3] - b[axd] <= 200: grp.setdefault((round(b[axd] / 10), round(b[axd + 3] / 10)), []).append(i)
    for key_, rs in grp.items():
        if len(rs) < 6 or any(i.get('_div') for i in rs): continue
        d0, d1 = min(i['bb'][axd] for i in rs), max(i['bb'][axd + 3] for i in rs)
        conj = list(rs); topo = max(i['bb'][5] for i in rs)
        for i in rs: i['_div'] = True
        mudou = True
        while mudou:
            mudou = False
            for c in _comps:
                if c.get('_div'): continue
                b = c['bb']; dentro = b[axd] >= d0 - 30 and b[axd + 3] <= d1 + 30
                faixa = b[2] <= 100 or b[5] >= topo - 130 or (b[5] - b[2]) >= 0.8 * topo
                if (dentro or faixa) and any(_toca(c, o) for o in conj):
                    conj.append(c); c['_div'] = True; topo = max(topo, b[5]); mudou = True
        DIVISORIAS.append(dict(itens=conj, axd=axd, d0=d0, d1=d1))
# 2) DIVISOR DE GAVETA (joias/talheres): 4+ peças finas (<= 18) e baixas (<= 100) de até 450 mm, nos dois sentidos,
#    encostadas, acima do piso. Sai da listagem da parede e ganha uma PRANCHA PRÓPRIA (vista de cima com cotas).
DIVISORES = []
# REGRA (v26, cozinha Priscila): divisor de TALHER de gaveta de cozinha tem peças até 750 mm (conjunto até 800 x 800);
#    as peças ficam DEITADAS (altura <= 100 mm de verdade no DXF) -> fechamento/tamponamento em pé não entra.
_dv = [i for i in _comps if not i.get('_div') and i['bb'][2] > 150 and i['bb'][5] - i['bb'][2] <= 100 and (lambda d: d[0] <= 18 and d[1] <= 100 and d[2] <= 750)(_sd(i))]
_vis = set()
for i in _dv:
    if id(i) in _vis: continue
    g_ = [i]; _vis.add(id(i)); k_ = 0
    while k_ < len(g_):
        for o in _dv:
            if id(o) not in _vis and _toca(g_[k_], o, 3): g_.append(o); _vis.add(id(o))
        k_ += 1
    ori = {0 if (o['bb'][3] - o['bb'][0]) > (o['bb'][4] - o['bb'][1]) else 1 for o in g_}
    U_ = [min(o['bb'][0] for o in g_), min(o['bb'][1] for o in g_), max(o['bb'][3] for o in g_), max(o['bb'][4] for o in g_)]
    if len(g_) >= 4 and len(ori) == 2 and U_[2] - U_[0] <= 800 and U_[3] - U_[1] <= 800:
        DIVISORES.append(g_)
# 3) GAVETA / MÓDULO MONTADO COM PAINÉIS (não é módulo do Promob): peça horizontal (fundo, >= 0,1 m²) acima de 300 mm
#    + peças do MESMO material encostadas, até 140 mm acima do fundo, 3+ em pé. Sai da parede -> prancha própria.
GAVETAS = []
_usad = {id(i) for g_ in DIVISORES for i in g_}
for fb in _comps:
    if fb.get('_div') or id(fb) in _usad or fb['bb'][2] <= 300: continue
    b = fb['bb']; dx_, dy_, dz_ = b[3] - b[0], b[4] - b[1], b[5] - b[2]
    if not (dz_ <= 30 and dx_ * dy_ >= 1e5 and max(dx_, dy_) <= 1000): continue
    mat_ = P[fb['pecas'][0]].get('mat')
    g_ = [fb]; k_ = 0
    while k_ < len(g_):
        for o in _comps:
            if o in g_ or o.get('_div') or id(o) in _usad: continue
            ob = o['bb']
            if P[o['pecas'][0]].get('mat') != mat_ or ob[2] < b[2] - 5 or ob[5] > b[2] + 140: continue
            if _toca(g_[k_], o, 3): g_.append(o)
        k_ += 1
    em_pe = [o for o in g_ if o['bb'][5] - o['bb'][2] >= 60]
    if len(g_) >= 4 and len(em_pe) >= 3:
        GAVETAS.append(g_); _usad |= {id(o) for o in g_}
_fora = {id(i) for d in DIVISORIAS for i in d['itens']} | {id(i) for g_ in DIVISORES for i in g_} | {id(i) for g_ in GAVETAS for i in g_}
if _fora:
    for w in paredes: w['itens'] = [i for i in w['itens'] if id(i) not in _fora]
    paredes = [w for w in paredes if w['itens']]
for d in DIVISORIAS:   # parede "virtual" da divisória: vista pelo lado do painel (peça larga e fina), senão pelo lado do ambiente
    axd = d['axd']; its = d['itens']
    lrg = [i for i in its if _sd(i)[1] > 300 and d['d0'] - 30 <= i['bb'][axd] and i['bb'][axd + 3] <= d['d1'] + 30]
    mid = (d['d0'] + d['d1']) / 2
    if lrg: menor = sum((i['bb'][axd] + i['bb'][axd + 3]) / 2 for i in lrg) / len(lrg) < mid
    else: menor = sum((i['bb'][axd] + i['bb'][axd + 3]) / 2 for i in inst) / len(inst) < mid
    key = ('x+' if menor else 'x-') if axd == 0 else ('y+' if menor else 'y-')
    pl = d['d1'] if menor else d['d0']
    w = dict(key=key, plano=pl, itens=its, id=f"DIVISORIA@{round(pl)}", divisoria=True)
    for i in its: i['parede'] = w['id']
    paredes.append(w); d['parede'] = w['id']
# 4) CONDIÇÃO (v22, planta do João): PERNA DO L dentro de uma parede (ex.: penteadeira em L) = VISTA PRÓPRIA.
#    Peças soltas da parede que vão bem mais fundo que os módulos (> 300 mm além da frente deles), formando um trecho de
#    600 mm+ na profundidade, viram outra "parede" vista de lado (pelo lado de dentro do L).
_novas = []
for w in [w for w in paredes if not w.get('divisoria')]:
    f_ = FV[w['key']]; ad = 0 if f_[0] else 1; al = 1 - ad; sg_ = f_[ad]
    prof_ = lambda bb: max((w['plano'] - bb[ad]) * sg_, (w['plano'] - bb[ad + 3]) * sg_)
    mods_ = [i for i in w['itens'] if i['tipo'] == 'mod']
    if not mods_: continue
    D_ = max(prof_(m['bb']) for m in mods_)
    perna = [i for i in w['itens'] if i['tipo'] == 'comp' and prof_(i['bb']) > D_ + 300]
    if len(perna) < 2: continue
    p0 = min(min((w['plano'] - i['bb'][ad]) * sg_, (w['plano'] - i['bb'][ad + 3]) * sg_) for i in perna)
    if max(prof_(i['bb']) for i in perna) - max(p0, D_) < 600: continue
    c_perna = sum((i['bb'][al] + i['bb'][al + 3]) / 2 for i in perna) / len(perna)
    c_main = sum((i['bb'][al] + i['bb'][al + 3]) / 2 for i in mods_) / len(mods_)
    maior = c_perna > c_main       # câmera olha do lado de dentro do L (onde está o resto do móvel)
    key = ('x+' if maior else 'x-') if al == 0 else ('y+' if maior else 'y-')
    pl = max(i['bb'][al + 3] for i in perna) if maior else min(i['bb'][al] for i in perna)
    w['itens'] = [i for i in w['itens'] if i not in perna]
    nw = dict(key=key, plano=pl, itens=perna, id=f"{key}@{round(pl)}L", perna_l=True, pai=w['id'])
    for i in perna: i['parede'] = nw['id']
    _novas.append(nw)
paredes += _novas
# 5) CONDIÇÃO (v26, cozinha Priscila): PAREDE CORTADA POR PILAR / VÃO DE PASSAGEM. Os móveis de uma mesma parede ficam
#    dos dois lados de uma parede real que atravessa a faixa dos móveis (pilar, verga de vão de passagem) -> são DOIS
#    ambientes: cada lado vira uma parede (vista) própria, com listagem e cotas só dele (escala maior, leitura por lado).
def _faces_parede():
    for p_ in PAR_DXF + MALHA_PAR:
        for fc in p_['faces']: yield fc
_cortadas = []
for w in [w for w in paredes if not w.get('divisoria') and not w.get('perna_l')]:
    f_ = FV[w['key']]; ad = 0 if f_[0] else 1; al = 1 - ad; sg_ = f_[ad]; pl = w['plano']
    mods_ = [i for i in w['itens'] if i['tipo'] == 'mod']
    if len(mods_) < 2: continue
    D_ = max(max((pl - m['bb'][ad]) * sg_, (pl - m['bb'][ad + 3]) * sg_) for m in mods_)
    a0, a1 = min(m['bb'][al] for m in mods_), max(m['bb'][al + 3] for m in mods_)
    cs = []
    for fc in _faces_parede():
        vs = [v[al] for v in fc]
        if max(vs) - min(vs) > 1: continue
        c = vs[0]
        if not a0 + 300 < c < a1 - 300: continue
        d0, d1 = sorted(((pl - min(v[ad] for v in fc)) * sg_, (pl - max(v[ad] for v in fc)) * sg_))
        if min(d1, D_) - max(d0, 0) >= 0.8 * D_: cs.append(c)
    cs.sort(); grp = []
    for c in cs:
        if grp and c - grp[-1][-1] <= 400: grp[-1].append(c)
        else: grp.append([c])
    partes = [w['itens']]
    for g in grp:
        c = (g[0] + g[-1]) / 2; nv = []
        for its_ in partes:
            e_ = [i for i in its_ if (i['bb'][al] + i['bb'][al + 3]) / 2 < c]; d_ = [i for i in its_ if i not in e_]
            le = sum(i['bb'][al + 3] - i['bb'][al] for i in e_ if i['tipo'] == 'mod'); ld = sum(i['bb'][al + 3] - i['bb'][al] for i in d_ if i['tipo'] == 'mod')
            nv += [e_, d_] if le >= 1000 and ld >= 1000 else [its_]
        partes = nv
    if len(partes) > 1: _cortadas.append((w, partes))
for w, partes in _cortadas:
    paredes.remove(w)
    for k_, its_ in enumerate(partes):
        nw = dict(key=w['key'], plano=w['plano'], itens=its_, id=f"{w['id']}{'abcdef'[k_]}", cortada=True)
        for i in its_: i['parede'] = nw['id']
        paredes.append(nw)
# 6) CONDIÇÃO (v26, cozinha Priscila): CONJUNTO DE PAINÉIS SEM MÓDULO (painel com nichos na ponta da parede, painel
#    no teto, barrotes/cunhas, agastadores). Paredes só com painéis que se ENCOSTAM formam UM BLOCO PRÓPRIO no fim
#    (como a divisória): listagem com o móvel sozinho (3D frontal + 3D lateral reta) e cotas frontal + lateral.
_so = [w for w in paredes if not w.get('divisoria') and not any(i['tipo'] == 'mod' for i in w['itens'])]
_blocos = []
for w in _so:
    junto = [b for b in _blocos if any(_toca(i, j, 10) for o in b for i in o['itens'] for j in w['itens'])]
    novo_ = [w] + [o for b in junto for o in b]
    _blocos = [b for b in _blocos if b not in junto] + [novo_]
BLOCOS = []
for b in _blocos:
    its_ = [i for o in b for i in o['itens']]
    if len(b) < 2 or len(its_) < 4: continue
    # frente = parede do MAIOR painel em pé (visto de frente); plano = face da parede real logo atrás (até 150 mm)
    def _af(o):
        f_ = FV[o['key']]; ad = 0 if f_[0] else 1; al = 1 - ad
        return max([(i['bb'][al + 3] - i['bb'][al]) * (i['bb'][5] - i['bb'][2]) for i in o['itens'] if i['bb'][ad + 3] - i['bb'][ad] <= 30] or [0])
    fr_ = max(b, key=_af); f_ = FV[fr_['key']]; ad = 0 if f_[0] else 1; sg_ = f_[ad]; pl = fr_['plano']
    for fc in _faces_parede():
        vs = [v[ad] for v in fc]
        if max(vs) - min(vs) <= 1 and 0 < (vs[0] - pl) * sg_ <= 150: pl_ = vs[0]; break
    else: pl_ = pl
    for o in b: paredes.remove(o)
    nicho_ = any(re.match(r'tampon', i['desc'], re.I) for i in its_) and any(_sd(i)[0] <= 8 for i in its_)
    nw = dict(key=fr_['key'], plano=pl_, itens=its_, id=f"BLOCO@{round(pl_)}", divisoria=True, bloco='PAINEL COM NICHOS' if nicho_ else 'CONJUNTO DE PAINÉIS')
    for i in its_: i['parede'] = nw['id']
    paredes.append(nw); BLOCOS.append(nw)
PW = {w['id']: w for w in paredes}
# 7) CONDIÇÃO (v26): PAINEL USINADO. Painel em pé na FRENTE de uma estrutura de nichos aberta (2 laterais + 3 ou mais
#    prateleiras logo atrás, até 150 mm) = painel com VÃOS usinados alinhados aos nichos (o DXF traz o painel inteiro).
#    Vão = largura livre entre as laterais x altura livre entre prateleiras (> 150 mm). O painel é desenhado com os vãos.
def _caixa_fq(b):
    x0, y0, z0, x1, y1, z1 = b
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    F = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (3, 2, 6, 7), (0, 3, 7, 4), (1, 2, 6, 5)]
    N = [(0, 0, -1), (0, 0, 1), (0, -1, 0), (0, 1, 0), (-1, 0, 0), (1, 0, 0)]
    return [[[c[i] for i in f_], n_, [True] * 4] for f_, n_ in zip(F, N)]
USINADOS = {}
for w in paredes:
    f_ = FV[w['key']]; ad = 0 if f_[0] else 1; al = 1 - ad; sg_ = f_[ad]
    cps = [i for i in w['itens'] if i['tipo'] == 'comp']
    for pn in cps:
        b = pn['bb']
        if b[ad + 3] - b[ad] > 25 or b[al + 3] - b[al] < 400 or b[5] - b[2] < 800: continue
        tras = b[ad + 3] if sg_ > 0 else b[ad]
        atr = [i for i in cps if i is not pn and i['bb'][al] >= b[al] - 5 and i['bb'][al + 3] <= b[al + 3] + 5 and i['bb'][2] >= b[2] - 5
               and i['bb'][5] <= b[5] + 5 and 0 <= ((i['bb'][ad] - tras) if sg_ > 0 else (tras - i['bb'][ad + 3])) <= 150]
        prs = sorted([i for i in atr if i['bb'][5] - i['bb'][2] <= 30 and i['bb'][al + 3] - i['bb'][al] >= 150], key=lambda i: i['bb'][2])
        lts = sorted([i for i in atr if i['bb'][al + 3] - i['bb'][al] <= 30 and i['bb'][5] - i['bb'][2] >= 300], key=lambda i: i['bb'][al])
        if len(prs) < 3 or len(lts) < 2: continue
        o0, o1 = lts[0]['bb'][al + 3], lts[-1]['bb'][al]
        vz = [(p0['bb'][5], p1['bb'][2]) for p0, p1 in zip(prs, prs[1:]) if p1['bb'][2] - p0['bb'][5] > 150]
        if not vz or o1 - o0 < 150: continue
        pi = pn['pecas'][0]; USINADOS[pi] = dict(u=(o0, o1), z=vz, al=al)
        cxs = []
        def sub(a0_, a1_, z0_, z1_):
            bb_ = list(b); bb_[al], bb_[al + 3], bb_[2], bb_[5] = a0_, a1_, z0_, z1_; cxs.append(bb_)
        sub(b[al], o0, b[2], b[5]); sub(o1, b[al + 3], b[2], b[5])
        zz = [b[2]] + [v for z_ in vz for v in z_] + [b[5]]
        for z0_, z1_ in zip(zz[0::2], zz[1::2]):
            if z1_ - z0_ > 0.5: sub(o0, o1, z0_, z1_)
        P[pi]['fq'] = [fq_ for c_ in cxs for fq_ in _caixa_fq(c_)]
        print('PAINEL USINADO:', pn['desc'], pn['dim'], '->', len(vz), 'vão(s)')
grupos = geo.agrupar_vistas2([w for w in paredes if not w.get('divisoria')])
_DIVW = [w['id'] for w in paredes if w.get('divisoria')]
nao_achados = [(d, dm) for n, (d, dm) in enumerate(linhas, 1) if not any(i['n'] == n for i in inst)]

# vistas: liga cada grupo à imagem 3D do config pela peça de referência
V = []
livres = list(grupos)
for cv in cfg['vistas']:
    g = next((g for g in livres if any(cv['ref'] in f"{i['desc']} {i['dim']}" for w in g for i in PW[w]['itens'])), None)
    if g: livres.remove(g); V.append(dict(cv, paredes=sorted(g, key=lambda w: -len(PW[w]['itens']))))
letras = 'ABCDEFGHIJKL'
# REGRA (João): cada parede tem sua LETRA (A, B, C, D... em sequência; em cada L a parede maior primeiro).
# Parede PEQUENA (< PAREDE_PEQ ao longo da parede) vai junto com a parede grande do mesmo L:
#   listagem única com 3D angulado pegando as duas + cotas das duas lado a lado na mesma prancha.
# Paredes grandes = vista própria (3D frontal).
PAREDE_PEQ = 2500  # João: parede < 2,5 m vai junto com a vizinha do L (listagem na diagonal)
def _larg(w):
    ax = 1 if FV[PW[w]['key']][0] else 0
    return max(i['bb'][ax + 3] for i in PW[w]['itens']) - min(i['bb'][ax] for i in PW[w]['itens'])
_nl = len(V)
for g in livres:
    ws = sorted(g, key=lambda w: -_larg(w)); blocos = []
    for w in ws:
        if blocos and _larg(w) < PAREDE_PEQ and len(blocos[0]) < 2: blocos[0].append(w)
        else: blocos.append([w])
    for b in blocos:
        ls = [letras[_nl + k] for k in range(len(b))]; _nl += len(b)
        V.append(dict(letra=ls[0], letras=ls, img3d=None, paredes=b))
for wid in _DIVW:   # REGRA (v18): divisória ripada = bloco próprio no fim
    V.append(dict(letra=letras[_nl], letras=[letras[_nl]], img3d=None, paredes=[wid], divisoria=True)); _nl += 1
# REGRA (v22, planta do João): a vista da PERNA DO L vem logo DEPOIS da vista da parede dela (b -> c); letras em sequência
for v in [v for v in V if len(v['paredes']) == 1 and PW[v['paredes'][0]].get('perna_l')]:
    pai_ = PW[v['paredes'][0]]['pai']; V.remove(v)
    k_ = next((j for j, o in enumerate(V) if pai_ in o['paredes']), len(V) - 1)
    V.insert(k_ + 1, v)
_c = 0
for v in V:
    if v.get('img3d') is None and not v.get('ref'):
        v['letras'] = [letras[_c + k] for k in range(len(v['paredes']))]; v['letra'] = v['letras'][0]
    _c += len(v['paredes'])
for v in V:
    v.setdefault('letras', [v['letra'] + (str(j + 1) if len(v['paredes']) > 1 else '') for j in range(len(v['paredes']))])
    v['titulo'] = 'VISTA ' + v['letras'][0] if len(v['letras']) == 1 else 'VISTAS ' + ' E '.join(v['letras'])
    if v.get('divisoria'): v['titulo'] = PW[v['paredes'][0]].get('bloco') or 'DIVISÓRIA RIPADA'
    # REGRA (João): LISTAGEM sempre FRONTAL e POR PAREDE (só os móveis daquela parede); o bloco junta só as cotas.
    v['subs'] = [v] if len(v['paredes']) == 1 else [dict(letra=l_, letras=[l_], titulo='VISTA ' + l_, img3d=None, paredes=[w_]) for w_, l_ in zip(v['paredes'], v['letras'])]
VW = [s_ for v in V for s_ in v['subs']]

# listagem de cada vista: módulos primeiro, depois componentes; mesmo item = mesma linha
for v in VW:
    its = [i for w in v['paredes'] for i in PW[w]['itens']]
    ordem = sorted(its, key=lambda i: (i['tipo'] != 'mod', i['n']))
    chaves = []
    for i in ordem:
        k = (i['desc'], i['dim'])
        if k not in chaves: chaves.append(k)
    v['linhas'] = [(d, dm, '') for d, dm in chaves]
    for i in its: i['num_' + v['letra']] = chaves.index((i['desc'], i['dim'])) + 1
if nao_achados:
    VW[0]['linhas'] += [(d, dm, '*') for d, dm in nao_achados]

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
    sh.draw_line((X(G.get('vmin', G['umin'])) - 6, fy), (X(G.get('vmax', G['umax'])) + 6, fy)); sh.finish(color=PRETO, width=0.9)
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

# nível do piso pronto: placa de piso do DXF (grande, fina, no chão). Cotas de altura partem daqui.
ZP = max([p_['bb'][5] for p_ in P if min(p_['dim'][0], p_['dim'][1]) > 1500 and p_['dim'][2] <= 60 and p_['bb'][2] <= 1] or [0])
CORTE = 1100
def _eh_ripa(it):
    try: d_ = sorted(float(x) for x in re.findall(r'[\d.]+', it['dim'].replace(',', '.'))[:3])
    except Exception: return False
    return len(d_) == 3 and d_[0] <= 30 and 60 <= d_[1] <= 200 and d_[2] >= 500

def cotar_divisoria(page, G, ox, fy, k):
    # REGRA (v18, PDF do João): divisória ripada NÃO cota ripa por ripa. Cota: largura total + peças laterais,
    # UMA ripa e UM vão (amostra), altura total e as alturas das partes (bases, painel, travessas).
    X = lambda u: ox + (u - G['umin']) * k
    Y = lambda z: fy - z * k
    bx = G['boxes']; u0, u1 = G['umin'], G['umax']; ztop_ = max(b['z1'] for b in bx)
    rip = sorted([b for b in bx if _eh_ripa(b['it'])], key=lambda b: b['u0'])
    alt = [b for b in bx if not _eh_ripa(b['it']) and (b['z1'] - b['z0']) >= 0.8 * ztop_]
    cadeia_h(page, [u0, u1] + [v for b in alt for v in (b['u0'], b['u1'])], fy + 14, fy + 2, X)
    cadeia_h(page, [u0, u1], Y(ztop_) - 14, Y(ztop_) - 2, X)
    # REGRA (v18b, João): o montador precisa da distância entre as ripas -> cota TODOS os vãos, em cada faixa de ripas
    # (embaixo e em cima do painel), com as setas por dentro; a espessura da ripa sai uma vez só.
    faixas = sorted({(round(b['z0'] / 50), round(b['z1'] / 50)) for b in rip if b['z1'] - b['z0'] >= 300})
    feitas = []
    for f0, f1 in faixas:
        zc = (f0 + f1) * 25
        if any(abs(zc - z_) < 250 for z_ in feitas): continue
        estreitas = [b for b in bx if b['z0'] <= zc <= b['z1'] and (b['u1'] - b['u0']) <= 200]
        ed = _uniq(sorted(v for b in estreitas for v in (b['u0'], b['u1'])), 1.0)
        if len(ed) < 4: continue
        feitas.append(zc); yl = Y(zc)
        sh = page.new_shape(); sh.draw_line((X(ed[0]), yl), (X(ed[-1]), yl)); sh.finish(color=CR, width=0.4)
        for u_ in ed: _tick(sh, X(u_), yl)
        sh.finish(color=CR, width=0.5); sh.commit()
        ripa_ok = False
        for a_, c_ in zip(ed, ed[1:]):
            t_ = fmt(c_ - a_); tw = fz.get_text_length(t_, 'helv', 5)
            if (c_ - a_) >= 40 and (c_ - a_) * k >= tw + 1:
                _txt(page, ((X(a_) + X(c_)) / 2 - tw / 2, yl - 1.5), t_, 5, fundo=True)
            elif not ripa_ok and (c_ - a_) < 40:
                _txt(page, (X(c_) + 1, yl + 6), t_, 5, fundo=True); ripa_ok = True
    hor = [b for b in bx if not _eh_ripa(b['it']) and (b['u1'] - b['u0']) >= 0.4 * (u1 - u0)]
    zs = [ZP, ztop_] + [v for b in hor for v in (b['z0'], b['z1'])]
    cadeia_v(page, zs, X(u1) + 16, X(u1) + 2, Y)
    cadeia_v(page, [ZP, ztop_], X(u0) - 16, X(u0) - 2, Y)

def _u_de(G, c, al):   # coordenada do DXF (eixo al) -> coordenada u da elevação
    f = G['f']; return c * (f[1] if al == 0 else -f[0])

def cotar_bloco(page, G, ox, fy, k):
    # REGRA (v26): BLOCO DE PAINÉIS (painel com nichos). Cota: largura total, VÃOS USINADOS do painel (largura e altura
    # de cada vão e das faixas entre eles), altura do painel a partir do piso pronto e até o teto (painel do teto).
    X = lambda u: ox + (u - G['umin']) * k
    Y = lambda z: fy - z * k
    bx = G['boxes']; f = G['f']; ad = 0 if f[0] else 1
    fin = [b for b in bx if b['it']['bb'][ad + 3] - b['it']['bb'][ad] <= 30]
    pn = max(fin or bx, key=lambda b: (b['u1'] - b['u0']) * (b['z1'] - b['z0']))
    zt = max(b['z1'] for b in bx); u0, u1 = G['umin'], G['umax']
    us_, zs_ = [pn['u0'], pn['u1']], [pn['z0'], pn['z1']]
    ui = USINADOS.get(pn['it']['pecas'][0])
    if ui:
        us_ += [_u_de(G, c, ui['al']) for c in ui['u']]; zs_ += [v for z_ in ui['z'] for v in z_]
    cadeia_h(page, us_, Y(pn['z0']) + 14, Y(pn['z0']) + 2, X, fundo=True)
    cadeia_h(page, [u0, u1], Y(zt) - 14, Y(zt) - 2, X)
    xr = X(max(pn['u1'], u1))
    cadeia_v(page, zs_, xr + 14, X(pn['u1']) + 2, Y)
    cadeia_v(page, [ZP, pn['z0'], pn['z1'], zt], xr + 30, xr + 2, Y)

def cotar(page, G, ox, fy, k):
    if G['w'].get('bloco'): return cotar_bloco(page, G, ox, fy, k)
    if G['w'].get('divisoria'): return cotar_divisoria(page, G, ox, fy, k)
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
    vr, vl = X(G.get('vmax', G['umax'])), X(G.get('vmin', G['umin']))   # REGRA (v15): cotas por FORA das paredes
    dir_ = [b for b in mb if b['u1'] >= G['umax'] - 700]
    esq = [b for b in mb if b['u0'] <= G['umin'] + 700]
    # móvel longe da parede lateral (> 600 mm): a cadeia fica encostada no móvel, não atravessa a parede vazia
    if vr - xr > 600 * k: vr = xr
    if xl - vl > 600 * k: vl = xl
    cadeia_v(page, [ZP] + [v for b in dir_ for v in (b['z0'], b['z1'])], vr + 14, xr + 2, Y)
    cadeia_v(page, [ZP] + [v for b in esq for v in (b['z0'], b['z1'])], vl - 14, xl - 2, Y)
    cadeia_v(page, [ZP, max(b['z1'] for b in mb)], vl - 28, xl - 2, Y)
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

# REGRA (v16, João): VISTA LATERAL do móvel na MESMA prancha da cota frontal (página dividida: frontal à esquerda,
# lateral à direita, mesma escala). Mostra a PROFUNDIDADE (a partir da parede) e as alturas; parede do fundo em cinza.
def _desenho2d(page, faces, XY):
    """REGRA (v16, João): cotas 2D (frontal e lateral) com as MESMAS cores e TEXTURAS do 3D (madeirado com veio).
    Chapa 1830 x 2750 mm, veio no sentido do comprimento da peça. Sem Pillow/textura = cor lisa (vetor)."""
    its = []
    for f_ in faces:
        pts, cor, ft = f_[1], f_[2], f_[3]
        q = [XY(a, b) for a, b in pts]
        if area2(q) < 0.15: continue
        its.append((q, cor, ft, f_[4] if len(f_) > 4 else None, f_[5] if len(f_) > 5 else 0, pts))
    if not its: return
    if _Im is None or not cfg.get('textura', True) or not any(textura(m_) for _, _, _, m_, _, _ in its if m_):
        sh = page.new_shape()
        for q, cor, ft, _, _, _ in its:
            sh.draw_polyline(q + [q[0]]); sh.finish(color=cor, fill=cor, width=0.45, closePath=True)
            if any(ft):
                for (a_, b_), f_ in zip(zip(q, q[1:] + q[:1]), ft):
                    if f_: sh.draw_line(a_, b_)
                sh.finish(color=(0.2, 0.2, 0.2), width=0.3, closePath=False)
        sh.commit(); return
    R = fz.Rect(min(x for q in [i[0] for i in its] for x, _ in q), min(y for q in [i[0] for i in its] for _, y in q),
                max(x for q in [i[0] for i in its] for x, _ in q), max(y for q in [i[0] for i in its] for _, y in q)) & page.rect
    if R.is_empty: return
    s_ = 250 / 72.0; W_ = max(1, int(R.width * s_)); H_ = max(1, int(R.height * s_))
    img = _Im.new('RGBA', (W_, H_), (0, 0, 0, 0)); dr = _ImD.Draw(img)
    for q, cor, ft, mat, pc, pts in its:
        Q = [((x - R.x0) * s_, (y - R.y0) * s_) for x, y in q]
        tex = textura(mat) if mat else None
        x0_ = int(max(0, min(a for a, _ in Q))); y0_ = int(max(0, min(b for _, b in Q)))
        x1_ = int(min(W_, max(a for a, _ in Q) + 1)); y1_ = int(min(H_, max(b for _, b in Q) + 1))
        if tex is not None and x1_ - x0_ >= 3 and y1_ - y0_ >= 3:
            Lu = max(a for a, _ in pts) - min(a for a, _ in pts); Lz = max(b for _, b in pts) - min(b for _, b in pts)
            sx_, sy_ = tex.width / CHAPA_L, tex.height / CHAPA_A
            deit = Lu > Lz                                   # peça deitada: veio na horizontal
            Lw, Lh = (Lz, Lu) if deit else (Lu, Lz)
            pw = max(2, min(tex.width, int(Lw * sx_))); ph = max(2, min(tex.height, int(Lh * sy_)))
            ox_ = (pc * 137) % max(1, tex.width - pw + 1); oy_ = (pc * 71) % max(1, tex.height - ph + 1)
            tile = tex.crop((ox_, oy_, ox_ + pw, oy_ + ph))
            if deit: tile = tile.rotate(90, expand=True)
            tile = tile.resize((x1_ - x0_, y1_ - y0_)).convert('RGBA')
            mask = _Im.new('L', tile.size, 0); _ImD.Draw(mask).polygon([(a - x0_, b - y0_) for a, b in Q], fill=255)
            img.paste(tile, (x0_, y0_), mask)
        else:
            dr.polygon(Q, fill=tuple(int(255 * v) for v in cor) + (255,))
        for (a_, b_), fl_ in zip(zip(Q, Q[1:] + Q[:1]), ft):
            if fl_: dr.line([a_, b_], fill=(50, 50, 50, 255), width=max(1, int(0.3 * s_)))
    import io as _io
    bio = _io.BytesIO(); img.save(bio, format='PNG', optimize=True)
    page.insert_image(R, stream=bio.getvalue())

def geom_lateral(w):
    f = FV[w['key']]; axd = 0 if f[0] else 1; sg = f[axd]; pl = w['plano']
    H = lambda v: (pl - v[axd]) * sg          # profundidade: 0 na parede, cresce para dentro do ambiente
    faces = []; boxes = []
    for it in w['itens']:
        cor = MADEIRA if it['tipo'] == 'comp' else BRANCO
        for pi in it['pecas']:
            sd_ = sorted(P[pi]['dim'])
            if sd_[1] < 50 or sd_[0] > 60: continue
            for uq, nv, ft in P[pi]['fq']:
                faces.append((sum(uu(v[0], v[1], f) for v in uq) / len(uq), [(H(v), v[2]) for v in uq], P[pi].get('rgb', cor), ft, P[pi].get('mat'), pi))
        b = it['bb']; h0, h1 = sorted((H((b[0], b[1])), H((b[3], b[4]))))
        boxes.append(dict(it=it, h0=max(h0, 0), h1=h1, z0=b[2], z1=b[5]))
    faces.sort(key=lambda t: t[0])            # vista pelo lado de u maior: o mais perto por último
    hmax = max(b['h1'] for b in boxes); zmax = max(b['z1'] for b in boxes)
    return dict(faces=faces, boxes=boxes, hmax=hmax, zmax=zmax, esp=150, divisoria=bool(w.get('divisoria')), bloco=w.get('bloco'))

def desenhar_lateral(page, L, ox, fy, k, ztop):
    X = lambda h: ox + h * k
    Y = lambda z: fy - z * k
    sh = page.new_shape()
    sh.draw_rect(fz.Rect(X(-L['esp']), Y(ztop), X(0), fy)); sh.finish(color=(0.2, 0.2, 0.2), fill=(0.9, 0.9, 0.9), width=0.4)
    sh.commit()
    _desenho2d(page, L['faces'], lambda h, z: (X(h), Y(z)))
    sh = page.new_shape()
    sh.draw_line((X(-L['esp']) - 6, fy), (X(L['hmax'] + 300), fy)); sh.finish(color=PRETO, width=0.9)
    sh.commit()

def cotar_lateral(page, L, ox, fy, k):
    X = lambda h: ox + h * k
    Y = lambda z: fy - z * k
    if L.get('bloco'):   # REGRA (v26): bloco de painéis de lado: profundidade do painel e do painel do teto + alturas
        bx = L['boxes']; ver = [b for b in bx if b['z1'] - b['z0'] >= 800]; dei = [b for b in bx if b['h1'] - b['h0'] >= 500]
        hv = max([b['h1'] for b in ver] or [0]); zt = L['zmax']
        cadeia_h(page, [0, hv, L['hmax']], Y(zt) - 13, Y(zt) - 2, X)
        if hv > 1: cadeia_h(page, [0, L['hmax']], Y(zt) - 26, Y(zt) - 2, X)
        zs = [ZP, zt] + [min(b['z0'] for b in ver)] * bool(ver) + [v for b in dei for v in (b['z0'], b['z1'])]
        xr = X(L['hmax']); cadeia_v(page, zs, xr + 14, xr + 2, Y); return
    if L.get('divisoria'):   # divisória: só profundidade total e altura total
        cadeia_h(page, [0, L['hmax']], fy + 13, fy + 2, X)
        xr = X(L['hmax']); cadeia_v(page, [ZP, L['zmax']], xr + 14, xr + 2, Y); return
    mb = [b for b in L['boxes'] if b['it']['tipo'] == 'mod'] or L['boxes']
    inf = [b for b in mb if b['z0'] < CORTE]; sup = [b for b in mb if b['z1'] > CORTE]
    if inf: cadeia_h(page, [0] + [v for b in inf for v in (b['h0'], b['h1'])], fy + 13, fy + 2, X)
    if sup:
        yt = Y(max(b['z1'] for b in sup))
        cadeia_h(page, [0] + [v for b in sup for v in (b['h0'], b['h1'])], yt - 13, yt - 2, X)
    xr = X(max(b['h1'] for b in mb))
    cadeia_v(page, [ZP] + [v for b in mb for v in (b['z0'], b['z1'])], xr + 14, xr + 2, Y)

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

def escala_para(larg_mm, alt_mm, W, H, cheio=False):
    for S in (ESC_COTA if cheio else ESC):
        k = MM / S
        lim = 1.0 if cheio else 0.75 if S < 25 else 1.0   # cotas (v15): ocupa a prancha toda
        if larg_mm * k <= W * lim and alt_mm * k <= H * lim: return S, k
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
    if ctx:   # REGRA (v15): piso de referência (cinza claro) para a imagem não ficar "flutuando" no branco
        _pz = [0.0] * 6; _pz[axl] = U[axl] - 4000; _pz[axl + 3] = U[axl + 3] + 4000; _pz[2] = -20; _pz[5] = 0
        _pl = w0['plano']; _pz[axd], _pz[axd + 3] = (_pl - 6000, _pl) if sg > 0 else (_pl, _pl + 6000)
        src.append((caixa_faces(_pz)[1], (0.86, 0.86, 0.86), [False] * 4, 0, -1))
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
    _desenho2d(page, G['faces'], lambda u, z: (X(u), Y(z)))
    sh = page.new_shape()
    sh.draw_line((X(G.get('vmin', G['umin'])) - 6, fy), (X(G.get('vmax', G['umax'])) + 6, fy)); sh.finish(color=PRETO, width=0.9)
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
    if ctx:   # REGRA (v15): piso de referência (cinza claro) para a imagem não ficar "flutuando" no branco
        _pz = [0.0] * 6; _pz[axl] = U[axl] - 4000; _pz[axl + 3] = U[axl + 3] + 4000; _pz[2] = -20; _pz[5] = 0
        _pl = w0['plano']; _pz[axd], _pz[axd + 3] = (_pl - 6000, _pl) if sg > 0 else (_pl, _pl + 6000)
        src.append((caixa_faces(_pz)[1], (0.86, 0.86, 0.86), [False] * 4, 0, -1))
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
PAREDES_PECAS = [p_ for p_ in P if p_['dim'][2] >= 2000 and 80 <= min(p_['dim'][0], p_['dim'][1]) <= 400 and max(p_['dim'][0], p_['dim'][1]) >= 1000]
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

def _vista_limites(w, f, umin_, umax_, zmax_):
    """REGRA (v15): limites da elevação 2D = parede a parede (face interna da parede lateral + espessura) e piso ao teto.
    Sem parede lateral a até 4 m: abre 300 mm além do móvel. Teto = maior altura das paredes reais (até 3,2 m)."""
    axd = 0 if f[0] else 1; sg = f[axd]; pl = w['plano']
    cx = []
    for p_ in PAREDES_PECAS + PAR_DXF: cx.append(p_['bb'])
    for p_ in MALHA_PAR:
        for fc in p_['faces']:
            cx.append([min(v[0] for v in fc), min(v[1] for v in fc), min(v[2] for v in fc), max(v[0] for v in fc), max(v[1] for v in fc), max(v[2] for v in fc)])
    esq, dir_, esp_e, esp_d, tetos = None, None, 150, 150, []
    for b in cx:
        if b[5] - b[2] < 1500: continue
        d0, d1 = sorted(((pl - b[axd]) * sg, (pl - b[axd + 3]) * sg))
        if d1 < -30 or d0 > 800: continue      # só paredes na faixa dos móveis (fundo até 800 mm à frente)
        u0, z0, u1, z1 = geo.caixa_elev(b, f)
        if u1 > umin_ + 20 and u0 < umax_ - 20: tetos.append(z1); continue
        if u0 >= umax_ - 20 and u0 - umax_ <= 4000 and (dir_ is None or u0 < dir_): dir_ = u0; esp_d = min(max(u1 - u0, 60), 250) if u1 - u0 > 1 else 150
        if u1 <= umin_ + 20 and umin_ - u1 <= 4000 and (esq is None or u1 > esq): esq = u1; esp_e = min(max(u1 - u0, 60), 250) if u1 - u0 > 1 else 150
        tetos.append(z1)
    vmin_ = esq - esp_e if esq is not None else umin_ - 300
    vmax_ = dir_ + esp_d if dir_ is not None else umax_ + 300
    ztop_ = min(max(tetos), 3200) if tetos else zmax_ + 150
    return vmin_, vmax_, max(ztop_, zmax_ + 50)

def geom_parede(w):
    f = FV[w['key']]; faces = []; boxes = []
    dep = lambda vs: sum(v[0] * f[0] + v[1] * f[1] for v in vs) / len(vs)
    for it in w['itens']:
        cor = MADEIRA if it['tipo'] == 'comp' else BRANCO
        for pi in it['pecas']:
            sd_ = sorted(P[pi]['dim'])
            if sd_[1] < 50 or sd_[0] > 60: continue  # REGRA: só MDF (sem dobradiças/suportes/cabideiros)
            for uq, nv, ft in P[pi]['fq']:
                faces.append((dep(uq), [(uu(v[0], v[1], f), v[2]) for v in uq], P[pi].get('rgb', cor), ft, P[pi].get('mat'), pi))
        u0, z0, u1, z1 = geo.caixa_elev(it['bb'], f)
        boxes.append(dict(it=it, u0=u0, z0=z0, u1=u1, z1=z1))
    Ub = list(w['itens'][0]['bb'])
    for it in w['itens']: Ub = geo.uniao(Ub, it['bb'])
    R = [Ub[0] - 1700, Ub[1] - 1700, 0, Ub[3] + 1700, Ub[4] + 1700, 3200]
    if f[0] > 0: R[3] += 300
    if f[0] < 0: R[0] -= 300
    if f[1] > 0: R[4] += 300
    if f[1] < 0: R[1] -= 300
    _pr = []
    _axd = 0 if f[0] else 1
    for b in paredes_recorte(R):
        # REGRA (v15): parede toda NA FRENTE do fundo dos móveis não entra (esconderia o móvel na elevação)
        if min((w['plano'] - b[_axd]) * f[_axd], (w['plano'] - b[_axd + 3]) * f[_axd]) > 100: continue
        for fc in caixa_faces(b):
            _pr.append((dep(fc), [(uu(v[0], v[1], f), v[2]) for v in fc], (0.9, 0.9, 0.9), [True] * 4))
    umin_ = min(b['u0'] for b in boxes); umax_ = max(b['u1'] for b in boxes); zmax_ = max(b['z1'] for b in boxes)
    vmin_, vmax_, ztop_ = _vista_limites(w, f, umin_, umax_, zmax_)
    if w.get('bloco'):   # REGRA (v26): bloco de painéis (móvel sozinho, estreito) = elevação curta em volta dele -> escala maior
        vmin_ = max(vmin_, umin_ - 600); vmax_ = min(vmax_, umax_ + 600)
    Cc = (sum((x['it']['bb'][0] + x['it']['bb'][3]) / 2 for x in boxes) / len(boxes), sum((x['it']['bb'][1] + x['it']['bb'][4]) / 2 for x in boxes) / len(boxes))
    wf = []
    # REGRA (v15, João): a cota NÃO elimina as paredes. A vista abre até as paredes laterais (com a espessura delas)
    # e vai do piso até o teto (pé-direito). Tudo recortado nos limites da vista, nunca rente ao móvel.
    clq = lambda q: [(min(max(u_, vmin_), vmax_), min(max(z_, 0), ztop_)) for u_, z_ in q]
    for d_, q_, c_, fl_ in _pr:
        q2 = clq(q_); faces.append((d_, q2, c_, [a_ and b0 == b1 for a_, b0, b1 in zip(fl_, q2, q_)]))
    for p_ in P:   # REGRA: parede atrás dos móveis na elevação 2D (só referência, não é cotada)
        b = p_['bb']
        if p_['i'] in MALHA_I:   # paredes em peça única: só as faces do fundo (até 300 mm atrás do plano da parede)
            for fc, fl in zip(p_['faces'], p_['ft']):
                if max(abs(((w['plano'] - v[0] if f[0] else w['plano'] - v[1]) * (f[0] or f[1]))) for v in fc) > 300: continue
                q_ = [(uu(v[0], v[1], f), v[2]) for v in fc]
                q2 = clq(q_)
                wf.append((1e9, q2, (0.9, 0.9, 0.9), [f0 and a0 == b0 for f0, a0, b0 in zip(fl, q2, q_)]))
            continue
        if not (80 <= min(p_['dim'][0], p_['dim'][1]) <= 400 and p_['dim'][2] >= 100 and max(p_['dim'][0], p_['dim'][1]) >= 300 and p_['i'] not in _usadas): continue
        if ((b[0] + b[3]) / 2 - Cc[0]) * f[0] + ((b[1] + b[4]) / 2 - Cc[1]) * f[1] < -150: continue
        u0_, z0_, u1_, z1_ = geo.caixa_elev(b, f)
        if u1_ < vmin_ or u0_ > vmax_: continue
        u0_ = max(u0_, vmin_); u1_ = min(u1_, vmax_); z1_ = min(z1_, ztop_)
        if u1_ - u0_ < 5: continue
        wf.append((1e9, [(u0_, 0), (u1_, 0), (u1_, z1_), (u0_, z1_)], (0.9, 0.9, 0.9), [True] * 4))
    # AMBIENTE no 2D (só referência, NUNCA cotado): pedra e móveis das paredes vizinhas perto desta parede.
    axd = 0 if f[0] else 1; sg = f[axd]
    prof_ = lambda bb: min((w['plano'] - bb[axd]) * sg, (w['plano'] - bb[axd + 3]) * sg)
    cl = lambda u: min(max(u, vmin_), vmax_)
    for p_ in AMB + ELETROS:   # pedra/eletros só aparecem na parede onde estão
        b = p_['bb']; u0_, z0_, u1_, z1_ = geo.caixa_elev(b, f)
        if prof_(b) > 1000 or u1_ < umin_ - 50 or u0_ > umax_ + 50: continue
        c0_ = PEDRA_COR if p_['i'] in AMB_I else ELETRO_COR
        for fc, fl in zip(p_['faces'], p_['ft']):
            faces.append((dep(fc), [(cl(uu(v[0], v[1], f)), v[2]) for v in fc], c0_, fl))
    _mi = {pi for it in w['itens'] for pi in it['pecas']}
    for it in inst:   # móveis vizinhos: cinza claro, cortados na borda
        for pi in it['pecas']:
            if pi in _mi: continue
            p_ = P[pi]; b = p_['bb']; sd_ = sorted(p_['dim'])
            if sd_[1] < 50 or sd_[0] > 60 or prof_(b) > 1000: continue
            u0_, z0_, u1_, z1_ = geo.caixa_elev(b, f)
            if u1_ <= vmin_ or u0_ >= vmax_: continue
            for uq, nv, ft in p_['fq']:
                faces.append((dep(uq), [(cl(uu(v[0], v[1], f)), v[2]) for v in uq], (0.86, 0.86, 0.86), ft))
    faces.sort(key=lambda t: -t[0]); faces = wf + faces
    return dict(w=w, f=f, faces=faces, boxes=boxes, umin=umin_, umax=umax_, zmax=zmax_, vmin=vmin_, vmax=vmax_, ztop=ztop_)

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

# REGRA (João): a imagem da textura = UMA CHAPA de MDF de 1830 mm (largura) x 2750 mm (altura, sentido do veio).
# Cada peça usa o pedaço da chapa proporcional ao seu tamanho (peça maior que a chapa repete a chapa).
CHAPA_L, CHAPA_A = 1830.0, 2750.0
def _persp(dst, src_):
    # coeficientes PIL PERSPECTIVE: saída (dst) -> entrada (src_)
    A = []; B = []
    for (x, y), (u, v) in zip(dst, src_):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return _np.linalg.solve(_np.array(A, float), _np.array(B, float)).tolist()

def _raster3d(page, rect, fcs, T, pmat, dpi=170):
    s_ = dpi / 72.0; W_ = max(1, int(rect.width * s_)); H_ = max(1, int(rect.height * s_))
    img = _Im.new('RGB', (W_, H_), (255, 255, 255)); dr = _ImD.Draw(img)
    px = lambda x, y: ((T(x, y)[0] - rect.x0) * s_, (T(x, y)[1] - rect.y0) * s_)
    for f_ in fcs:
        q, c_, ft, pc, vs, fs_ = f_[2], f_[3], f_[4], f_[5], f_[6], f_[7]
        Q = [px(x, y) for x, y in q]
        if area2(Q) < 0.5: continue
        tex = textura(pmat.get(pc)) if pc is not None and pc >= 0 and len(vs) == 4 else None
        x0_ = int(max(0, min(a for a, _ in Q))); y0_ = int(max(0, min(b for _, b in Q)))
        x1_ = int(min(W_, max(a for a, _ in Q) + 1)); y1_ = int(min(H_, max(b for _, b in Q) + 1))
        if tex is not None and x1_ - x0_ >= 3 and y1_ - y0_ >= 3:
            L1 = math.dist(vs[0], vs[1]); L2 = math.dist(vs[0], vs[3])
            sx_, sy_ = tex.width / CHAPA_L, tex.height / CHAPA_A   # px por mm da chapa
            # veio (altura da chapa) acompanha o lado mais comprido da peça
            if L1 >= L2: corners = [vs[0], vs[3], vs[2], vs[1]]; Lw, Lh = L2, L1
            else: corners = [vs[0], vs[1], vs[2], vs[3]]; Lw, Lh = L1, L2
            pw = max(2, int(Lw * sx_)); ph = max(2, int(Lh * sy_))
            if pw <= tex.width and ph <= tex.height:
                ox_ = (pc * 137) % max(1, tex.width - pw + 1); oy_ = (pc * 71) % max(1, tex.height - ph + 1)   # pedaço da chapa varia por peça
                tile = tex.crop((ox_, oy_, ox_ + pw, oy_ + ph))
            else:
                tile = _Im.new('RGB', (pw, ph))
                for ty in range(0, ph, tex.height):
                    for tx in range(0, pw, tex.width): tile.paste(tex, (tx, ty))
            if max(pw, ph) > 1400: tile = tile.resize((max(2, pw * 1400 // max(pw, ph)), max(2, ph * 1400 // max(pw, ph)))); pw, ph = tile.size
            if fs_ < 0.999: tile = tile.point(lambda v: int(v * fs_))
            iq = [q[vs.index(c3_)] for c3_ in corners]
            dst = [(px(*p2)[0] - x0_, px(*p2)[1] - y0_) for p2 in iq]
            try:
                co = _persp(dst, [(0, 0), (pw, 0), (pw, ph), (0, ph)])
                patch = tile.transform((x1_ - x0_, y1_ - y0_), _Im.PERSPECTIVE, co, _Im.BILINEAR)
                mask = _Im.new('L', patch.size, 0); _ImD.Draw(mask).polygon([(a - x0_, b - y0_) for a, b in Q], fill=255)
                img.paste(patch, (x0_, y0_), mask)
            except Exception:
                dr.polygon(Q, fill=tuple(int(255 * v) for v in c_))
        else:
            dr.polygon(Q, fill=tuple(int(255 * v) for v in c_))
        for (a_, b_), fl_ in zip(zip(Q, Q[1:] + Q[:1]), ft):
            if fl_: dr.line([a_, b_], fill=(50, 50, 50), width=max(1, int(0.35 * s_)))
    import io as _io
    bio = _io.BytesIO(); img.save(bio, format='JPEG', quality=88)
    page.insert_image(rect, stream=bio.getvalue())

def costas(w):
    # itens (painéis) cuja face voltada para a câmera fica atrás do fundo de um módulo da mesma parede -> escondidos
    f_ = FV[w['key']]; ad = 0 if f_[0] else 1; al = 1 - ad; sg_ = f_[ad]
    perto = lambda bb: min(bb[ad] * sg_, bb[ad + 3] * sg_); longe = lambda bb: max(bb[ad] * sg_, bb[ad + 3] * sg_)
    mods = [i for i in w['itens'] if i['tipo'] == 'mod']; out = []
    for i in w['itens']:
        if i['tipo'] != 'comp': continue
        b = i['bb']
        tapa = [m for m in mods if perto(b) >= longe(m['bb']) - 5 and min(b[al + 3], m['bb'][al + 3]) - max(b[al], m['bb'][al]) > 0.5 * (b[al + 3] - b[al])
                and min(b[5], m['bb'][5]) - max(b[2], m['bb'][2]) > 0.5 * (b[5] - b[2])]
        if tapa: out.append(i)
    return out

# ===== CONDIÇÃO (v21, João): LISTAGEM POLUÍDA =====
# Parede com MUITOS balões (>= 12 peças numeradas) -> a imagem grande fica só com os painéis/móveis principais e:
#  - MÓDULO PEQUENO FECHADO (gaveta/mesa de cabeceira suspensa: até 1 m x 0,7 m, com porta/gaveta) + tampo em cima
#    vai para um DETALHE embaixo da tabela (um por tipo; repetidos iguais = um detalhe só), balões só lá;
#  - peça ESCONDIDA ATRÁS DE PAINEL (afastadores atrás da cabeceira) vai para o DETALHE DAS COSTAS.
def poluida(w):
    return not w.get('divisoria') and len(w['itens']) >= 12

def pequenos(w):
    if not poluida(w): return []
    f_ = FV[w['key']]; al = 1 if f_[0] else 0; out = []; tipos = {}
    for m in w['itens']:
        mb = m['bb']
        if m['tipo'] != 'mod' or mb[al + 3] - mb[al] > 1000 or mb[5] - mb[2] > 700 or not tem_porta(m, w): continue
        g = [m] + [o for o in w['itens'] if o['tipo'] == 'comp' and abs(o['bb'][2] - mb[5]) <= 25
                   and o['bb'][al] >= mb[al] - 40 and o['bb'][al + 3] <= mb[al + 3] + 40 and (o['bb'][5] - o['bb'][2]) <= 40]
        # só módulo SOLTO (nenhum outro módulo encostado a até 100 mm): mesa de cabeceira, gaveteiro suspenso; armários de
        # cozinha lado a lado NÃO entram
        if any(o is not m and o['tipo'] == 'mod' and geo.dist_caixas(o['bb'], mb) <= 100 for o in w['itens']): continue
        chave = (m['desc'], m['dim'])
        if chave in tipos: tipos[chave]['todos'] += g; continue
        tipos[chave] = dict(mostra=g, todos=list(g)); out.append(tipos[chave])
    return out

def costas_paineis(w):
    if not poluida(w): return []
    f_ = FV[w['key']]; ad = 0 if f_[0] else 1; al = 1 - ad; sg_ = f_[ad]
    perto = lambda bb: min(bb[ad] * sg_, bb[ad + 3] * sg_); longe = lambda bb: max(bb[ad] * sg_, bb[ad + 3] * sg_)
    grandes = [i for i in w['itens'] if i['tipo'] == 'comp' and (i['bb'][ad + 3] - i['bb'][ad]) <= 30
               and (i['bb'][al + 3] - i['bb'][al]) * (i['bb'][5] - i['bb'][2]) >= 5e5]
    out = []
    for i in w['itens']:
        if i['tipo'] != 'comp' or i in grandes: continue
        b = i['bb']
        if any(perto(b) >= longe(g['bb']) - 5 and b[al] >= g['bb'][al] - 30 and b[al + 3] <= g['bb'][al + 3] + 30 for g in grandes): out.append(i)
    # cobertos pela UNIÃO dos painéis (afastador atrás da emenda de dois painéis)
    if grandes:
        g0 = min(g['bb'][al] for g in grandes); g1 = max(g['bb'][al + 3] for g in grandes)
        z0 = min(g['bb'][2] for g in grandes); z1 = max(g['bb'][5] for g in grandes); fundo = max(longe(g['bb']) for g in grandes)
        for i in w['itens']:
            b = i['bb']
            if i['tipo'] == 'comp' and i not in grandes and i not in out and perto(b) >= fundo - 5 and b[al] >= g0 - 30 and b[al + 3] <= g1 + 30 and b[2] >= z0 - 30 and b[5] <= z1 + 30:
                out.append(i)
    return out

# CONDIÇÃO (v22, João): RODAPÉ/BASE ESCONDIDA embaixo do móvel (3+ peças até 150 mm do piso, com pelo menos uma
# no sentido da profundidade = quadro de base) -> DETALHE "RODAPÉ / BASE" embaixo da tabela, balões só lá.
def rodapes(w):
    if w.get('divisoria'): return []
    f_ = FV[w['key']]; ad = 0 if f_[0] else 1
    rs = [i for i in w['itens'] if i['tipo'] == 'comp' and i['bb'][2] <= 20 and i['bb'][5] <= 150]
    if len(rs) < 3: return []
    if not any((i['bb'][ad + 3] - i['bb'][ad]) > 150 for i in rs): return []
    return rs

# ===== PUXADORES (v23, João): o DXF do Promob NÃO traz o puxador; o motor GERA pela regra =====
# Tipo/medida/cor = item "Puxador..." do XML (ex.: Linear Pino Champagne 200 x 15,8 x 37,5). Puxador de perfil/cava/aba = sem barra.
# Porta/frente = chapa fina na frente do módulo (geometria). Porta de giro: puxador VERTICAL do lado OPOSTO às dobradiças
# (dobradiças do DXF), 40 mm da borda; alto (armário) na altura da mão (~1,05 m), balcão perto do topo, aéreo perto de baixo.
# Gaveta/basculante (mais larga que alta): HORIZONTAL centrado, perto do topo (aéreo: perto de baixo).
def _puxador_xml():
    for e in ET.parse(cfg['xml']).iter('ITEM'):
        d_ = e.get('DESCRIPTION', '')
        if d_.lower().startswith('puxador'):
            if re.search(r'perfil|cava|aba|embutid|usinad', d_, re.I): return None
            try: L_ = float(e.get('WIDTH') or 150)
            except Exception: L_ = 150.0
            n_ = d_.lower()
            cor_ = (0.80, 0.70, 0.52) if 'champ' in n_ else (0.83, 0.68, 0.33) if ('dourad' in n_ or 'ouro' in n_) else \
                   (0.12, 0.12, 0.12) if 'preto' in n_ else (0.62, 0.52, 0.46) if 'rose' in n_ else (0.74, 0.74, 0.76)
            return dict(L=max(60.0, min(L_, 1200.0)), cor=cor_)
    return None
PUX_TIPO = _puxador_xml() if cfg.get('xml') else None
_DOBR = [p_ for p_ in P if (lambda d: 12 <= d[0] <= 32 and 40 <= d[1] <= 65 and 65 <= d[2] <= 95)(sorted(p_['dim']))]
def _gerar_puxadores():
    out = []
    if not PUX_TIPO: return out
    L_ = PUX_TIPO['L']; ja = set()
    for w in paredes:
        f_ = FV[w['key']]; ad = 0 if f_[0] else 1; al = 1 - ad; sg_ = f_[ad]
        perto = lambda bb: min(bb[ad] * sg_, bb[ad + 3] * sg_)
        for m in w['itens']:
            if m['tipo'] != 'mod': continue
            mb = m['bb']; fr = perto(mb)
            for p_ in P:
                b = p_['bb']
                if p_['i'] in ja or b[ad + 3] - b[ad] > 30 or (b[al + 3] - b[al]) < 100 or (b[5] - b[2]) < 100: continue
                if not (fr - 40 <= perto(b) <= fr + 5): continue
                if b[al] < mb[al] - 30 or b[al + 3] > mb[al + 3] + 30 or b[2] < mb[2] - 30 or b[5] > mb[5] + 30: continue
                ja.add(p_['i'])
                du, dz = b[al + 3] - b[al], b[5] - b[2]
                face = b[ad] if sg_ > 0 else b[ad + 3]; sai = -sg_     # lado de fora da porta
                if dz >= du:   # porta de giro
                    hs = [h for h in _DOBR if b[al] - 40 <= (h['bb'][al] + h['bb'][al + 3]) / 2 <= b[al + 3] + 40
                          and b[2] <= (h['bb'][2] + h['bb'][5]) / 2 <= b[5] and 0 <= (min(h['bb'][ad] * sg_, h['bb'][ad + 3] * sg_) - perto(b)) <= 160]
                    if not hs: continue
                    hc = sum((h['bb'][al] + h['bb'][al + 3]) / 2 for h in hs) / len(hs)
                    uc = b[al + 3] - 40 if abs(hc - b[al]) < abs(hc - b[al + 3]) else b[al] + 40
                    Lr = min(L_, dz - 120)
                    if dz >= 1200: zc = min(max(1050, b[2] + Lr / 2 + 80), b[5] - Lr / 2 - 80)
                    elif b[5] <= 1100: zc = b[5] - 60 - Lr / 2
                    elif b[2] >= 1200: zc = b[2] + 60 + Lr / 2
                    else: zc = (b[2] + b[5]) / 2
                    seg = dict(eixo='z', c_al=uc, z0=zc - Lr / 2, z1=zc + Lr / 2)
                else:          # gaveta / basculante
                    Lr = min(L_, du - 120); uc = (b[al] + b[al + 3]) / 2
                    zc = b[2] + 40 if b[2] >= 1200 else b[5] - 40
                    seg = dict(eixo='u', u0=uc - Lr / 2, u1=uc + Lr / 2, zc=zc)
                caixas = []
                def cx(a0, a1, dd0, dd1, z0, z1):
                    bb = [0.0] * 6; bb[al], bb[al + 3] = a0, a1; bb[2], bb[5] = z0, z1
                    p0, p1 = face + sai * dd0, face + sai * dd1; bb[ad], bb[ad + 3] = min(p0, p1), max(p0, p1); return bb
                if seg['eixo'] == 'z':
                    u = seg['c_al']
                    caixas.append(cx(u - 7.9, u + 7.9, 27, 37.5, seg['z0'], seg['z1']))                 # barra
                    for zz in (seg['z0'] + 6, seg['z1'] - 16): caixas.append(cx(u - 5, u + 5, 0, 27, zz, zz + 10))   # pés
                else:
                    z = seg['zc']
                    caixas.append(cx(seg['u0'], seg['u1'], 27, 37.5, z - 7.9, z + 7.9))
                    for uu_ in (seg['u0'] + 6, seg['u1'] - 16): caixas.append(cx(uu_, uu_ + 10, 0, 27, z - 5, z + 5))
                out.append(dict(porta=p_['i'], caixas=caixas))
    return out

def tem_porta(m, w):
    # porta/frente/basculante = chapa fina (<= 30 mm na profundidade) na FRENTE do módulo cobrindo >= 40% da face frontal
    f_ = FV[w['key']]; ad = 0 if f_[0] else 1; al = 1 - ad; sg_ = f_[ad]
    perto = lambda bb: min(bb[ad] * sg_, bb[ad + 3] * sg_)
    mb = m['bb']; fr = perto(mb); area_ = (mb[al + 3] - mb[al]) * (mb[5] - mb[2]); cob = 0.0
    for p_ in P:
        b = p_['bb']
        if b[ad + 3] - b[ad] > 30 or (b[al + 3] - b[al]) < 100 or (b[5] - b[2]) < 100: continue
        if not (fr - 40 <= perto(b) <= fr + 25): continue
        ov = max(0, min(b[al + 3], mb[al + 3]) - max(b[al], mb[al])) * max(0, min(b[5], mb[5]) - max(b[2], mb[2]))
        cob += ov
    return cob >= 0.4 * area_

def detalhes(w):
    # nichos de painéis + módulos abertos; grupos que se encostam viram UM detalhe só
    gs = [list(g) for g in nichos(w) + abertos(w)]
    toca = lambda A, B: all(min(A[k + 3], B[k + 3]) - max(A[k], B[k]) > -5 for k in range(3))
    mudou = True
    while mudou:
        mudou = False
        for i0 in range(len(gs)):
            for j0 in range(i0 + 1, len(gs)):
                if any(toca(a['bb'], b['bb']) for a in gs[i0] for b in gs[j0]):
                    gs[i0] += gs.pop(j0); mudou = True; break
            if mudou: break
    return gs

def abertos(w):
    # REGRA (João): NICHO = estrutura ABERTA, SEM PORTA (sem porta/basculante/gaveta), com ou sem prateleira.
    # Módulo sem porta (até 2 m x 1,2 m) + tamponamentos/painéis encostados = DETALHE. Armário com porta NUNCA é nicho.
    f_ = FV[w['key']]; al = 1 if f_[0] else 0; out = []; ja = set()
    for g in nichos(w):
        for i in g: ja.add(id(i))
    for m in w['itens']:
        if m['tipo'] != 'mod' or id(m) in ja: continue
        mb = m['bb']
        if mb[al + 3] - mb[al] > 2000 or mb[5] - mb[2] > 1200 or tem_porta(m, w): continue
        g = [m] + [o for o in w['itens'] if o['tipo'] == 'comp' and id(o) not in ja
                   and all(min(o['bb'][k + 3], mb[k + 3]) - max(o['bb'][k], mb[k]) > -5 for k in range(3))
                   and (o['bb'][5] - o['bb'][2]) <= (mb[5] - mb[2]) + 150   # REGRA (v26): painel alto (tamponamento até o teto) não entra no detalhe do nicho
                   and o['bb'][al] >= mb[al] - 150 and o['bb'][al + 3] <= mb[al + 3] + 150]
        for i in g: ja.add(id(i))
        out.append(g)
    return out

def nichos(w):
    # REGRA (João): TODO NICHO ABERTO vira detalhe. Nicho = conjunto de painéis/tamponamentos encostados entre si
    # (peças "Vista" de acabamento não entram no agrupamento), com 3+ peças e 2+ horizontais, até 2 m de largura e 1,2 m de altura.
    cs = [i for i in w['itens'] if i['tipo'] == 'comp' and not re.match(r'vista\b', i['desc'], re.I)]; grupos_ = []
    toca = lambda A, B: all(min(A[k + 3], B[k + 3]) - max(A[k], B[k]) > -3 for k in range(3))
    for i in cs:
        junto = [g for g in grupos_ if any(toca(i['bb'], j['bb']) for j in g)]
        novo = [i] + [j for g in junto for j in g]
        grupos_ = [g for g in grupos_ if g not in junto] + [novo]
    out = []
    for g in grupos_:
        U_ = list(g[0]['bb'])
        for i in g: U_ = geo.uniao(U_, i['bb'])
        ext = [U_[k + 3] - U_[k] for k in range(3)]
        hz = sum(1 for i in g if i['bb'][5] - i['bb'][2] <= 30)
        ax_ = 1 if FV[w['key']][0] else 0
        if len(g) >= 3 and hz >= 2 and ext[ax_] <= 2000 and ext[2] <= 1200: out.append(g)
    return out

def render3d(page, rect, pids, letra=None, itens=None, ang=None, dmin=4200, contexto=False, **kw):
    # contexto=True (REGRA João): mostra o AMBIENTE em volta (móveis e pedra das paredes vizinhas, perto desta parede)
    # para orientar; balões/listagem continuam só nos móveis da parede da vista.
    its = itens or [i for w in pids for i in PW[w]['itens']]
    U = list(its[0]['bb'])
    for i in its: U = geo.uniao(U, i['bb'])
    E = [U[0] - 80, U[1] - 80, U[2] - 80, U[3] + 80, U[4] + 80, U[5] + 80]
    f = FV[PW[pids[0]]['key']]; a = 0.0
    if len(pids) > 1:
        f2 = FV[PW[pids[1]]['key']]; a = math.radians(22 if f[0] * f2[1] - f[1] * f2[0] >= 0 else -22)
    if ang is not None: a = math.radians(ang)
    hx = f[0] * math.cos(a) - f[1] * math.sin(a); hy = f[0] * math.sin(a) + f[1] * math.cos(a)
    e = math.radians(kw.get('elev', 3 if (contexto and not itens) else 9))   # REGRA: listagem BEM FRONTAL (câmera quase na horizontal)
    fw = (hx * math.cos(e), hy * math.cos(e), -math.sin(e))
    rn = math.hypot(hy, hx); r = (hy / rn, -hx / rn, 0.0)
    up = (r[1] * fw[2] - r[2] * fw[1], r[2] * fw[0] - r[0] * fw[2], r[0] * fw[1] - r[1] * fw[0])
    dot = lambda a_, b_: a_[0] * b_[0] + a_[1] * b_[1] + a_[2] * b_[2]
    tc = ((U[0] + U[3]) / 2, (U[1] + U[4]) / 2, (U[2] + U[5]) / 2)
    D = max(max(U[3] - U[0], U[4] - U[1], U[5] - U[2]) * 1.9, dmin)
    if contexto and not itens and len(pids) == 1: D = max(D, 7000)   # com ambiente: câmera mais longe (menos distorção)  # parede pequena: câmera não chega perto demais (sem distorção)
    cam = (tc[0] - fw[0] * D, tc[1] - fw[1] * D, tc[2] - fw[2] * D)
    ctx = contexto and not itens and len(pids) == 1
    if ctx:
        w0 = PW[pids[0]]; axd = 0 if f[0] else 1; axl = 1 - axd; sg = f[axd]
        prof_ = lambda bb: min((w0['plano'] - bb[axd]) * sg, (w0['plano'] - bb[axd + 3]) * sg)
        _tg = {pi for i in its for pi in i['pecas']}
        def dentro_(bb, pi=None):
            if not (prof_(bb) <= 1000 and bb[axl + 3] >= U[axl] - 1800 and bb[axl] <= U[axl + 3] + 1800): return False
            if pi in _tg: return True
            # REGRA (v26, só parede cortada / bloco): o que fica todo ATRÁS do plano da vista (outro ambiente) não aparece
            if (w0.get('cortada') or w0.get('bloco')) and max((w0['plano'] - bb[axd]) * sg, (w0['plano'] - bb[axd + 3]) * sg) < -100: return False
            cz = sum(((bb[k_] + bb[k_ + 3]) / 2 - cam[k_]) * fw[k_] for k_ in range(3))
            return cz > D * 0.8   # vizinho não fica entre a câmera e a parede
    cor = {}
    for i in inst:
        for pi in i['pecas']: cor[pi] = MADEIRA if i['tipo'] == 'comp' else (0.97, 0.97, 0.97)
    src = []; shell = []; _pmat = {}; _pidx = {}
    _iso = {pi for i in its for pi in i['pecas']} if kw.get('isolado') else None   # REGRA (v18): móvel complexo SOZINHO
    for p_ in P:
        b = p_['bb']
        sd_ = sorted(p_['dim'])
        if _iso is not None and p_['i'] not in _iso: continue
        if p_['i'] in DUP_I: continue
        if p_['i'] in AMB_I or p_['i'] in ELETRO_I:
            if itens: continue   # detalhe (nicho/costas): só os móveis, sem pedra/eletros
            if (dentro_(b, p_['i']) if ctx else all(b[k] <= E[k + 3] and b[k + 3] >= E[k] for k in range(3))):
                c0_ = PEDRA_COR if p_['i'] in AMB_I else ELETRO_COR
                for fc, fl in zip(p_['faces'], p_['ft']): src.append((fc, c0_, fl, 1, len(shell)))
                shell.append(b)
            continue
        if sd_[1] < 50 or sd_[0] > 60: continue  # REGRA: 3D só com MDF (chapas); suportes, dobradiças, cabideiros, pés = fora
        if (dentro_(b, p_['i']) if ctx else (all(b[k] >= E[k] for k in range(3)) and all(b[k + 3] <= E[k + 3] for k in range(3)))):
            base = p_.get('rgb') or cor.get(p_['i'], (0.80, 0.80, 0.83))
            _pmat[len(shell)] = p_.get('mat'); _pidx[len(shell)] = p_['i']
            for uq, nv, ft in p_['fq']: src.append((uq, base, ft, 1, len(shell)))
            shell.append(b)
    for px_ in PUXADORES:   # REGRA (v23): puxador aparece junto com a porta dele
        if px_['porta'] in _pidx.values():
            for bx_ in px_['caixas']:
                for fc in caixa_faces(bx_): src.append((fc, PUX_TIPO['cor'], [True] * 4, 1, len(shell)))
                shell.append(bx_)
    mg = kw.get('margem', 700); R = [U[0] - mg, U[1] - mg, 0 if mg >= 700 else U[2] - mg, U[3] + mg, U[4] + mg, U[5] + min(150, mg)]
    if ctx and MALHA_PAR:
        _cob = []; _ilha = U[5] <= 1200   # móvel baixo solto (ilha/bancada): sem parede inventada nem laterais distantes
        for p_ in MALHA_PAR:
            for fc, fl in zip(p_['faces'], p_['ft']):
                c_ = [sum(v[k_] for v in fc) / len(fc) for k_ in range(3)]
                if min((w0['plano'] - v[axd]) * sg for v in fc) > 1300: continue
                if c_[axl] < U[axl] - 700 or c_[axl] > U[axl + 3] + 700: continue
                if max(v[axd] for v in fc) - min(v[axd] for v in fc) < 1:   # face "de frente" para a câmera
                    pf = (w0['plano'] - c_[axd]) * sg
                    if pf > 100: continue            # parede NA FRENTE do fundo dos móveis: esconderia móvel
                    lo_, hi_ = max(U[axl], min(v[axl] for v in fc)), min(U[axl + 3], max(v[axl] for v in fc))
                    if hi_ > lo_: _cob.append((lo_, hi_))
                elif _ilha: continue
                src.append((fc, (0.94, 0.94, 0.94), fl, 0, -1))
        _tot = 0; _fim = U[axl]
        for lo_, hi_ in sorted(_cob):
            lo_ = max(lo_, _fim)
            if hi_ > lo_: _tot += hi_ - lo_; _fim = hi_
        if not _ilha and not w0.get('divisoria') and _tot < 0.5 * (U[axl + 3] - U[axl]):   # REGRA: parede real cobre < metade dos móveis -> parede de fundo de referência
            bf = [0.0] * 6; bf[axl] = U[axl] - 400; bf[axl + 3] = U[axl + 3] + 400; bf[2] = 0; bf[5] = U[5] + 150
            pl0 = w0['plano']; bf[axd], bf[axd + 3] = (pl0, pl0 + 100) if sg > 0 else (pl0 - 100, pl0)
            for fc in caixa_faces(bf): src.append((fc, (0.94, 0.94, 0.94), [True] * 4, 0, -1))
    if ctx and (PAR_DXF or MALHA_PAR):
        # REGRA (João): paredes reais do DXF que compõem o L (fundo e laterais), com janela/abertura; tira só as que ficam na frente
        for p_ in PAR_DXF:
            b = p_['bb']
            if prof_(b) > 1300 or b[axl + 3] < U[axl] - 1800 or b[axl] > U[axl + 3] + 1800: continue
            for fc in caixa_faces(b): src.append((fc, (0.94, 0.94, 0.94), [True] * 4, 0, -1))
    elif _iso is None:
        if ctx: R[axl] -= 1800; R[axl + 3] += 1800
        for b in paredes_recorte(R):
            for fc in caixa_faces(b): src.append((fc, (0.94, 0.94, 0.94), [True] * 4, 0, -1))
    if ctx:   # REGRA (v15): piso de referência (cinza claro) para a imagem não ficar "flutuando" no branco
        _pz = [0.0] * 6; _pz[axl] = U[axl] - 4000; _pz[axl + 3] = U[axl + 3] + 4000; _pz[2] = -20; _pz[5] = 0
        _pl = w0['plano']; _pz[axd], _pz[axd + 3] = (_pl - 6000, _pl) if sg > 0 else (_pl, _pl + 6000)
        src.append((caixa_faces(_pz)[1], (0.86, 0.86, 0.86), [False] * 4, 0, -1))
    L = (0.35, -0.45, 0.82); nl = math.sqrt(dot(L, L))
    def pj(v):
        rel = (v[0] - cam[0], v[1] - cam[1], v[2] - cam[2]); z = dot(rel, fw)
        return (dot(rel, r) / z, dot(rel, up) / z, z)
    fcs = []
    for vs, base, ft, gr, pc in src:
        pp = [pj(v) for v in vs]
        if min(t[2] for t in pp) < 50: continue
        nm = _n(vs[0], vs[1], vs[2]); fs_ = 0.72 + 0.28 * abs(dot(nm, L)) / nl
        fcs.append((gr, sum(t[2] for t in pp) / len(pp), [(t[0], t[1]) for t in pp], tuple(min(1, x * fs_) for x in base), ft, pc, vs, fs_))
    if not fcs: return
    fcs = _ordem_pecas(fcs, shell, cam)
    xs = [x for f_ in fcs for x, _ in f_[2]]; ys = [y for f_ in fcs for _, y in f_[2]]
    if itens:   # detalhe: enquadra só as peças do detalhe (zoom)
        _alvo = {pi for i in its for pi in i['pecas']}; _bi = {pc_: b_ for pc_, b_ in enumerate(shell)}
        cc = [pj((b_[i0], b_[1 + j0], b_[2 + k0])) for pc_, b_ in _bi.items() if _pidx.get(pc_) in _alvo for i0 in (0, 3) for j0 in (0, 3) for k0 in (0, 3)]
        cc = [c_ for c_ in cc if c_[2] > 50]
        if cc: xs = [c_[0] for c_ in cc]; ys = [c_[1] for c_ in cc]
    if ctx:   # REGRA (v15, João): a imagem PREENCHE o quadro todo. Enquadra os móveis com folga curta
        # (300 mm dos lados, piso até 150 mm acima do móvel); o ambiente (paredes, piso) completa o resto e é recortado.
        Uq = list(U); Uq[axl] -= 300; Uq[axl + 3] += 300; Uq[2] = 0; Uq[5] += 150
        # móvel pequeno: enquadramento mínimo 2,2 m x 2,0 m (mostra o ambiente, não vira close do móvel)
        _fx = max(0, 2200 - (Uq[axl + 3] - Uq[axl])) / 2; Uq[axl] -= _fx; Uq[axl + 3] += _fx; Uq[5] = max(Uq[5], 2000)
        cc = [pj((Uq[i0], Uq[1 + j0], Uq[2 + k0])) for i0 in (0, 3) for j0 in (0, 3) for k0 in (0, 3)]
        cc = [c_ for c_ in cc if c_[2] > 50]
        xs = [c_[0] for c_ in cc]; ys = [c_[1] for c_ in cc]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mgf = 22 if itens else 4 if ctx else 16
    k = min((rect.width - mgf) / (x1 - x0), (rect.height - mgf) / (y1 - y0))
    ox = rect.x0 + (rect.width - (x1 - x0) * k) / 2; oy = rect.y0 + (rect.height - (y1 - y0) * k) / 2
    T = lambda x, y: (ox + (x - x0) * k, oy + (y1 - y) * k)
    if kw.get('visiveis') is not None and _Im is not None:
        # REGRA (v25): quais peças APARECEM nesta imagem (buffer de identificação, desenho na mesma ordem das faces)
        _s = 2.0; _W = max(1, int(rect.width * _s)); _H = max(1, int(rect.height * _s))
        _ib = _Im.new('I', (_W, _H), 0); _dr = _ImD.Draw(_ib)
        for f_ in fcs:
            Q_ = [((T(x_, y_)[0] - rect.x0) * _s, (T(x_, y_)[1] - rect.y0) * _s) for x_, y_ in f_[2]]
            if len(Q_) >= 3: _dr.polygon(Q_, fill=(f_[5] + 1) if f_[5] is not None and f_[5] >= 0 else 0)
        _vv, _cc = _np.unique(_np.asarray(_ib), return_counts=True)
        _bx = {}
        for f_ in fcs:
            if f_[5] is None or f_[5] < 0: continue
            for x_, y_ in f_[2]:
                px_, py_ = T(x_, y_); b_ = _bx.setdefault(f_[5], [px_, py_, px_, py_])
                b_[0] = min(b_[0], px_); b_[1] = min(b_[1], py_); b_[2] = max(b_[2], px_); b_[3] = max(b_[3], py_)
        for v_, c_ in zip(_vv, _cc):
            pc_ = int(v_) - 1
            if v_ <= 0 or pc_ not in _pidx or pc_ not in _bx: continue
            b_ = _bx[pc_]; area_ = max(1.0, (b_[2] - b_[0]) * (b_[3] - b_[1]) * _s * _s)
            if c_ >= 40 and c_ / area_ >= 0.15: kw['visiveis'].add(_pidx[pc_])   # peça aparece DE VERDADE (15%+ dela)
        if kw.get('so_visiveis'): return
    if _Im is not None and cfg.get('textura', True) and any(textura(m_) for m_ in _pmat.values()):
        _raster3d(page, rect, fcs, T, _pmat)
    else:
        if ctx: _tmp = fz.open(); _tp = _tmp.new_page(width=page.rect.width, height=page.rect.height); sh = _tp.new_shape()
        else: sh = page.new_shape()
        for f_ in fcs:
            q, c_, ft = f_[2], f_[3], f_[4]
            Q = [T(x, y) for x, y in q]
            if area2(Q) < 0.1: continue
            sh.draw_polyline(Q + [Q[0]]); sh.finish(color=c_, fill=c_, width=0.5, closePath=True)
            if any(ft):
                for (a_, b_), fl_ in zip(zip(Q, Q[1:] + Q[:1]), ft):
                    if fl_: sh.draw_line(a_, b_)
                sh.finish(color=(0.2, 0.2, 0.2), width=0.35, closePath=False)
        sh.commit()
        if ctx: page.show_pdf_page(rect, _tmp, 0, clip=rect)
    if letra:
        _bal = []; _ja_bal = set()
        for i in its:
            nb = i.get('num_' + letra)
            if not nb or id(i) in kw.get('sem_balao', ()): continue
            if PW.get(i.get('parede'), {}).get('divisoria'):   # REGRA (v18): divisória = UM balão por tipo de peça
                if nb in _ja_bal: continue
                _ja_bal.add(nb)
            b = i['bb']; fi = FV[PW[i['parede']]['key']]; axi = 0 if fi[0] else 1
            c3 = [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2]
            c3[axi] = b[axi] if (fi[axi] > 0) != bool(kw.get('costas')) else b[axi + 3]
            _us = USINADOS.get(i['pecas'][0])
            if _us: c3[_us['al']] = (b[_us['al']] + _us['u'][0]) / 2   # painel usinado: balão na faixa cheia, não no vão
            t3 = pj(c3); cx, cy = T(t3[0], t3[1]); t_ = str(nb); wv = fz.get_text_length(t_, 'hebo', 7) + 4
            # REGRA: balões não ficam um em cima do outro -> desloca o novo e liga ao ponto com traço fino
            bx, by = cx, cy
            for tent in range(24):
                rr = fz.Rect(bx - wv / 2 - 1, by - 6.5, bx + wv / 2 + 1, by + 6.5)
                if not any(rr.intersects(o_) for o_ in _bal): break
                ang_ = tent * 0.9; dist_ = 10 + 3 * tent
                bx, by = cx + dist_ * math.cos(ang_), cy + dist_ * math.sin(ang_)
            if (bx, by) != (cx, cy):
                page.draw_line((cx, cy), (bx, by), color=PRETO, width=0.35); page.draw_circle((cx, cy), 0.9, color=PRETO, fill=PRETO)
            _bal.append(fz.Rect(bx - wv / 2 - 1, by - 6.5, bx + wv / 2 + 1, by + 6.5))
            page.draw_rect(fz.Rect(bx - wv / 2, by - 5.5, bx + wv / 2, by + 5.5), color=PRETO, fill=(1, 1, 0), width=0.4)
            page.insert_text((bx - wv / 2 + 2, by + 2.5), t_, fontname='hebo', fontsize=7)


import xml.etree.ElementTree as _ET
_todas = [e.get('DESCRIPTION', '') for e in _ET.parse(cfg['xml']).iter('ITEM')] if cfg.get('xml') else []
def _pega(rx):
    v = sorted(set(re.sub(r'\s+', ' ', x).strip() for x in _todas if re.search(rx, x, re.I)))
    return ', '.join(v[:3]) if v else 'Não possui'
# puxador por regra DESLIGADO (João: posições erradas). Só liga com "puxadores_regra": true no config.
PUXADORES = _gerar_puxadores() if cfg.get('puxadores_regra') else []
print('PUXADORES:', len(PUXADORES), '(regra desligada; o DXF não traz puxador)' if not PUXADORES else 'gerados')
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
# REGRA (João): planta só com MÓVEIS e PAREDES (sem forro, sanca, pedra, eletros por cima dos móveis)
_par_ids = {p_['i'] for p_ in PAREDES_PECAS} | {p_['i'] for p_ in PAR_DXF}
_linhas_par = set()
for p_ in MALHA_PAR:   # paredes em peça única: faces verticais viram as linhas das paredes (vãos ficam abertos)
    for fc in p_['faces']:
        zs_ = [v[2] for v in fc]
        if max(zs_) - min(zs_) < 500 or min(zs_) > 1200: continue
        xy = sorted({(round(v[0]), round(v[1])) for v in fc})
        if len(xy) >= 2 and math.dist(xy[0], xy[-1]) > 20: _linhas_par.add((xy[0], xy[-1]))
for p_ in P:
    b = p_['bb']
    if p_['i'] not in _usadas and p_['i'] not in _par_ids: continue
    if p_['i'] in _usadas and (sorted(p_['dim'])[1] < 50 or sorted(p_['dim'])[0] > 60): continue
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
    if any(ft):
        for (a_, b_), f_ in zip(zip(q, q[1:] + q[:1]), ft):
            if f_: sh.draw_line(a_, b_)
        sh.finish(color=PRETO if cor is None else (0.3, 0.3, 0.3), width=0.5 if cor is None else 0.3, closePath=False)
sh.commit()
for (a_, b_) in _linhas_par:
    p.draw_line((PX(a_[0]), PY(a_[1])), (PX(b_[0]), PY(b_[1])), color=PRETO, width=0.9)
for w in paredes:          # REGRA GERAL (v23, João): planta LIMPA = UMA cota por parede, o COMPRIMENTO TOTAL dos móveis
    f = FV[w['key']]; its = w['itens']
    if w['key'][0] == 'x':
        vals = [min(i['bb'][1] for i in its), max(i['bb'][4] for i in its)]
        xl = PX(w['plano']) + (16 if f[0] > 0 else -16)
        cadeia_v(p, vals, xl, PX(w['plano']), PY, fs=7)
    else:
        vals = [min(i['bb'][0] for i in its), max(i['bb'][3] for i in its)]
        yl = PY(w['plano']) + (16 if f[1] < 0 else -16)
        cadeia_h(p, vals, yl, PY(w['plano']), PX, fs=7)
_circ = []
for v in V:                # setas das vistas (uma por parede); se encostar em outra, desliza ao longo da parede
  for wid, letra_ in zip(v['paredes'], v['letras']):
    w = PW[wid]; f = FV[w['key']]; its = w['itens']
    cx = sum((i['bb'][0] + i['bb'][3]) / 2 for i in its) / len(its); cy = sum((i['bb'][1] + i['bb'][4]) / 2 for i in its) / len(its)
    ex, ey = PX(cx) - f[0] * 30, PY(cy) + f[1] * 30
    for _t in range(8):
        sx, sy = ex - f[0] * 32, ey + f[1] * 32
        cc_ = (sx - f[0] * 8, sy + f[1] * 8); seg = [(sx, sy), (ex, ey), cc_]
        if all(math.dist(a_, b_) > 22 for a_ in seg for b_ in _circ): break
        ex += 30 * abs(f[1]) * (1 if _t % 2 == 0 else -2); ey += 30 * abs(f[0]) * (1 if _t % 2 == 0 else -2)
    _circ += [(sx, sy), (ex, ey), (sx - f[0] * 8, sy + f[1] * 8)]
    p.draw_line((sx, sy), (ex, ey), color=RED, width=1.4)
    p.draw_polyline([(ex + f[1] * 4 - f[0] * 7, ey + f[0] * 4 + f[1] * 7), (ex, ey), (ex - f[1] * 4 - f[0] * 7, ey - f[0] * 4 + f[1] * 7)], color=RED, width=1.4)
    p.draw_circle((sx - f[0] * 8, sy + f[1] * 8), 7, color=RED, fill=BRANCO, width=1)
    p.insert_text((sx - f[0] * 8 - 3.5, sy + f[1] * 8 + 3.5), letra_, fontname='hebo', fontsize=10, color=RED)
lab = f'PLANTA BAIXA - ESC. 1:{S}'
p.insert_text((pr.x0 + pr.width / 2 - fz.get_text_length(lab, 'hebo', 8) / 2, pr.y1 - 3), lab, fontname='hebo', fontsize=8)

# PRANCHA 4: visão geral
n += 1; p = nova_prancha(doc, n, 'VISÃO GERAL DOS MÓVEIS')
com_img = VW
m = len(com_img); a = AREA_IN
_nc = 1 if m == 1 else 2 if m <= 4 else 3; _nr = -(-m // _nc)
cel = [fz.Rect(a.x0 + (i % _nc) * a.width / _nc, a.y0 + (i // _nc) * a.height / _nr, a.x0 + (i % _nc + 1) * a.width / _nc, a.y0 + (i // _nc + 1) * a.height / _nr) for i in range(m)]
for v, c in zip(com_img, cel):
    (encaixa(p, v['img3d'], fz.Rect(c.x0 + 4, c.y0 + 16, c.x1 - 4, c.y1 - 4)) if v.get('img3d') else render3d(p, fz.Rect(c.x0 + 4, c.y0 + 16, c.x1 - 4, c.y1 - 4), v['paredes'], contexto=True))
    p.insert_text((c.x0 + 6, c.y0 + 11), v['titulo'], fontname='hebo', fontsize=10, color=RED)
for j in range(1, _nc): p.draw_line((a.x0 + j * a.width / _nc, AREA.y0), (a.x0 + j * a.width / _nc, AREA.y1), color=PRETO, width=0.6)
for j in range(1, _nr): p.draw_line((AREA.x0, a.y0 + j * a.height / _nr), (AREA.x1, a.y0 + j * a.height / _nr), color=PRETO, width=0.6)

# REGRA (v26, João): LISTAGEM POLUÍDA (mais de 15 linhas) = DUAS pranchas: SUPERIORES (armários de cima e altos) e
# INFERIORES (balcões). Cada uma com a tabela e os balões só das suas peças (numeração própria). Sem os dois grupos:
# divide a parede ao meio (PARTE 1 / PARTE 2).
LIST_MAX = 15; _extra = 0
def _partes(s_):
    global _extra
    its = [i for w in s_['paredes'] for i in PW[w]['itens']]
    if len(s_['linhas']) <= LIST_MAX or not its: return [s_]
    sup = [i for i in its if (i['bb'][2] + i['bb'][5]) / 2 > 1300]; inf = [i for i in its if i not in sup]
    if sup and inf: gs = [('SUPERIORES', sup), ('INFERIORES', inf)]
    else:
        f_ = FV[PW[s_['paredes'][0]]['key']]; al = 1 if f_[0] else 0
        o_ = sorted(its, key=lambda i: (i['bb'][al] + i['bb'][al + 3]) / 2); h_ = len(o_) // 2
        gs = [('PARTE 1', o_[:h_]), ('PARTE 2', o_[h_:])]
    out = []
    for k_, (nome, g) in enumerate(gs):
        key = f"{s_['letra']}{k_ + 1}"; chv = []
        for i in sorted(g, key=lambda i: (i['tipo'] != 'mod', i['n'])):
            if (i['desc'], i['dim']) not in chv: chv.append((i['desc'], i['dim']))
        for i in g: i['num_' + key] = chv.index((i['desc'], i['dim'])) + 1
        lin = [(d, dm, '') for d, dm in chv]
        if k_ == 0 and s_ is VW[0]: lin += [(d, dm, '*') for d, dm in nao_achados]
        out.append(dict(letra=key, titulo=f"{s_['titulo']} - {nome}", linhas=lin, paredes=s_['paredes'], ids={id(i) for i in g}, primeiro=k_ == 0, base=s_))
    _extra += len(out) - 1
    return out

# por bloco: listagem de cada parede (frontal) e depois as cotas do bloco (paredes lado a lado)
for v in V:
    GS = [geom_parede(PW[w]) for w in v['paredes']]
    if v.get('divisoria'):
        # REGRA (v18b, João): móvel complexo (divisória ripada em L) = SOZINHO, sem o ambiente, em DUAS imagens na
        # diagonal (uma de cada lado do L), cada uma na sua prancha; tabela completa nas duas; um balão por tipo de peça.
        its_ = PW[v['paredes'][0]]['itens']
        # REGRA (v20, João): 1ª prancha = 3D FRONTAL (como a cota, com todas as ripas); 2ª = 3D LATERAL pegando o L
        w_ = PW[v['paredes'][0]]; f_ = FV[w_['key']]; ax_ = 1 if f_[0] else 0; axd_ = 1 - ax_
        rd_ = (f_[1], -f_[0])
        cm_ = sum((i['bb'][ax_] + i['bb'][ax_ + 3]) / 2 for i in its_) / len(its_)
        dd_ = [i for i in its_ if abs((i['bb'][axd_] + i['bb'][axd_ + 3]) / 2 - w_['plano']) > 120]   # peças fora da faixa = perna do L
        lado_ = (sum((i['bb'][ax_] + i['bb'][ax_ + 3]) / 2 for i in dd_) / len(dd_) - cm_) * rd_[ax_] if dd_ else 1
        if w_.get('bloco'):   # REGRA (v26): bloco de painéis = lateral vista pelo lado onde estão os móveis (de dentro do ambiente)
            _ms = [i for i in inst if i['tipo'] == 'mod']
            if _ms: lado_ = (sum((i['bb'][ax_] + i['bb'][ax_ + 3]) / 2 for i in _ms) / len(_ms) - cm_) * rd_[ax_]
        for ang_ in (0, (90 if lado_ > 0 else -90)):   # REGRA (v24, João): 2ª imagem = LATERAL RETA (90°), não diagonal
            n += 1; p = nova_prancha(doc, n, f"MÓDULOS E PAINÉIS - {v['titulo']}")
            r_img = fz.Rect(AREA_IN.x0 + 258, AREA_IN.y0, AREA_IN.x1, AREA_IN.y1)
            if ang_ == 0:
                tabela(p, v['linhas'], AREA_IN.x0, AREA_IN.y0)
                render3d(p, r_img, v['paredes'], letra=v['letra'], itens=its_, ang=ang_, elev=6, dmin=5200, margem=60, isolado=True)
                continue
            # REGRA (v25, João): a LATERAL lista SÓ as peças que APARECEM nela (numeração própria desta prancha)
            _vis = set(); _tmp = fz.open(); _tp = _tmp.new_page(width=p.rect.width, height=p.rect.height)
            render3d(_tp, r_img, v['paredes'], itens=its_, ang=ang_, elev=6, dmin=5200, margem=60, isolado=True, visiveis=_vis, so_visiveis=True)
            its_v = [i for i in its_ if any(pi in _vis for pi in i['pecas'])] or its_
            lt_l = v['letra'] + 'L'; chv_l = []
            for i in sorted(its_v, key=lambda i: i['n']):
                if (i['desc'], i['dim']) not in chv_l: chv_l.append((i['desc'], i['dim']))
            for i in its_: i.pop('num_' + lt_l, None)
            for i in its_v: i['num_' + lt_l] = chv_l.index((i['desc'], i['dim'])) + 1
            tabela(p, [(d, dm, '') for d, dm in chv_l], AREA_IN.x0, AREA_IN.y0)
            render3d(p, r_img, v['paredes'], letra=lt_l, itens=its_, ang=ang_, elev=6, dmin=5200, margem=60, isolado=True)
    for s_ in ([] if v.get('divisoria') else [q_ for s0_ in v['subs'] for q_ in _partes(s0_)]):
        n += 1; p = nova_prancha(doc, n, f"MÓDULOS E PAINÉIS - {s_['titulo']}")
        yb = tabela(p, s_['linhas'], AREA_IN.x0, AREA_IN.y0)
        if nao_achados and s_.get('base', s_) is VW[0] and s_.get('primeiro', True):
            p.insert_text((AREA_IN.x0, yb + 9), '* não localizado no DXF - conferir', fontname='helv', fontsize=6, color=(0.7, 0, 0))
        # REGRA (João): nicho pequeno/apertado ganha uma imagem só dele embaixo da tabela; continua desenhado na imagem
        # grande, mas os balões dele ficam SÓ no detalhe (imagem grande menos poluída)
        nis = [(w, c) for w in s_['paredes'] for c in detalhes(PW[w])]
        # REGRA (João): item listado que fica ESCONDIDO ATRÁS dos módulos (ex.: painel nas costas da ilha)
        # ganha um detalhe visto de trás; balão dele só nesse detalhe.
        cts = [(w, c + [o for o in costas_paineis(PW[w]) if o not in c], 'costas') for w in s_['paredes'] for c in [costas(PW[w])] if c or costas_paineis(PW[w])]
        mps = [(w, t_) for w in s_['paredes'] for t_ in pequenos(PW[w])]
        rds = [(w, r_) for w in s_['paredes'] for r_ in [rodapes(PW[w])] if r_]
        if s_.get('ids') is not None:   # prancha dividida: só os detalhes das peças desta parte
            _ok = lambda c: any(id(i) in s_['ids'] for i in c)
            nis = [(w, c) for w, c in nis if _ok(c)]; cts = [(w, c, t) for w, c, t in cts if _ok(c)]
            mps = [(w, t_) for w, t_ in mps if _ok(t_['todos'])]; rds = [(w, r_) for w, r_ in rds if _ok(r_)]
        render3d(p, fz.Rect(AREA_IN.x0 + 258, AREA_IN.y0, AREA_IN.x1, AREA_IN.y1), s_['paredes'], letra=s_['letra'], contexto=True,
                 sem_balao={id(i) for _, c in nis for i in c} | {id(i) for _, c, _ in cts for i in c} | {id(i) for _, t_ in mps for i in t_['todos']} | {id(i) for _, r_ in rds for i in r_})
        nis = [(w, c, 'nicho') for w, c in nis] + cts + [(w, t_['mostra'], 'modulo') for w, t_ in mps] + [(w, r_, 'rodape') for w, r_ in rds]
        if nis:
            y0_ = (yb + 18 if not (nao_achados and s_ is VW[0]) else yb + 24)
            # quadro com o FORMATO do detalhe (nicho largo = quadro largo e baixo); largos ocupam a linha inteira
            def _asp(w, c):
                ax_ = 1 if FV[PW[w]['key']][0] else 0
                la = max(i['bb'][ax_ + 3] for i in c) - min(i['bb'][ax_] for i in c); al = max(i['bb'][5] for i in c) - min(i['bb'][2] for i in c)
                return max(0.25, min(1.6, al / max(la, 1)))
            itens_q = [(w, c, tp_, _asp(w, c)) for w, c, tp_ in nis]
            # REGRA: detalhes usam TODA a coluna da esquerda embaixo da tabela (um por linha; se faltar altura, 2 por linha)
            disp = AREA_IN.y1 - y0_; n_ = len(itens_q)
            por = 1 if disp / n_ >= 95 else 2; rows = [itens_q[i0:i0 + por] for i0 in range(0, n_, por)]
            h2 = disp / len(rows); quadros = []; yy = y0_
            for r0 in rows:
                lg = (248 - 4 * (len(r0) - 1)) / len(r0); xx = AREA_IN.x0
                for it_ in r0:
                    quadros.append((it_, fz.Rect(xx, yy, xx + lg, yy + h2 - 4))); xx += lg + 4
                yy += h2
            for (w, c, tp_, _a), r_ in quadros:
                p.draw_rect(r_, color=PRETO, width=0.5)
                _tit = 'DETALHE - NICHO' if tp_ == 'nicho' else 'DETALHE - COSTAS' if tp_ == 'costas' else 'DETALHE - RODAPÉ / BASE' if tp_ == 'rodape' else ('DETALHE - ' + c[0]['desc'].upper())[:44]
                p.insert_text((r_.x0 + 4, r_.y0 + 10), _tit, fontname='hebo', fontsize=7.5, color=RED)
                if tp_ == 'rodape':   # base/rodapé sozinho visto de cima em diagonal (como o PDF do João)
                    render3d(p, fz.Rect(r_.x0 + 2, r_.y0 + 14, r_.x1 - 2, r_.y1 - 2), [w], letra=s_['letra'], itens=c, ang=28, elev=38, dmin=2600, margem=60, isolado=True)
                    continue
                if tp_ == 'modulo':   # módulo pequeno sozinho, em diagonal leve, balões só dele
                    render3d(p, fz.Rect(r_.x0 + 2, r_.y0 + 14, r_.x1 - 2, r_.y1 - 2), [w], letra=s_['letra'], itens=c, ang=25, elev=18, dmin=2000, margem=60, isolado=True)
                    continue
                if tp_ == 'costas':
                    todos_ = PW[w]['itens']
                    render3d(p, fz.Rect(r_.x0 + 2, r_.y0 + 14, r_.x1 - 2, r_.y1 - 2), [w], letra=s_['letra'], itens=todos_, ang=180 + 20,
                             dmin=4500, margem=60, costas=True, sem_balao={id(i) for i in todos_ if all(i is not j for j in c)})
                    continue
                # câmera virada para o lado aberto do nicho (em direção ao meio da parede)
                fw_ = FV[PW[w]['key']]; ax_ = 1 if fw_[0] else 0
                cm_ = sum((i['bb'][ax_] + i['bb'][ax_ + 3]) / 2 for i in PW[w]['itens']) / len(PW[w]['itens'])
                cn_ = sum((i['bb'][ax_] + i['bb'][ax_ + 3]) / 2 for i in c) / len(c)
                r_dir = (fw_[1], -fw_[0])  # direção "direita" da câmera frontal
                lado = (cm_ - cn_) * r_dir[ax_]
                render3d(p, fz.Rect(r_.x0 + 2, r_.y0 + 14, r_.x1 - 2, r_.y1 - 2), [w], letra=s_['letra'], itens=c, ang=(-1 if lado > 0 else 1) * (28 if max(i['bb'][ax_ + 3] for i in c) - min(i['bb'][ax_] for i in c) < 1000 else 14), dmin=2200, margem=60)
    # cotas
    n += 1; p = nova_prancha(doc, n, f"MEDIDAS E ALTURAS - {v['titulo']}")
    nc = len(GS); zm = max(G['ztop'] for G in GS)
    Wm = [G['vmax'] - G['vmin'] for G in GS]
    # REGRA (v16, João): parede sozinha na prancha -> a prancha se divide: FRONTAL à esquerda, LATERAL do móvel à direita
    LT = None   # REGRA (v26, João): COTA É SÓ A VISTA FRONTAL. Não tem vista lateral na prancha de cotas.
    Wl = (LT['hmax'] + LT['esp'] + 350) if LT else 0
    # REGRA (v15, João): a elevação PREENCHE a prancha (parede a parede, piso ao teto), mesma escala nas colunas;
    # móvel pequeno não fica pequeno: escala sobe até 1:10. Colunas proporcionais ao tamanho de cada parede.
    S, k = escala_para(sum(Wm) + Wl, zm, AREA_IN.width - 80 * (nc + (1 if LT else 0)), AREA_IN.height - 62, cheio=True)
    if LT:
        cwl = max(Wl * k + 80, AREA_IN.width * 0.28)
        cws = [AREA_IN.width - cwl]
    else:
        sobra = (AREA_IN.width - sum(w_ * k + 80 for w_ in Wm)) / nc
        cws = [w_ * k + 80 + sobra for w_ in Wm]
    fy = AREA_IN.y0 + (AREA_IN.height - 62 - zm * k) / 2 + 22 + zm * k
    for j, G in enumerate(GS):
        cw = cws[j]; cx0 = AREA_IN.x0 + sum(cws[:j])
        ox = cx0 + (cw - Wm[j] * k) / 2 + (G['umin'] - G['vmin']) * k
        desenhar(p, G, ox, fy, k)
        cotar(p, G, ox, fy, k)
        lab = (f"{v['titulo']} - ESC. 1:{S:g}" if v.get('divisoria') else f"VISTA {v['letras'][j]} - ESC. 1:{S:g}")
        p.insert_text((cx0 + cw / 2 - fz.get_text_length(lab, 'hebo', 8.5) / 2, min(fy + 44, AREA_IN.y1 - 2)), lab, fontname='hebo', fontsize=8.5)
        if j: p.draw_line((cx0, AREA.y0), (cx0, AREA.y1), color=PRETO, width=0.6)
    if LT:
        cx0 = AREA_IN.x0 + cws[0]
        oxl = cx0 + (cwl - (LT['hmax'] + LT['esp'] + 60) * k) / 2 + LT['esp'] * k
        desenhar_lateral(p, LT, oxl, fy, k, GS[0]['ztop'])
        cotar_lateral(p, LT, oxl, fy, k)
        lab = (f"{v['titulo']} - LATERAL - ESC. 1:{S:g}" if v.get('divisoria') else f"VISTA {v['letras'][0]} - LATERAL - ESC. 1:{S:g}")
        p.insert_text((cx0 + cwl / 2 - fz.get_text_length(lab, 'hebo', 8.5) / 2, min(fy + 44, AREA_IN.y1 - 2)), lab, fontname='hebo', fontsize=8.5)
        p.draw_line((cx0, AREA.y0), (cx0, AREA.y1), color=PRETO, width=0.6)


# REGRA (v18, PDF da Priscila): DIVISOR DE GAVETA (joias) = prancha própria: listagem das peças, 3D do divisor e
# VISTA DE CIMA com as cotas de todos os vãos (largura e profundidade) + altura das peças.
def _prancha_peca(g_, titulo, rotulo):
    global n, _nl
    n += 1; p = nova_prancha(doc, n, titulo)
    lt_ = letras[_nl]; _nl += 1
    chv = []
    for i in sorted(g_, key=lambda i: i['n']):
        if (i['desc'], i['dim']) not in chv: chv.append((i['desc'], i['dim']))
    for i in g_: i['num_' + lt_] = chv.index((i['desc'], i['dim'])) + 1
    yb = tabela(p, [(d, dm, '') for d, dm in chv], AREA_IN.x0, AREA_IN.y0)
    wid_ = g_[0].get('parede') if g_[0].get('parede') in PW else paredes[0]['id']
    for i in g_: i['parede'] = wid_
    # REGRA (v20, João): 3D SÓ das peças (isolado), com os balões da listagem
    r3 = fz.Rect(AREA_IN.x0, yb + 12, AREA_IN.x0 + 248, AREA_IN.y1)
    p.draw_rect(r3, color=PRETO, width=0.5)
    render3d(p, fz.Rect(r3.x0 + 2, r3.y0 + 2, r3.x1 - 2, r3.y1 - 2), [wid_], letra=lt_, itens=g_, ang=30, elev=35, dmin=1800, margem=60, isolado=True)
    x0_ = min(i['bb'][0] for i in g_); x1_ = max(i['bb'][3] for i in g_); y0_ = min(i['bb'][1] for i in g_); y1_ = max(i['bb'][4] for i in g_)
    ra = fz.Rect(AREA_IN.x0 + 262, AREA_IN.y0, AREA_IN.x1, AREA_IN.y1 - 20)
    Sd, kd = next(((S_, MM / S_) for S_ in (2, 2.5, 5, 10, 15, 20) if (x1_ - x0_) * MM / S_ <= ra.width - 90 and (y1_ - y0_) * MM / S_ <= ra.height - 70), (20, MM / 20))
    ox_ = ra.x0 + (ra.width - (x1_ - x0_) * kd) / 2; oy_ = ra.y0 + (ra.height - (y1_ - y0_) * kd) / 2
    X_ = lambda x: ox_ + (x - x0_) * kd
    Y_ = lambda y: oy_ + (y1_ - y) * kd
    fcs_ = []
    for i in g_:
        for pi in i['pecas']:
            b = P[pi]['bb']
            fcs_.append((b[5], [(b[0], b[1]), (b[3], b[1]), (b[3], b[4]), (b[0], b[4])], P[pi].get('rgb', MADEIRA), [True] * 4, P[pi].get('mat'), pi))
    fcs_.sort(key=lambda t: t[0])
    _desenho2d(p, fcs_, lambda x, y: (X_(x), Y_(y)))
    fin = lambda i: (i['bb'][3] - i['bb'][0]) <= 40 or (i['bb'][4] - i['bb'][1]) <= 40
    vx = [v for i in g_ if fin(i) and i['bb'][3] - i['bb'][0] < i['bb'][4] - i['bb'][1] for v in (i['bb'][0], i['bb'][3])]
    vy = [v for i in g_ if fin(i) and i['bb'][3] - i['bb'][0] >= i['bb'][4] - i['bb'][1] for v in (i['bb'][1], i['bb'][4])]
    cadeia_h(p, [x0_, x1_] + vx, Y_(y0_) + 16, Y_(y0_) + 2, X_)
    cadeia_h(p, [x0_, x1_], Y_(y1_) - 14, Y_(y1_) - 2, X_)
    cadeia_v(p, [y0_, y1_] + vy, X_(x1_) + 18, X_(x1_) + 2, lambda y: Y_(y))
    cadeia_v(p, [y0_, y1_], X_(x0_) - 14, X_(x0_) - 2, lambda y: Y_(y))
    alt_ = round(max(i['bb'][5] for i in g_) - min(i['bb'][2] for i in g_))
    lab = f'{rotulo} - VISTA DE CIMA - ESC. 1:{Sd:g}   |   ALTURA: {alt_} mm'
    p.insert_text((ra.x0 + ra.width / 2 - fz.get_text_length(lab, 'hebo', 8.5) / 2, AREA_IN.y1 - 6), lab, fontname='hebo', fontsize=8.5)

# REGRA (v18/v20): DIVISOR DE GAVETA e GAVETA/MÓDULO MONTADO COM PAINÉIS = prancha própria (tabela + 3D isolado + vista de cima)
for g_ in GAVETAS: _prancha_peca(g_, 'GAVETA MONTADA COM PAINÉIS', 'GAVETA')
for g_ in DIVISORES: _prancha_peca(g_, 'DIVISOR DE GAVETA', 'DIVISOR')

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
esperado = 4 + len(VW) + _extra + len(V) + len(DIVISORES) + len(DIVISORIAS) + len(BLOCOS) + len(GAVETAS)
q = [f"# QUALIDADE — {cfg['dados']['cliente']} / {cfg['dados']['ambiente']} (gerado por script)", '',
     f"- {'APROVADO' if n == esperado else 'REPROVADO'} | nº de pranchas {n} = 4 + {len(VW)} listagens + {len(V)} cotas" + (f" + {len(DIVISORES)} divisor(es) de gaveta" if DIVISORES else '') + (f" + {len(GAVETAS)} gaveta(s) em painéis" if GAVETAS else '') + (f" | divisória ripada: {len(DIVISORIAS)}" if DIVISORIAS else ''),
     f"- {'APROVADO' if not nao_achados else 'INCERTO'} | itens localizados no DXF: {len(linhas) - len(nao_achados)}/{len(linhas)}"]
for d, dm in nao_achados: q.append(f"  - INCERTO: {d} {dm} (não localizado; listado com * na vista {VW[0]['letra']})")
q.append(f"- {'APROVADO' if confere else 'INCERTO'} | XML confere com o projeto" + ('' if confere else ' — exportar XML atual'))
TEX_FALTA = [m_ for m_ in TEX_FALTA if not textura(m_)] + [m_ for m_, v_ in _cc.items() if not v_ and m_ in _todas_mats]
q.append(f"- {'APROVADO' if not TEX_FALTA else 'INCERTO'} | texturas dos materiais" + ('' if not TEX_FALTA else ' — faltando (sai cor lisa): ' + ', '.join(TEX_FALTA)))
for v in VW:
    _ex = []
    for w_ in v['paredes']:
        if pequenos(PW[w_]): _ex.append(f"{len(pequenos(PW[w_]))} detalhe(s) de módulo pequeno")
        if rodapes(PW[w_]): _ex.append(f"rodapé/base ({len(rodapes(PW[w_]))} peças) em detalhe")
        if PW[w_].get('perna_l'): _ex.append("perna do L com vista própria")
        if costas_paineis(PW[w_]): _ex.append(f"{len(costas_paineis(PW[w_]))} peça(s) atrás de painel no detalhe das costas")
    q.append(f"- {v['titulo']}: paredes {', '.join(v['paredes'])} | {len(v['linhas'])} linhas de listagem" + (' | CONDIÇÕES -> ' + ', '.join(_ex) if _ex else ''))
q += [f"  {v['letra']}{i}: {d} {dm}{m_}" for v in VW for i, (d, dm, m_) in enumerate(v['linhas'], 1)]
open(os.path.splitext(cfg['saida'])[0] + '_QUALIDADE.md', 'w', encoding='utf-8').write('\n'.join(q))
print('\n'.join(q))
for i in range(len(doc)):
    doc[i].get_pixmap(dpi=80).save(os.path.join(os.path.dirname(cfg['saida']), f'_prev_{i + 1}.png'))
print('OK', cfg['saida'])
