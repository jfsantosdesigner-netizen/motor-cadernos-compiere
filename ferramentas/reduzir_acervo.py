# Reduz os acervos grandes para dentro do motor (roda no PC do João).
#   python ferramentas/reduzir_acervo.py materiais   -> C:\CLAUDE\MATERIAIS  => <motor>\MATERIAIS          (texturas em 512 px)
#   python ferramentas/reduzir_acervo.py promob      -> bibliotecas do Promob => <motor>\BIBLIOTECA_PROMOB (imagens 256 px + .obj/.mtl + indice.json)
# Mesmos nomes e pastas da origem (o motor acha a textura pelo mesmo caminho). Pode rodar de novo: pula o que já existe.
import os, sys, json, shutil
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

MOTOR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}

def reduzir(orig, dest, maxpx, copiar=(), indice=None):
    n = pul = err = 0; itens = []
    for d, _, fs in os.walk(orig):
        for f in fs:
            e = os.path.splitext(f)[1].lower(); sp = os.path.join(d, f); rel = os.path.relpath(sp, orig); dp = os.path.join(dest, rel)
            if indice is not None and e in ('.entity', '.pmob', '.mob3d', '.obj', '.jpg', '.jpeg', '.png'):
                itens.append(dict(lib=rel.split(os.sep)[0], nome=os.path.splitext(f)[0], tipo=e[1:], caminho=rel,
                                  puxador='pux' in rel.lower(), ferragem=any(k in rel.lower() for k in ('ferrag', 'dobradi', 'corredi', 'acessor'))))
            if e in IMG:
                if os.path.exists(dp): pul += 1; continue
                try:
                    im = Image.open(sp); im = im.convert('RGB'); im.thumbnail((maxpx, maxpx))
                    os.makedirs(os.path.dirname(dp), exist_ok=True); im.save(dp, 'JPEG', quality=80, optimize=True); n += 1
                except Exception:
                    err += 1
            elif e in copiar:
                if os.path.exists(dp): pul += 1; continue
                os.makedirs(os.path.dirname(dp), exist_ok=True); shutil.copy2(sp, dp); n += 1
            if (n + pul) % 500 == 0 and n: print('...', n, 'feitos', flush=True)
    if indice is not None:
        json.dump(itens, open(os.path.join(dest, indice), 'w', encoding='utf-8'), ensure_ascii=False)
    tam = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(dest) for f in fs)
    print(f'FIM {dest}: {n} novos, {pul} já existiam, {err} com erro, total {tam / 1e6:.0f} MB', flush=True)

if __name__ == '__main__':
    qual = sys.argv[1] if len(sys.argv) > 1 else 'materiais'
    if qual == 'materiais':
        reduzir(r'C:\CLAUDE\MATERIAIS', os.path.join(MOTOR, 'MATERIAIS'), 512)
    elif qual == 'promob':
        reduzir(r'C:\Program Files\Promob\Promob Plus\System\bibliotecas', os.path.join(MOTOR, 'BIBLIOTECA_PROMOB'), 256,
                copiar=('.obj', '.mtl'), indice='indice.json')
