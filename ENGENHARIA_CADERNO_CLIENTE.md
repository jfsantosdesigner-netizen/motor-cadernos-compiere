# ENGENHARIA DO CADERNO CLIENTE

Levantamento feito a partir dos cadernos reais da **NADECOR** (Drive `jfsantos.designer@gmail.com`,
pasta `NADECOR`), para determinar a lógica do Caderno Cliente antes de mexer no motor.

## 1. O acervo

A NADECOR organiza por **vendedor → cliente → tipo de caderno**. Os três tipos que o João
descreveu existem como pastas, não como ideia:

```
NADECOR/
  CAROLINA/        Alexandre e Katia/   CADERNOS/CADERNO CLIENTE/   (5 cadernos)
                                        CADERNOS/CADERNOS/          (6 cadernos)
                   Edson e Andressa/    CADERNO CLIENTE/            (8 cadernos)
                                        CADERNO EXECUTIVO/
  YONE/            JULIANA SILVA/       CADERNO CLIENTE/            (3 cadernos)
                                        CADERNO INSTALAÇÃO/
                                        CADERNO PRODUÇÃO/
  NATHALIA/        WILLIAM FONSECA/     CADERNOS/CADERNO CLIENTE/   (6 cadernos)
                                        CADERNOS/CADERNO INSTALAÇÃO/
                                        CADERNOS/CADERNO PRODUÇÃO/
  LUANY E NATANAEL/Daniel Furtado/      CADERNO CLIENTE/            (1 caderno)
                                        CADERNO INSTALAÇÃO/
                                        CADERNO PRODUÇÃO/
  PRATIKA 280/     ALEXANDRE GIARDINO/, NADECOR_COZINHA/
```

**29 Caderno Cliente** localizados. Este documento foi escrito lendo **5** deles, escolhidos para
cobrir 4 clientes e os extremos de tamanho (1 vista até 4 vistas):

| caderno | cliente | vistas | pranchas |
|---|---|---:|---:|
| BANHO SUÍTE | Willian Fonseca | 1 | 4 |
| ÁREA DE SERVIÇO | Edson Souza | 1 | 4 |
| COZINHA | Willian Fonseca | 2 | 6 |
| COZINHA | Alexandre Giardino | 2 | 5 |
| COZINHA | Edson Souza | 4 | 8 |
| SUÍTE CASAL | Juliana Silva | 4 | 9 |

## 2. A gramática

O Caderno Cliente é montado com **duas pranchas fixas + duas por vista**:

```
1.  CAPA                                  (cliente + ambiente)
2.  PLANTA COM VISTAS E ESPECIFICAÇÕES    (uma só, sempre)
    por vista:
      VISÃO GERAL DOS MÓVEIS              (3D)
      VISTA <letra> COM MEDIDAS           (elevação cotada)
```

Confere em todos os seis: Banho Suíte 2+2×1 = 4 · Cozinha Willian 2+2×2 = 6 · Cozinha Edson
2+2×4 = 10 (saiu 8, por agrupamento) · Suíte Juliana 2+2×4 = 10 (saiu 9, por agrupamento).

### O que o Caderno Cliente NÃO tem

Isto é tão definidor quanto o que ele tem, e é onde o motor está mais longe:

- **não tem tabela de listagem** — nenhum item com descrição e medida em lugar nenhum
- **não tem balão numerado** sobre os móveis
- **não tem prancha de contrato**
- **não tem detalhe de nicho, de costas, de rodapé, de divisor de gaveta**
- **não tem prancha "MÓDULOS E PAINÉIS"**

## 3. Prancha a prancha

### 3.1 CAPA
Cliente em destaque e o ambiente. Só isso.

### 3.2 PLANTA COM VISTAS E ESPECIFICAÇÕES
Uma prancha só, sempre presente, e carrega quatro coisas:

**a) A planta** com as letras das vistas posicionadas (A, B, C, D) e cotas de parede —
curtas, do tipo `1042 900 900 48` e `600` / `1931`.

**b) O bloco ESPECIFICAÇÕES DO PROJETO**, com três seções de rótulo fixo:

```
CORES E ACABAMENTOS:            FERRAGENS E ACESSÓRIOS:      ESPESSURAS:
  Caixa Modulos:                  Dobradiças:                  Caixa Modulos (Interno):
  Porta e Frentes:                Corrediças:                  Prateleiras internas:
  Tamponamentos:                  Puxadores:                   Porta e Frentes:
  Paines e Tampos:                Ferragens especiais:         Tamponamentos:
  Puxadores:                                                   Paines e Tampos e Prateleiras:
  Portas de Vidro:
```

Os rótulos são **sempre os mesmos**, inclusive o erro de digitação "EPECIFICAÇÕES" e "Paines",
que se repete nos 6 cadernos — é um template. Campo sem conteúdo fica em branco, não some
(`Portas de Vidro:` vazio na Área de Serviço e na Suíte da Juliana).

O valor é sempre `<cor> - <fabricante>`: `Beton Matt - Arauco`, `Branco Tx - Duratex`,
`Mint - Duratex e Louro Freijó trend - Arauco` (dois materiais na mesma linha, separados por "e").

**c) O detalhe de PUXADOR**, desenhado e cotado, um por tipo usado no projeto, com o nome em
caixa alta: `PUXADOR PASSANTE`, `PUXADOR CAVA`, `PUXADOR ROMA`, `PUXADOR SUPERIOR`,
`PUXADOR INFERIOR`, ou só `PUXADOR` quando é um só.

**d) O cabeçalho**, que é diferente do que o motor usa hoje:

```
PROJETO: <ambiente>   CLIENTE: <nome>   RESPONSÁVEL TÉCNICO: JOÃO FELIPE SANTOS   PÁG:
```

O motor usa `CLIENTE / AMBIENTE / PROJETISTA TÉCNICO / ARQUITETA`. São campos diferentes.

### 3.3 VISÃO GERAL DOS MÓVEIS
3D do móvel da vista. Duas variações observadas:

- **portas fechadas + portas abertas** na mesma prancha (Cozinha do Willian: `VISTA A` e
  `VISTA A - ABERTO`), quando há basculante ou algo que só se entende aberto;
- **duas vistas na mesma prancha** quando cabem (Cozinha do Alexandre: `VISTA A VISTA B`;
  Cozinha do Edson: `VISTA A` e `VISTA B` juntas, `VISTA C` na seguinte).

### 3.4 VISTA <letra> COM MEDIDAS
Elevação cotada. O título varia entre `VISTA A COM MEDIDAS`, `VISTA B - COM MEDIDAS` e só
`VISTA A` — não é rígido.

As cotas **não são só o contorno**: a Cozinha do Edson traz `200 185 200 100 100 100 300` numa
cadeia, que são as frentes de gaveta uma a uma. Ou seja, o Caderno Cliente cota o que o cliente
enxerga pela frente — larguras, alturas de frente, vãos — mas não abre o interior do módulo.

### 3.5 Anotações livres
Aparecem soltas sobre o desenho, escritas à mão pelo projetista:

- `LED PARTE INFERIOR BASCULANTE`, `LED NA PRATELEIRA`, `Led na parte superior da penteadeira`
- `Vão deixado para porta de correr`, `Vão deixado para o acesso ao interruptor`
- `Penteadeira com vidro no tampo`
- acessórios nomeados sobre a vista: `ADEGA`, `FRUTEIRA`, `PORTA TEMPEIROS INCLINADO`,
  `PORTA TALHERES` — estes com um detalhe cotado próprio ao lado (`405 500 30`)

As três primeiras famílias o motor **não tem como inventar** — precisam vir do config do projeto.
A última (acessórios nomeados) **vem do XML** e é gerável.

## 4. A distância entre o motor e o Caderno Cliente

Esta é a conclusão que muda o rumo do trabalho, e por isso está separada: **o que o motor produz
hoje não é um Caderno Cliente.**

| | Caderno Cliente (NADECOR) | motor v31/v32 hoje |
|---|---|---|
| pranchas fixas | 2 (capa, planta+espec) | 4 (capa, contrato, planta, visão geral) |
| por vista | 2 (3D, medidas) | 2 + réplicas de detalhe |
| tabela de itens | **não existe** | em toda prancha de listagem |
| balões numerados | **não existem** | sim |
| detalhes (nicho, costas, rodapé, divisor) | **não existem** | 8 condições implementadas |
| cabeçalho | PROJETO / CLIENTE / RESP. TÉCNICO | CLIENTE / AMBIENTE / PROJETISTA / ARQUITETA |
| espessuras e ferragens | bloco fixo na prancha 2 | prancha 03 própria |

O `config_nuvem.json` dos exemplos diz `"tipo_caderno": "MONTAGEM E INSTALAÇÃO"` — e é isso mesmo
que o motor faz. Listagem com balões, tabela de peças e detalhes de nicho/costas/rodapé são
informação de **montador**, não de cliente. As 25 versões de regra da v9 à v31 foram todas
construídas em cima desse tipo.

Logo: **a maior parte do que está no motor não é erro — é o caderno errado.** O Caderno Cliente é
mais simples, e boa parte do que o motor aprendeu a fazer com tanto esforço (listagem poluída,
peça escondida, sub-imagem, divisor de gaveta) não entra nele. Deve migrar para o Caderno de
Instalação, que é o tipo onde essa informação faz sentido.

## 5. O que falta confirmar

Este documento vem de 5 cadernos. Antes de virar especificação, precisa passar pelos **24
restantes**, para separar regra de exceção:

1. A prancha 2 é sempre uma só, mesmo com 4+ vistas?
2. Quando duas vistas dividem a prancha de VISÃO GERAL — é por largura da parede, por número de
   vistas, ou é escolha manual?
3. `VISTA A - ABERTO` aparece por qual gatilho? (basculante? gaveta? adega?)
4. As cotas internas (frentes de gaveta) aparecem sempre, ou só em cozinha?
5. Os rótulos do bloco de especificações são fixos mesmo, ou variam por vendedor?
6. Existe caderno de cliente com listagem? (até agora: nenhum)

## 6. Como confirmar, de forma determinística

Os cadernos são PDF com texto real — dá para extrair sem olhar desenho:

- título de cada prancha, na ordem → a sequência
- rótulos do bloco de especificações → o template
- valores de cota por prancha → granularidade
- presença ou ausência de tabela (par descrição + `AxBxC`) → o corte Cliente x Instalação

Rodando isso nos 29 e cruzando, cada resposta da seção 5 vira contagem, não opinião.
