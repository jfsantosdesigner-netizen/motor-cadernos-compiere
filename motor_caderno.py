# MOTOR DE CADERNO v1 — Compiere (24/09/2026)
# Entrada: XML montado + PDF de imagens do Promob + LAYOUT FIXO. Saída: caderno PDF.
# Uso: python motor_caderno.py config.json
import sys, re, json, xml.etree.ElementTree as ET
from collections import OrderedDict
import pymupdf as fz
sys.stdout.reconfigure(encoding='utf-8')

cfg = json.load(open(sys.argv[1], encoding='utf-8'))
AREA = fz.Rect(19, 142, 823, 577)          # quadro de desenho (medido no caderno aprovado)
RED = (0.545, 0, 0)
ESCALAS = [10, 15, 16, 20, 25, 30, 40, 50, 75, 100]

# ---------------- XML -> listagem ----------------
def fmt(v):
    f = float(v); s = ('%g' % f) if f != int(f) else str(int(f))
    return s.replace('.', ',')

def entra(cat, iid):
    u = (iid or '').upper(); c = (cat or '').upper()
    if any(k in c for k in ('ACESS', 'FERRAG', 'EURONOBRE', 'PUXADOR')): return False
    if '_POR_' in u or u.startswith('ACE') or u.startswith('EUR_') or 'PUX' in u: return False
    return True

def modelo(it):
    refs = it.find('REFERENCES')
    if refs is None: return ''
    for tag in ('MODEL', 'COR', 'MAT'):
        e = refs.find(tag)
        if e is not None and e.get('REFERENCE'): return e.get('REFERENCE')
    return ''

def eh_comp(iid):
    return iid.upper().startswith(('PAI', 'COM_COZ_DIV'))

def ler_xml(path):
    root = ET.parse(path).getroot()
    mods, comps, cores = OrderedDict(), OrderedDict(), OrderedDict()
    for cat in root.iter('CATEGORY'):
        items = cat.find('ITEMS')
        if items is None: continue
        for it in items.findall('ITEM'):
            a = it.attrib; iid = a.get('ID', '')
            m = modelo(it)
            if '_POR_' in iid.upper(): grupo = 'Portas e frentes'
            elif eh_comp(iid): grupo = 'Painéis e tamponamentos'
            else: grupo = 'Módulos (caixa)'
            if m and (entra(cat.get('DESCRIPTION'), iid) or grupo == 'Portas e frentes'):
                cores.setdefault(grupo, OrderedDict())[m] = 1
            if not entra(cat.get('DESCRIPTION'), iid): continue
            desc = re.sub(r'\s+\d+(?:[.,]\d+)?x\d+(?:[.,]\d+)?x\d+(?:[.,]\d+)?mm\s*$', '', a.get('DESCRIPTION', '')).strip()
            dim = f"{fmt(a['WIDTH'])}x{fmt(a['HEIGHT'])}x{fmt(a['DEPTH'])}"
            destino = comps if eh_comp(iid) else mods
            destino.setdefault((desc, dim), 0); destino[(desc, dim)] += 1
    linhas = [(d, dm, q) for (d, dm), q in mods.items()] + [(d, dm, q) for (d, dm), q in comps.items()]
    return linhas, cores

# ---------------- página base (carimbo) ----------------
lay = fz.open(cfg['layout'])
def nova_prancha(doc, n, titulo):
    p = doc.new_page(width=lay[0].rect.width, height=lay[0].rect.height)
    p.show_pdf_page(p.rect, lay, 0)
    p.draw_rect(fz.Rect(300, 117, 540, 141), color=None, fill=(1, 1, 1))   # tira "PRANCHA LIVRE"
    p.draw_rect(fz.Rect(712, 52, 816, 96), color=None, fill=(1, 1, 1))    # refaz PRANCHA nº
    d = cfg['dados']
    for x, y, txt in ((224, 33, d['cliente']), (234, 59, d['ambiente']), (285, 85, d['projetista']), (239, 111, d['arquiteta'])):
        p.insert_text((x, y), txt, fontname='hebo', fontsize=10)
    tw = fz.get_text_length(titulo, 'hebo', 16)
    p.insert_text((419.5 - tw / 2, 135), titulo, fontname='hebo', fontsize=16, color=RED)
    p.insert_text((764 - fz.get_text_length('PRANCHA', 'hebo', 18) / 2, 62), 'PRANCHA', fontname='hebo', fontsize=18)
    num = '%02d' % n
    p.insert_text((764 - fz.get_text_length(num, 'hebo', 18) / 2, 85), num, fontname='hebo', fontsize=18)
    return p

# ---------------- imagens do Promob ----------------
img = fz.open(cfg['imagens'])
def regiao(pno):
    pg = img[pno - 1]
    rs = [fz.Rect(i['bbox']) for i in pg.get_image_info() if i['width'] > 1000]
    r = fz.Rect(rs[0])
    for x in rs[1:]: r |= x
    r = fz.Rect(r.x0 + 3, r.y0 + 3, r.x1 - 3, r.y1 - 3)          # tira a moldura
    pix = pg.get_pixmap(clip=r, dpi=60)                            # corta o branco em volta
    import numpy as np
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]
    m = (a < 235).any(axis=2)
    ys, xs = np.where(m)
    if len(xs):
        k = r.width / pix.w
        r = fz.Rect(r.x0 + xs.min() * k - 2, r.y0 + ys.min() * k - 2, r.x0 + (xs.max() + 1) * k + 2, r.y0 + (ys.max() + 1) * k + 2)
    mt = re.search(r'1:(\d+)', pg.get_text())
    return r, (int(mt.group(1)) if mt else None)

def encaixa(p, pno, alvo):
    r, _ = regiao(pno)
    f = min(alvo.width / r.width, alvo.height / r.height)
    w, h = r.width * f, r.height * f
    x0 = alvo.x0 + (alvo.width - w) / 2; y0 = alvo.y0 + (alvo.height - h) / 2
    t = fz.Rect(x0, y0, x0 + w, y0 + h)
    p.show_pdf_page(t, img, pno - 1, clip=r)
    return t

def grade(n):
    a = AREA
    if n == 1: return [a]
    if n == 2: return [fz.Rect(a.x0, a.y0, a.x0 + a.width / 2, a.y1), fz.Rect(a.x0 + a.width / 2, a.y0, a.x1, a.y1)]
    w, h = a.width / 2, a.height / 2
    return [fz.Rect(a.x0 + (i % 2) * w, a.y0 + (i // 2) * h, a.x0 + (i % 2 + 1) * w, a.y0 + (i // 2 + 1) * h) for i in range(n)]

def ortos(p, pnos, letra):
    regs = [(r, e or 20) for r, e in (regiao(n) for n in pnos)]
    gap = 30
    for S in ESCALAS:                                              # mesma escala padrão para todas as paredes
        fs = [e / S for _, e in regs]
        W = sum(r.width * f for (r, _), f in zip(regs, fs)) + gap * (len(regs) - 1)
        H = max(r.height * f for (r, _), f in zip(regs, fs))
        if W <= AREA.width - 20 and H <= AREA.height - 40: break
    x = AREA.x0 + (AREA.width - W) / 2
    base = AREA.y0 + 15 + H
    for ((r, e), f), pno in zip(zip(regs, fs), pnos):
        w, h = r.width * f, r.height * f
        p.show_pdf_page(fz.Rect(x, base - h, x + w, base), img, pno - 1, clip=r)
        x += w + gap
    lab = f'VISTA {letra} - ESC. 1:{S}'
    p.insert_text((419.5 - fz.get_text_length(lab, 'hebo', 10) / 2, base + 20), lab, fontname='hebo', fontsize=10)

# ---------------- tabela de listagem ----------------
def tabela(p, linhas, rect):
    n = len(linhas); fs = 8.3; lh = 11.8
    while n * lh + 18 > rect.height and fs > 5.5:
        fs -= 0.3; lh = fs * 1.42
    p.draw_rect(rect, color=(0, 0, 0), fill=(1, 1, 1), width=0.6)
    y = rect.y0 + 11
    p.insert_text((rect.x0 + 4, y), 'Nº', fontname='hebo', fontsize=7.5, color=RED)
    p.insert_text((rect.x0 + 24, y), 'DESCRIÇÃO', fontname='hebo', fontsize=7.5, color=RED)
    p.insert_text((rect.x1 - 74, y), 'DIMENSÃO (LxAxP)', fontname='hebo', fontsize=7.5, color=RED)
    p.draw_line((rect.x0, y + 3), (rect.x1, y + 3), width=0.5)
    y += 3
    for i, (d, dm, q) in enumerate(linhas, 1):
        y += lh
        dtxt = d if q == 1 else f'{d} ({q} un)'
        while fz.get_text_length(dtxt, 'helv', fs) > rect.width - 104: dtxt = dtxt[:-2]
        p.insert_text((rect.x0 + 4, y), str(i), fontname='hebo', fontsize=fs)
        p.insert_text((rect.x0 + 24, y), dtxt, fontname='helv', fontsize=fs)
        p.insert_text((rect.x1 - 4 - fz.get_text_length(dm, 'helv', fs), y), dm, fontname='helv', fontsize=fs)
def listagem_de_pdf(path, pno):
    # fallback: lê Descrição/Dimensão de uma prancha de listagem aprovada (usado quando o XML não confere)
    pg = fz.open(path)[pno - 1]
    spans = [s for b in pg.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']
             if s['bbox'][0] < 260 and 145 < s['bbox'][1] < 575 and s['text'].strip()]
    rows = {}
    for s in spans: rows.setdefault(round(s['bbox'][1]), []).append(s)
    out = []
    for y in sorted(rows):
        t = sorted(rows[y], key=lambda s: s['bbox'][0])
        if len(t) >= 2 and 'x' in t[-1]['text']: out.append(([s['text'].strip() for s in t if not s['text'].strip().isdigit()][0], t[-1]['text'].strip(), 1))
    return out

linhas, cores = ler_xml(cfg['xml'])
if cfg.get('listagem_pdf'):
    cores = OrderedDict([('ATENÇÃO - v1', OrderedDict([('XML da pasta COZINHA é de outra versão', 1),
                                                     ('(cores Mogno/Chumbo/Nero não conferem)', 1),
                                                     ('Exportar XML do projeto atual', 1)]))])
doc = fz.open(); n = 0
V = cfg['vistas']

n += 1; p = nova_prancha(doc, n, 'CAPA')
encaixa(p, cfg['capa_img'], fz.Rect(AREA.x0 + 10, AREA.y0 + 40, AREA.x1 - 10, AREA.y1 - 10))
t = f"CADERNO DE {cfg['tipo_caderno']} — {cfg['dados']['ambiente'].upper()}"
p.insert_text((419.5 - fz.get_text_length(t, 'hebo', 18) / 2, AREA.y0 + 28), t, fontname='hebo', fontsize=18, color=RED)

n += 1; p = nova_prancha(doc, n, 'CONTRATO')
contrato = fz.open(cfg['contrato_fonte'])
clip = fz.Rect(AREA.x0, 143, AREA.x1, 540)
p.show_pdf_page(clip, contrato, 0, clip=clip)

n += 1; p = nova_prancha(doc, n, 'PLANTA - ESPECIFICAÇÕES DO PROJETO')
esp = fz.Rect(AREA.x0 + 5, AREA.y0 + 5, AREA.x0 + 235, AREA.y1 - 5)
p.draw_rect(esp, color=(0, 0, 0), width=0.6)
y = esp.y0 + 14
p.insert_text((esp.x0 + 6, y), 'CORES E ACABAMENTOS', fontname='hebo', fontsize=9, color=RED)
for g, ms in cores.items():
    y += 16; p.insert_text((esp.x0 + 6, y), g + ':', fontname='hebo', fontsize=8)
    for m in list(ms)[:8]:
        y += 11; p.insert_text((esp.x0 + 12, y), '- ' + m, fontname='helv', fontsize=8)
t = encaixa(p, cfg['planta_img'], fz.Rect(esp.x1 + 10, AREA.y0 + 5, AREA.x1 - 5, AREA.y1 - 20))
lab = 'PLANTA BAIXA — VISTAS: ' + ', '.join(v['letra'] for v in V)
p.insert_text((t.x0 + t.width / 2 - fz.get_text_length(lab, 'hebo', 9) / 2, t.y1 + 13), lab, fontname='hebo', fontsize=9)

n += 1; p = nova_prancha(doc, n, 'VISÃO GERAL DOS MÓVEIS')
for v, cel in zip(V, grade(len(V))):
    c = fz.Rect(cel.x0 + 6, cel.y0 + 18, cel.x1 - 6, cel.y1 - 6)
    encaixa(p, v['img3d'], c)
    p.insert_text((cel.x0 + 10, cel.y0 + 13), f"VISTA {v['letra']}", fontname='hebo', fontsize=10, color=RED)

for v in V:
    n += 1; p = nova_prancha(doc, n, f"MÓDULOS E PAINÉIS - VISTA {v['letra']}")
    encaixa(p, v['img3d'], fz.Rect(AREA.x0 + 260, AREA.y0 + 4, AREA.x1 - 4, AREA.y1 - 4))
    if cfg.get('listagem_pdf'): lin = listagem_de_pdf(cfg['listagem_pdf'], v['listagem_pag'])
    else: lin = linhas
    print(f'VISTA {v["letra"]}: {len(lin)} linhas')
    for l in lin: print('   ', l)
    tabela(p, lin, fz.Rect(AREA.x0 + 4, AREA.y0 + 4, AREA.x0 + 252, AREA.y1 - 4))
    n += 1; p = nova_prancha(doc, n, f"MEDIDAS E ALTURAS - VISTA {v['letra']}")
    ortos(p, v['orto'], v['letra'])

doc.save(cfg['saida'], garbage=3, deflate=True)
print(f'OK {cfg["saida"]} | pranchas={n} (regra 4+2x{len(V)}={4 + 2 * len(V)})')
