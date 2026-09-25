# Motor de Cadernos Compiere

Gera o caderno PDF (Capa, Contrato, Planta+Especificações, Visão Geral, Listagem e Cotas por vista) a partir do **XML montado + DXF** exportados do Promob.

- Versão atual: ver `VERSAO.txt`. No PC fica em `C:\CLAUDE\motor vN` (o nome da pasta é a versão).
- Uso: arrastar a pasta do ambiente (ex.: `PROJETO FULANO\COZINHA`, com XML + DXF) no `GERAR_CADERNO.bat`.
- Cores reais: `materiais_cores.json` traz a cor média de cada textura da pasta `C:\CLAUDE\MATERIAIS` (3 GB, fora do repositório). Com essa tabela o motor pinta as peças sem precisar da pasta. Se ela existir, texturas sem cor na tabela são lidas direto dela.
- Configuração: `padrao.json` (projetista, arquiteta, layout, contrato, logo, pasta de materiais).
