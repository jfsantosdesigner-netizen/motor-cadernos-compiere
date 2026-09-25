# Gera uma página HTML com as pranchas dos cadernos em imagem (para ver dentro do Claude, sem baixar PDF).
# Uso: python ferramentas/visualizador.py saida.html "Nome|caminho.pdf" ["Nome|caminho.pdf" ...]
import sys, base64, html, pymupdf as fz
out, cads = sys.argv[1], [a.split('|', 1) for a in sys.argv[2:]]
tabs, secs = [], []
for k, (nome, pdf) in enumerate(cads):
    d = fz.open(pdf); cid = f'c{k}'
    tabs.append(f'<button class="tab" data-alvo="{cid}" aria-selected="{str(k == 0).lower()}">{html.escape(nome)}<span>{len(d)} pranchas</span></button>')
    figs = []
    for i, p in enumerate(d):
        b = base64.b64encode(p.get_pixmap(dpi=115).tobytes('jpeg', jpg_quality=78)).decode()
        figs.append(f'<figure id="{cid}-{i + 1}"><figcaption>Prancha {i + 1:02d}</figcaption><img loading="lazy" alt="{html.escape(nome)} prancha {i + 1}" src="data:image/jpeg;base64,{b}"></figure>')
    nav = ''.join(f'<a href="#{cid}-{i + 1}">{i + 1:02d}</a>' for i in range(len(d)))
    secs.append(f'<section id="{cid}" {"" if k == 0 else "hidden"}><nav class="pags" aria-label="Pranchas">{nav}</nav>{"".join(figs)}</section>')
open(out, 'w', encoding='utf-8').write(f'''<title>Cadernos Compiere</title>
<style>
:root {{ --fundo:#eef0f2; --papel:#ffffff; --tinta:#1d2429; --sutil:#5d6873; --linha:#cfd5db; --acento:#8b1a1a; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --fundo:#15191c; --papel:#20262b; --tinta:#e6eaee; --sutil:#9aa6b0; --linha:#343c43; --acento:#e07a6f; color-scheme:dark; }} }}
:root[data-theme="dark"] {{ --fundo:#15191c; --papel:#20262b; --tinta:#e6eaee; --sutil:#9aa6b0; --linha:#343c43; --acento:#e07a6f; color-scheme:dark; }}
body {{ background:var(--fundo); color:var(--tinta); font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; padding-inline:16px; padding-block:16px 40px; }}
.wrap {{ max-width:1100px; margin:0 auto; display:flex; flex-direction:column; gap:14px; }}
h1 {{ font-size:18px; margin:0; letter-spacing:.02em; }} h1 b {{ color:var(--acento); }}
.tabs {{ display:flex; flex-wrap:wrap; gap:8px; }}
.tab {{ font:inherit; font-weight:600; color:var(--tinta); background:var(--papel); border:1px solid var(--linha); border-radius:6px; padding:8px 12px; cursor:pointer; display:flex; gap:8px; align-items:baseline; }}
.tab span {{ font-weight:400; color:var(--sutil); font-size:12px; }}
.tab[aria-selected="true"] {{ border-color:var(--acento); box-shadow:inset 0 -2px 0 var(--acento); }}
.tab:focus-visible, .pags a:focus-visible {{ outline:2px solid var(--acento); outline-offset:2px; }}
section {{ display:flex; flex-direction:column; gap:18px; }}
.pags {{ position:sticky; top:env(safe-area-inset-top,0px); z-index:2; display:flex; flex-wrap:wrap; gap:4px; background:var(--fundo); padding-block:6px; }}
.pags a {{ font-variant-numeric:tabular-nums; font-size:12px; color:var(--tinta); text-decoration:none; border:1px solid var(--linha); background:var(--papel); border-radius:4px; padding:3px 7px; }}
figure {{ margin:0; display:flex; flex-direction:column; gap:6px; scroll-margin-top:48px; }}
figcaption {{ font-size:12px; color:var(--sutil); text-transform:uppercase; letter-spacing:.08em; }}
figure img {{ width:100%; height:auto; background:#fff; border:1px solid var(--linha); border-radius:3px; }}
</style>
<div class="wrap">
<h1>Cadernos <b>Compiere</b> · motor v26</h1>
<div class="tabs" role="tablist">{"".join(tabs)}</div>
{"".join(secs)}
</div>
<script>
document.querySelectorAll('.tab').forEach(function(t){{t.addEventListener('click',function(){{
 document.querySelectorAll('.tab').forEach(function(o){{o.setAttribute('aria-selected',String(o===t));}});
 document.querySelectorAll('section').forEach(function(s){{s.hidden=s.id!==t.dataset.alvo;}});
}});}});
</script>
''')
print('ok', out)
