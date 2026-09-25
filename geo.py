# GEO — liga cada item da listagem (XML ou caderno) à sua posição real no DXF.
# Módulo = par de laterais (peças finas e altas) cujo volume bate com L x A x P.
# Painel/tamponamento = peça única cujas 3 medidas batem.
import json, re, itertools

TOL = 3.0

def num(s): return float(str(s).replace(',', '.'))

def parse_dim(dm):
    w, h, d = [num(x) for x in dm.lower().split('x')]
    return w, h, d

def eh_componente(desc):
    return bool(re.match(r'\s*(tampon|painel|vista|rodap|fecham|prateleira ext)', desc, re.I))

def carregar(path):
    P = json.load(open(path))
    for i, p in enumerate(P): p['i'] = i
    return P

def uniao(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3]), max(a[4], b[4]), max(a[5], b[5])]

def dentro(b, U, tol=2.5):
    return all(b[k] >= U[k] - tol for k in range(3)) and all(b[k + 3] <= U[k + 3] + tol for k in range(3))

def laterais(P, zmin=150):
    out = []
    for p in P:
        dx, dy, dz = p['dim']
        if min(dx, dy) <= 26 and dz >= zmin and max(dx, dy) >= 150:
            p['eixo'] = 'x' if dx <= dy else 'y'
            out.append(p)
    return out

def casar(P, linhas, qtd=None):
    """linhas: [(desc, 'LxAxP')]. Retorna instâncias: dict(n, desc, dim, bb, tipo, pecas)."""
    # REGRA (v26): módulo BAIXO (adega/nicho de 150 mm) tem laterais de 100-150 mm -> entram só para módulo até 200 mm
    L = laterais(P, 100)
    usados = set(); inst = []
    # 1) componentes: peça única
    for n, (desc, dm) in enumerate(linhas, 1):
        if not eh_componente(desc): continue
        alvo = sorted(parse_dim(dm)); lim = (qtd or {}).get((desc, dm)); pegou = 0
        for p in P:
            if lim is not None and pegou >= lim: break
            if p['i'] in usados: continue
            if all(abs(a - b) <= 1.6 for a, b in zip(sorted(p['dim']), alvo)):
                usados.add(p['i']); pegou += 1
                inst.append(dict(n=n, desc=desc, dim=dm, bb=p['bb'], tipo='comp', pecas=[p['i']]))
    # 2) módulos: par de laterais
    cands = []
    for n, (desc, dm) in enumerate(linhas, 1):
        if eh_componente(desc): continue
        w, h, d = parse_dim(dm)
        orients = [(w, h, 0)]
        # REGRA (v26): módulo GIRADO no Promob (adega deitada: XML 150 x 870 x 600 = 870 de largura, 150 de altura)
        if h > 2 * w and w <= 300: orients.append((h, w, 5))
        for w, h, pen in orients: cands += _cands_mod(L, n, desc, dm, w, h, d, pen)
    cands.sort(key=lambda c: c[0])
    ocupado = []
    for e, n, desc, dm, ia, ib, U, wr in cands:
        if ia in usados or ib in usados: continue
        if any(_sobrepoe(U, O) for O in ocupado): continue
        usados.update((ia, ib)); ocupado.append(U)
        inst.append(dict(n=n, desc=desc, dim=dm, bb=U, tipo='mod', pecas=[ia, ib], larg=wr))
    # peças internas de cada módulo (para o desenho), portas ficam fora porque estão à frente das laterais
    for it in inst:
        if it['tipo'] == 'mod':
            it['pecas'] = [p['i'] for p in P if dentro(p['bb'], it['bb'])]
    return inst

def _cands_mod(L, n, desc, dm, w, h, d, pen=0):
        cands = []
        tw, td = (45, 110) if 'canto' in desc.lower() else (TOL, 70)
        tz0 = 160 if 'rodap' in desc.lower() else TOL
        for a, b in itertools.combinations(L, 2):
            if h > 200 and min(a['dim'][2], b['dim'][2]) < 150: continue
            if abs(a['bb'][2] - b['bb'][2]) > tz0 or abs(a['bb'][5] - b['bb'][5]) > TOL: continue
            U = uniao(a['bb'], b['bb'])
            ux, uy, uz = U[3] - U[0], U[4] - U[1], U[5] - U[2]
            dh = h - uz
            if not (-TOL <= dh <= (260 if 'rodap' in desc.lower() else 45)): continue
            best = None
            for fw, fd in ((ux, uy), (uy, ux)):
                ew = abs(fw - w); ed = d - fd
                if ew <= tw and -TOL <= ed <= td:
                    e = ew + abs(dh) * (0.02 if 'rodap' in desc.lower() else 0.2) + max(0, ed) * 0.1
                    if best is None or e < best: best = e
            if best is None: continue
            if a['eixo'] == b['eixo']:
                ia = (a['bb'][1], a['bb'][4]) if a['eixo'] == 'x' else (a['bb'][0], a['bb'][3])
                ib = (b['bb'][1], b['bb'][4]) if b['eixo'] == 'x' else (b['bb'][0], b['bb'][3])
                if abs(ia[0] - ib[0]) > 30 or abs(ia[1] - ib[1]) > 30: continue
            cands.append((best + pen, n, desc, dm, a['i'], b['i'], U, w))
        return cands

def _sobrepoe(A, B, folga=5):
    return all(min(A[k + 3], B[k + 3]) - max(A[k], B[k]) > folga for k in range(3))

# ---------------- paredes e vistas ----------------
PAREDES = {  # f = direção do olhar (para dentro da parede)
    'y-': (0, -1), 'y+': (0, 1), 'x-': (-1, 0), 'x+': (1, 0)}

def limites(inst):
    return [min(i['bb'][0] for i in inst), min(i['bb'][1] for i in inst),
            max(i['bb'][3] for i in inst), max(i['bb'][4] for i in inst)]

def parede_de(it, lim, P):
    b = it['bb']
    dist = {'x-': b[0] - lim[0], 'x+': lim[2] - b[3], 'y-': b[1] - lim[1], 'y+': lim[3] - b[4]}
    dx, dy = b[3] - b[0], b[4] - b[1]
    if it['tipo'] == 'mod':
        a = P[it['pecas'][0]].get('eixo') if False else None
    # eixo ao longo da parede = maior extensão horizontal (módulo: largura; painel: comprimento)
    if it['tipo'] == 'mod':
        w = it.get('larg') or parse_dim(it['dim'])[0]
        ao_longo = 'x' if abs(dx - w) <= abs(dy - w) else 'y'
    else:
        ao_longo = 'x' if dx >= dy else 'y'
    ops = ('y-', 'y+') if ao_longo == 'x' else ('x-', 'x+')
    return min(ops, key=lambda k: dist[k])

def uz(p, f):
    """coordenada horizontal na elevação (esquerda->direita de quem olha a parede)"""
    return p[0] * f[1] - p[1] * f[0]

def caixa_elev(bb, f):
    us = [uz((x, y), f) for x in (bb[0], bb[3]) for y in (bb[1], bb[4])]
    return min(us), bb[2], max(us), bb[5]

def agrupar_vistas(inst, paredes):
    """junta paredes vizinhas com móveis encostando no mesmo canto (formando L). Máx. 2 por vista."""
    lim = limites(inst)
    cantos = {('x-', 'y-'): (lim[0], lim[1]), ('x+', 'y-'): (lim[2], lim[1]), ('x-', 'y+'): (lim[0], lim[3]), ('x+', 'y+'): (lim[2], lim[3])}
    liga = []
    for (a, b), (cx, cy) in cantos.items():
        if a not in paredes or b not in paredes: continue
        def perto(w):
            return sum(1 for i in inst if i['parede'] == w and
                       (abs(i['bb'][0] - cx) < 200 or abs(i['bb'][3] - cx) < 200) and (abs(i['bb'][1] - cy) < 200 or abs(i['bb'][4] - cy) < 200))
        s = min(perto(a), perto(b))
        if s: liga.append((s, a, b))
    liga.sort(reverse=True)
    grupo = {}
    for s, a, b in liga:
        if a in grupo or b in grupo: continue
        grupo[a] = grupo[b] = (a, b)
    vistas = []
    for w in paredes:
        g = grupo.get(w, (w,))
        if g not in vistas: vistas.append(g)
    return vistas

# ================= v2: parede pelo lado das portas =================
def _ov(a0, a1, b0, b1): return max(0.0, min(a1, b1) - max(a0, b0))

def lado_frontal(it, P, ocupadas=()):
    U = it['bb']; dentro_ = set(it['pecas']) | set(ocupadas); area = {'-x': 0, '+x': 0, '-y': 0, '+y': 0}
    for p in P:
        if p['i'] in dentro_: continue
        b = p['bb']; dx, dy, dz = p['dim']
        oz = _ov(b[2], b[5], U[2], U[5])
        if dz <= 0 or oz < 0.5 * dz: continue
        if dx <= 26:
            oy = _ov(b[1], b[4], U[1], U[4])
            if dy > 0 and oy >= 0.5 * dy:
                if abs(b[3] - U[0]) <= 35: area['-x'] += oy * oz
                if abs(b[0] - U[3]) <= 35: area['+x'] += oy * oz
        if dy <= 26:
            ox = _ov(b[0], b[3], U[0], U[3])
            if dx > 0 and ox >= 0.5 * dx:
                if abs(b[4] - U[1]) <= 35: area['-y'] += ox * oz
                if abs(b[1] - U[4]) <= 35: area['+y'] += ox * oz
    lado = max(area, key=area.get)
    return lado if area[lado] > 0 else None

OPOSTO = {'-x': 'x+', '+x': 'x-', '-y': 'y+', '+y': 'y-'}   # frente em -x => olho para +x

def plano(key, bb):
    return {'x+': bb[3], 'x-': bb[0], 'y+': bb[4], 'y-': bb[1]}[key]

def dist_caixas(A, B):
    d = [max(0, max(A[k], B[k]) - min(A[k + 3], B[k + 3])) for k in range(3)]
    return (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5

def _ao_longo(it):
    b = it['bb']; dx, dy = b[3] - b[0], b[4] - b[1]
    if it['tipo'] == 'mod':
        w = it.get('larg') or parse_dim(it['dim'])[0]
        return 'x' if abs(dx - w) <= abs(dy - w) else 'y'
    return 'x' if dx >= dy else 'y'

def _montar(inst):
    paredes = []
    for it in sorted(inst, key=lambda i: i['tipo'] != 'mod'):
        k = it['parede_key']; pl = plano(k, it['bb'])
        alvo = next((w for w in paredes if w['key'] == k and abs(w['plano'] - pl) <= 60), None)
        if alvo is None:
            alvo = {'key': k, 'plano': pl, 'itens': []}; paredes.append(alvo)
        alvo['itens'].append(it)
    for w in paredes:
        w['id'] = f"{w['key']}@{round(w['plano'])}"
        for it in w['itens']: it['parede'] = w['id']
    return paredes

def definir_paredes(inst, P):
    lim = limites(inst)
    mods = [i for i in inst if i['tipo'] == 'mod']
    ocup = set()
    for i in inst: ocup.update(i['pecas'])
    # 1) módulos: lado das portas
    for it in mods:
        lf = lado_frontal(it, P, ocup)
        it['frente'] = lf
        it['parede_key'] = OPOSTO[lf] if lf else parede_de(it, lim, P)
    # 2) módulos: costas encostadas no plano de uma parede já formada, largura ao longo dela
    for _ in range(2):
        paredes = _montar(mods)
        for it in mods:
            eixo = _ao_longo(it)
            keys = ('y-', 'y+') if eixo == 'x' else ('x-', 'x+')
            cand = [w for w in paredes if w['key'] in keys and abs(plano(w['key'], it['bb']) - w['plano']) <= 30]
            if not cand: continue
            atual = next(w for w in paredes if w['id'] == it.get('parede'))
            melhor = max(cand, key=lambda w: len(w['itens']))
            if atual['key'] not in keys or len(melhor['itens']) > len(atual['itens']):
                it['parede_key'] = melhor['key']
    paredes = _montar(mods)
    # 3) componentes: mesma regra; senão herda do módulo mais próximo
    for it in inst:
        if it['tipo'] == 'mod': continue
        eixo = _ao_longo(it)
        keys = ('y-', 'y+') if eixo == 'x' else ('x-', 'x+')
        cand = [w for w in paredes if w['key'] in keys and abs(plano(w['key'], it['bb']) - w['plano']) <= 40]
        if cand:
            it['parede_key'] = max(cand, key=lambda w: len(w['itens']))['key']; continue
        m = min(mods, key=lambda m: dist_caixas(it['bb'], m['bb'])) if mods else None
        if m and dist_caixas(it['bb'], m['bb']) <= 400:
            it['parede_key'] = m['parede_key']; it['_forca'] = m['parede']
        else:
            it['parede_key'] = parede_de(it, lim, P); it['_solto'] = True
    # REGRA (v15): peça solta (tamponamento/painel) que não encosta em parede nem em módulo, mas ENCOSTA (até 60 mm)
    # em outra peça do projeto, vai para a parede dessa peça (ex.: tamponamento de apoio na ponta do painel).
    # Nunca forma uma parede (vista) sozinha.
    for it in inst:
        if not it.get('_solto'): continue
        viz = [o for o in inst if o is not it and not o.get('_solto')]
        o = min(viz, key=lambda o: dist_caixas(it['bb'], o['bb'])) if viz else None
        if o is not None and dist_caixas(it['bb'], o['bb']) <= 60:
            it['parede_key'] = o['parede_key']; it['_junto'] = o
    paredes = _montar([i for i in inst if not i.get('_forca') and not i.get('_junto')])
    for it in inst:
        if it.get('_forca'):
            w = next(w for w in paredes if w['id'] == it['_forca']); w['itens'].append(it); it['parede'] = w['id']
    for it in inst:
        if it.get('_junto'):
            alvo = it['_junto']
            while alvo.get('_junto'): alvo = alvo['_junto']
            w = next(w for w in paredes if w['id'] == alvo['parede']); w['itens'].append(it); it['parede'] = w['id']
    return paredes

def agrupar_vistas2(paredes, raio=650):
    """duas paredes perpendiculares com móveis chegando no mesmo canto formam uma vista (L)."""
    def perto(w, cx, cy):
        return any((abs(i['bb'][0] - cx) < raio or abs(i['bb'][3] - cx) < raio) and
                   (abs(i['bb'][1] - cy) < raio or abs(i['bb'][4] - cy) < raio) for i in w['itens'])
    liga = []
    for a in paredes:
        for b in paredes:
            if a is b or a['key'][0] != 'x' or b['key'][0] != 'y': continue
            cx, cy = a['plano'], b['plano']
            if perto(a, cx, cy) and perto(b, cx, cy):
                liga.append((len(a['itens']) + len(b['itens']), a['id'], b['id']))
    liga.sort(reverse=True); g = {}
    for s, a, b in liga:
        if a in g or b in g: continue
        g[a] = g[b] = (a, b)
    vistas = []
    ordem = sorted(paredes, key=lambda w: -len(w['itens']))
    for w in ordem:
        grupo = g.get(w['id'], (w['id'],))
        if grupo not in vistas: vistas.append(grupo)
    return vistas

