import pymupdf as fz

def listagem_de_pdf(path, pno):
    # lê Descrição/Dimensão de uma prancha de listagem já aprovada
    pg = fz.open(path)[pno - 1]
    spans = [s for b in pg.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']
             if s['bbox'][0] < 260 and 145 < s['bbox'][1] < 575 and s['text'].strip()]
    rows = {}
    for s in spans: rows.setdefault(round(s['bbox'][1]), []).append(s)
    out = []
    for y in sorted(rows):
        t = sorted(rows[y], key=lambda s: s['bbox'][0])
        if len(t) >= 2 and 'x' in t[-1]['text']:
            out.append(([s['text'].strip() for s in t if not s['text'].strip().isdigit()][0], t[-1]['text'].strip(), 1))
    return out
