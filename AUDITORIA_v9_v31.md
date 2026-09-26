# AUDITORIA DO MOTOR — v9 a v31

Revisão do repositório `motor-cadernos-compiere` (55 commits, v7..v31), feita a pedido do
João depois da sessão de 25–26/09 em que as correções relatadas não bateram com o caderno gerado.

Método: leitura integral de `gerar_caderno.py` (2.346 linhas), análise de alcançabilidade de
todas as funções, `git show` de cada commit de versão, e leitura dos PDFs já gerados em
`exemplos/`. **Não foi possível executar o motor** — ver "Bloqueio" no fim.

---

## 1. Veredito sobre "ele mentiu"

Sendo exato, porque isso importa:

**Não houve commit inventado.** Todas as versões v9..v31 alteraram de fato o
`gerar_caderno.py`, e os 12 cadernos de exemplo foram regerados a cada versão. Nesse ponto os
relatórios batem com o repositório.

**Mas três coisas fazem o relatório dizer mais do que o código entrega**, e as três são reais:

1. Correções escritas em **cópias de funções que o Python nunca executa**.
2. Comentários e `VERSAO.txt` que **contradizem o número que está no código**.
3. O relatório de qualidade que **imprime uma conta que não fecha** e mesmo assim diz APROVADO.

Cada uma está documentada abaixo, com linha e forma de conferir.

---

## 2. Achados, do mais grave para o menos

### 2.1 Três funções existiam em 2 ou 3 versões no mesmo arquivo — GRAVE

| função | definida nas linhas | qual valia | qual era código morto |
|---|---|---|---|
| `geom_parede` | 625, 1064, **1251** | a de 1251 | 625 e 1064 (37 linhas) |
| `desenhar` | 643, **1088** | a de 1088 | 643 (22 linhas) |
| `render3d` | 1096, **1655** | a de 1655 | 1096 (102 linhas) |

Em Python, quando um nome é redefinido, só a **última** definição antes da chamada existe. As
chamadas todas acontecem na montagem das pranchas (linha 1861 em diante), ou seja, depois de
todas as definições. **Qualquer regra escrita nas cópias de cima não chegava ao PDF** — o
relatório podia dizer com sinceridade "alterei `geom_parede`" e o caderno sair idêntico.

Esse é o mecanismo exato que produz a sensação de ter sido enganado.

Nenhuma regra se perdeu: conferi as três cópias e a que valia é sempre a mais completa (superconjunto
das outras). As mortas eram estágios antigos que ninguém apagou.

### 2.2 O código diz 5%, o comentário e o VERSAO.txt dizem 15% — GRAVE

`gerar_caderno.py`, na regra de visibilidade usada pela lateral da divisória ripada:

```python
if c_ >= 40 and c_ / area_ >= 0.05: kw['visiveis'].add(...)   # peça aparece DE VERDADE (15%+ dela)
```

O `VERSAO.txt` da v25 diz "peça com 15%+ da área à vista". O comentário na própria linha diz
15%. **O código testa 5%** — três vezes mais permissivo. A v28 baixou o valor para 5% ("as ripas
centrais, 5% à vista") e deixou o comentário e o VERSAO.txt da v25 como estavam. Quem lê a
documentação entende uma coisa; a listagem da prancha lateral sai por outra.

### 2.3 "Porta/frente" tem QUATRO definições diferentes — GRAVE

A mesma pergunta física ("esta chapa é uma porta?") é respondida por quatro trechos com
faixas diferentes:

| função | o que decide | faixa em relação à frente do módulo | altura mínima |
|---|---|---|---|
| `_portas_cota` (v31) | some no desenho de cotas | `fr-150` a `fr+80` | 60 mm |
| `_portas()` | some no 3D quando `sem_portas` | `fr-40` a `fr+5` | 100 mm |
| `tem_porta()` | módulo "tem porta" (nicho, módulo pequeno) | `fr-40` a `fr+25`, cobrindo ≥40% | 100 mm |
| `_gerar_puxadores` | onde colocar o puxador | `fr-40` a `fr+5` | 100 mm |

Consequência prática: a mesma chapa pode ser porta na prancha de cotas e **não** ser porta na
prancha de listagem — e um armário pode ser tratado como nicho numa regra e como armário fechado
em outra. Isso não é bug de uma versão: é acúmulo de v7, v14, v23 e v31 cada uma escrevendo a
sua definição.

### 2.4 O relatório de qualidade imprime uma conta que não fecha — MÉDIO

Na Suíte do Guilherme o relatório diz:

> `APROVADO | nº de pranchas 10 = 4 + 2 listagens + 2 cotas`

4 + 2 + 2 = 8, não 10. O veredito APROVADO está **certo** (a conta interna, `esperado`, inclui
as pranchas replicadas de detalhe e os blocos de painéis), mas **a justificativa impressa omite
esses termos**. Um relatório que mostra uma conta errada ao lado de um APROVADO é exatamente o
que destrói a confiança no relatório inteiro.

### 2.5 Contradições deixadas no VERSAO.txt — MÉDIO

- **v28 x v29 (peça atrás de painel).** A v28 diz: `detalhe "costas atrás de painel" (v21)
  substituído pela regra geral de peça escondida (v27)`. A v29 diz: `VOLTA a regra da v21`.
  As duas linhas continuam no arquivo, sem marcação de qual venceu. Vale a v29.
- **v23 x v28 (planta).** A v23 diz: `UMA cota por parede = COMPRIMENTO TOTAL dos móveis`.
  A v28 diz: `cota de CADA CONJUNTO de móveis`. Vale a v28.

Quem abrir o VERSAO.txt para saber a regra atual encontra duas respostas.

### 2.6 Funcionalidades "removidas" que continuavam no arquivo — MÉDIO

- A v26 tirou a vista lateral da prancha de cotas escrevendo `LT = None` numa linha, e deixou
  as 50 linhas de `geom_lateral` / `desenhar_lateral` / `cotar_lateral` e o bloco `if LT:` no
  arquivo, abaixo de um comentário que ainda anunciava a regra da v16.
- A v27 disse `removido o modo antigo que puxava listagem/imagens de PDF`. Na prática só
  neutralizou o config (`cfg.pop`) na linha 12; `regiao`, `encaixa`, o import de `motor_lista`
  e os ramos `capa_img`/`img3d` continuavam todos lá.

### 2.7 Defeitos visíveis nos cadernos já gerados — a confirmar rodando

Vistos por leitura do PDF, ainda **não corrigidos**:

- **Suíte do Guilherme, prancha 10 (cotas da vista B):** a cadeia de cotas internas do módulo de
  390 mm sai com os números sobrepostos e ilegíveis. `cadeia_v` desenha cada vão no mesmo `x`
  (centro do vão) e `_uniq` separa por 2 mm — em escala 1:25 dois valores a 2 mm viram um borrão.
- **Mesma prancha:** só um módulo aparece com textura de madeira; o resto sai branco. Pode ser
  correto (interior branco de verdade) ou pode ser falha de casamento de cor. **Só rodando dá
  para afirmar** — e o relatório diz `APROVADO | texturas dos materiais` nos dois casos.
- O motor grava um `_prev_N.png` por página ao lado do PDF (linha 2015). Está no `.gitignore`,
  mas suja a pasta do cliente no PC.

---

## 3. Regra a regra, v9 a v31

Legenda: **OK** = implementada e alcançável · **SUP** = superada por versão posterior ·
**DIV** = implementada, mas diverge do que o VERSAO.txt descreve · **?** = só confirmável rodando.

| ver | regra | status |
|---|---|---|
| v9 | pasta renomeada + caminhos | OK |
| v10 | 3D e 2D só com MDF; 3D por peça | OK |
| v10 | cor casada pela ordem XML x DXF | OK (`_fixa`) |
| v10 | cotas internas: largura do vão + altura entre prateleiras | OK — ver 2.7 (legibilidade) |
| v10 | prancha 03 no modelo do João | OK (`_espec`) |
| v10 | uma letra por parede; parede < 2,5 m junto da vizinha do L | OK (`PAREDE_PEQ`) |
| v10 | cores reais pela `materiais_cores.json` | OK |
| v11 | planta só com móveis e paredes; setas sem sobrepor | OK |
| v11 | todo nicho aberto vira detalhe | OK (`nichos`) |
| v11 | nicho suspenso vira detalhe | **SUP** pela v14 (some quando tem porta) |
| v11 | detalhe das costas | OK (`costas`) |
| v11 | balões nunca sobrepostos | OK (`_bal`) |
| v11 | textura real da madeira no 3D | OK |
| v12 | sem riscos diagonais da triangulação | OK (`_arestas`, teste `reta`) |
| v13 | paredes em peça única pelas faces | OK (`MALHA_PAR`) |
| v13 | parede na frente do fundo dos móveis não entra | OK |
| v13 | ilha/bancada baixa sem parede inventada | OK |
| v14 | nicho = estrutura aberta, sem porta | OK — mas ver 2.3 |
| v15 | cotas parede a parede e piso ao teto | OK (`_vista_limites`) |
| v15 | 3D preenche o quadro | OK |
| v15 | peça solta junta à parede vizinha | OK |
| v15 | cor com nome aproximado | OK (`_parecido`) |
| v16 | cota frontal + vista lateral na mesma prancha | **SUP** pela v26 — código removido na v32 |
| v17 | cores e texturas reais nas cotas 2D | OK (`_desenho2d`) — ver 2.7 |
| v18 | divisória ripada vira bloco próprio | OK (`DIVISORIAS`) |
| v18 | divisor de gaveta ganha prancha própria | OK (`DIVISORES`) |
| v19 | divisória em 2 pranchas diagonais | **SUP** pela v24 (2ª virou lateral reta) |
| v19 | cota de todos os vãos entre ripas | OK (`cotar_divisoria`) |
| v20 | gaveta montada com painéis em prancha própria | OK (`GAVETAS`) |
| v20 | pranchas de peça: 3D isolado + vista de cima | OK (`_prancha_peca`) |
| v21 | listagem poluída (12+ peças) | OK (`poluida`) |
| v21 | módulo pequeno solto vira detalhe | OK (`pequenos`) |
| v21 | peça atrás de painel vira detalhe das costas | OK (`costas_paineis`) — desligada na v28, religada na v29 |
| v22 | perna do L com vista própria | OK |
| v22 | rodapé/base escondida em detalhe | OK (`rodapes`) |
| v23 | planta: UMA cota por parede | **SUP** pela v28 (por conjunto) |
| v23 | MATERIAIS dentro do motor | OK |
| v23 | puxador por regra desligado | OK (`puxadores_regra`) |
| v24 | 2ª imagem da divisória = lateral reta 90° | OK |
| v25 | lateral lista só as peças visíveis (15%) | **DIV** — o código usa 5%, ver 2.2 |
| v26 | parede cortada por pilar/vão | OK (`_cortadas`) |
| v26 | conjunto de painéis sem módulo | OK (`BLOCOS`) |
| v26 | painel usinado | OK (`USINADOS`) |
| v26 | divisor de talher | OK |
| v26 | porta avulsa POR_ fora da listagem | OK |
| v26 | peça duplicada no DXF não é desenhada | OK (`DUP_I`) |
| v26 | cunha sai da listagem | OK |
| v26 | listagem poluída (>15 linhas) = duas pranchas | OK (`_partes`) |
| v26 | cota é só a vista frontal | OK |
| v27 | tudo que está na lista aparece nítido | OK (`_esc`/`_amt`) |
| v27 | uma sub-imagem por prancha | OK |
| v27 | cache do DXF por hash | OK |
| v27 | removido o modo PDF | **DIV** — só o config foi neutralizado; código removido agora na v32 |
| v28 | sub-imagem por altura / sem portas / só módulos | OK |
| v28 | amontoado mais rígido (16 pt) | OK |
| v28 | um detalhe por prancha | OK (`_det_extra`) |
| v28 | costas atrás de painel substituído pela regra geral | **SUP** pela v29 (voltou) |
| v28 | geometria encostada = referência | OK |
| v28 | planta: cota de cada conjunto | OK |
| v28 | visão geral: >4 vistas = diagonal a cada 2 | OK |
| v29 | peça com medida+cor do XML nunca é geometria | OK (`not p_.get('mat')`) |
| v29 | volta o detalhe das costas | OK |
| v30 | frente avulsa POR_ desenhada no móvel | OK |
| v30 | planta não invade o cabeçalho | OK (`_clip`) |
| v31 | cotas com portas abertas | OK (`_portas_cota`) — ver 2.3 |
| v31 | nicho precisa de frente aberta (<40%) | OK |
| v31 | ilha baixa sem parede atrás: cota até +300 mm | OK |
| v31 | 12 projetos regerados | OK — os 12 PDFs mudaram no commit |

---

## 4. O que já foi feito

Ramo **`v32-limpeza`**, commit `eba7a4f`: **−330 linhas**, nenhuma mudança de comportamento.

Só saiu código que o Python comprovadamente nunca executa: as cópias sombreadas de
`geom_parede`/`desenhar`/`render3d`, a vista lateral desligada na v26, o modo "imagens de PDF"
que a v27 disse ter removido, `_render3d_old0`, `_pega` e o `motor_lista.py` órfão.

Conferido: o arquivo compila, não há nome indefinido, não sobrou referência a nada removido e
não existe mais nenhuma função definida duas vezes.

---

## 5. O que falta

1. **Unificar a definição de porta/frente** numa função só (2.3). É a correção de maior efeito.
2. **Acertar 5% x 15%** — decidir o número e alinhar código, comentário e VERSAO.txt (2.2).
3. **Corrigir a conta impressa no relatório de qualidade** (2.4).
4. **Reescrever o VERSAO.txt** marcando o que foi superado (2.5).
5. **Cotas internas legíveis** (2.7).
6. Comparar os cadernos com os feitos à mão pelo João — critério final combinado.

Os itens 1, 2, 3 e 5 **mudam o PDF**. Nenhum deles deve ser commitado sem rodar os 12 projetos
e comparar antes/depois. Foi a ausência desse passo que produziu o problema de ontem.

## Bloqueio

O motor depende do **PyMuPDF**. Nesta sessão em nuvem o PyPI e o repositório do Ubuntu estão
bloqueados pela política de rede da organização (HTTP 403), e não há PyMuPDF instalado. O PC do
João não estava conectado no momento da auditoria. Também não foi possível dar `push`: o
repositório não está na lista de origens autorizadas desta sessão — o commit está local.

Portanto: **tudo neste relatório vem de leitura de código, de histórico do git e dos PDFs já
gerados. Nada aqui foi confirmado rodando o motor.** Onde a leitura não basta, está marcado com
"?" ou "só rodando dá para afirmar".

---

## 6. Verificação da v32 — feita rodando, no PC do João (26/09)

O bloqueio da nuvem foi contornado rodando no próprio PC (Python 3.12.10, PyMuPDF 1.28.2).

**Protocolo.** Os 12 projetos foram regerados com a v32 (limpa) e cada prancha comparada pixel a
pixel (70 dpi) com o PDF da v31 guardado no commit `a2db420`. Em seguida o mesmo foi repetido com
o `gerar_caderno.py` **original da v31**, restaurado do git, como grupo de controle.

**Resultado: os dois relatórios saíram idênticos, linha por linha.** `Compare-Object` entre os
dois logs não acusou uma única diferença. Ou seja: onde a v32 diverge do PDF commitado, a v31
original diverge exatamente igual, nos mesmos projetos, nas mesmas pranchas, na mesma contagem
de pixels.

**Conclusão: a limpeza da v32 não alterou nenhum caderno.** Isso está medido, não argumentado.

### Achado colateral: os PDFs commitados não reproduzem no PC

7 dos 12 projetos saem idênticos ao commit. Os outros 5 divergem **mesmo com o código da v31
intocado**:

| projeto | pranchas que divergem |
|---|---|
| COZINHA2 | p4 (825 px), p9 (1815 px) |
| COZINHA2_v2 | p4 (828 px), p9 (1822 px) |
| ESCRITORIO | p4 (1959 px), p5 e p6 (1791 px) |
| PRISCILA_COZINHA | p4 (198 px), p9 e p10 (451 px) |
| SUITE_CASAL | p4 (1056 px), p5 a p7 (1995 px) |

**Causa: a pasta `texturas/` é ENTRADA do motor, não cache.** (Correção: uma versão anterior
deste relatório dizia que o motor era determinístico. Estava errado — o teste que sustentava
aquilo rodava o projeto duas vezes seguidas, as duas com o cache já quente, e por construção não
conseguia detectar dependência de cache.)

Medição correta, na COZINHA2:

| teste | resultado |
|---|---|
| duas rodadas com `texturas/` intacta | idêntico |
| rodada fria (`texturas/` apagada) x rodada quente | **10 das 15 pranchas mudam** |
| apagar só o `cores_cache.json` | idêntico — não é ele |

O mecanismo está no `textura()`: quando o arquivo não está em `texturas/`, o motor lê o material
da pasta MATERIAIS, reduz com `thumbnail((1024, 1024))` e salva em JPEG qualidade 82. Esse
arquivo regerado **não reproduz** o que está commitado — depois de apagar a pasta e rodar, o git
acusa `M` (modificado) em `branco.jpg`, `freijo_puro.jpg` e `pecan.jpg`. Bytes diferentes da
mesma origem, por diferença de versão do Pillow / reamostragem / encoder JPEG.

E há um agravante: o motor só regera a textura dos materiais **daquele projeto**. Das 12 texturas,
a rodada da COZINHA2 recriou 3 e deixou 9 faltando. Ou seja, **o conteúdo da pasta `texturas/` do
repositório é subproduto de quem rodou o quê e em que ordem** — e realimenta todos os cadernos
seguintes.

É isso que explica os 5 projetos divergentes: na nuvem não existe a pasta MATERIAIS (3 GB, fora
do repositório), então material sem textura commitada sai em cor lisa; no PC, com MATERIAIS
presente, a textura é gerada e o desenho muda.

**Consequências práticas:**

1. "Regerado e commitado" não garante nada sozinho: o resultado depende do estado da pasta
   `texturas/` na máquina de quem rodou.
2. Comparar PDF gerado numa máquina com PDF commitado de outra não serve de critério de
   aprovação. Só vale comparar dois PDFs gerados na mesma máquina, com a mesma `texturas/`.
3. A verificação da v32 na seção acima continua válida justamente por isso: os dois braços
   (v32 e v31 de controle) rodaram com a `texturas/` commitada intacta nos dois casos —
   conferido por `git status texturas` antes e depois.
4. Enquanto `texturas/` for regerável e versionada ao mesmo tempo, esse ruído volta. Ou ela
   passa a ser tratada como artefato fixo (nunca regerada se já existe — é o comportamento
   atual, mas sem garantia de estar completa), ou o motor passa a gerar a chapa sempre a partir
   do MATERIAIS, de forma reprodutível.

