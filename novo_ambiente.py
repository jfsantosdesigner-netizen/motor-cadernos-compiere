# Gera o caderno de um ambiente a partir da pasta (XML montado + DXF; PDF de imagens opcional)
import sys, os, glob, json, re, subprocess
sys.stdout.reconfigure(encoding='utf-8')
M = os.path.dirname(os.path.abspath(__file__))
pasta = os.path.abspath(sys.argv[1].strip('"'))
pad = json.load(open(os.path.join(M, 'padrao.json'), encoding='utf-8'))
xmls = [f for f in glob.glob(os.path.join(pasta, '*.xml')) if not re.search(r'x?plod', os.path.basename(f), re.I)]
mont = [f for f in xmls if 'montado' in f.lower()] or xmls
dxfs = glob.glob(os.path.join(pasta, '*.dxf'))
if not mont or not dxfs: sys.exit('FALTA: coloque na pasta o XML MONTADO e o DXF exportados do Promob.')
cliente = re.sub(r'^PROJETO\s+', '', os.path.basename(os.path.dirname(pasta)), flags=re.I).upper()
amb = re.sub(r'^EXECUTIVO\s*-?\s*', '', os.path.basename(pasta), flags=re.I).strip().title()
dados = {'cliente': cliente, 'ambiente': amb, 'projetista': pad['projetista'], 'arquiteta': pad['arquiteta']}
for extra in (os.path.join(os.path.dirname(pasta), 'dados.json'), os.path.join(pasta, 'dados.json')):
    if os.path.exists(extra): dados.update(json.load(open(extra, encoding='utf-8')))
cfg = {'tipo_caderno': pad['tipo_caderno'], 'dados': dados, 'layout': pad['layout'], 'contrato_fonte': pad['contrato_fonte'],
       'xml': max(mont, key=os.path.getmtime), 'xml_confere': True, 'dxf': max(dxfs, key=os.path.getmtime),
       'pecas_json': os.path.join(pasta, '_pecas_dxf.json'), 'vistas': [], 'logo': pad.get('logo'), 'materiais': pad.get('materiais'),
       'saida': os.path.join(pasta, f'CADERNO - {amb.upper()}.pdf')}
if os.path.exists(cfg['pecas_json']) and os.path.getmtime(cfg['pecas_json']) < os.path.getmtime(cfg['dxf']): os.remove(cfg['pecas_json'])
cj = os.path.join(pasta, '_config.json'); json.dump(cfg, open(cj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('Gerando:', dados['cliente'], '/', amb, '...')
subprocess.run([sys.executable, os.path.join(M, 'gerar_caderno.py'), cj])
for f in glob.glob(os.path.join(os.path.dirname(cfg['saida']), '_prev_*.png')): os.remove(f)
