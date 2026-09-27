# ESTADO DO PROJETO — MOTOR DO CADERNO CLIENTE

Atualizado em 27/09/2026. Ramo `v32-limpeza`, motor em `C:\CLAUDE\motor v34`.

## Quanto falta

**Aproximadamente 65% pronto.** A conta: das regras que o João definiu, **11 estão entregues
e medidas**, **6 estão pendentes** e a validação contra caderno aprovado ainda não foi feita.

O que sustenta esse número: a espinha do caderno está certa e provada, e as correções que faltam
são pontuais — nenhuma exige reescrever arquitetura.

## O que é o Caderno Cliente (ditado pelo João, é a fonte de verdade)

```
1.  CAPA
2.  CONTRATO
3.  FERRAGENS + CORES + PLANTA COM AS VISTAS      (tudo numa prancha só)
4.  VISÃO GERAL DOS MÓVEIS
    por vista:
      VISTA A — imagem 3D com listagem
      VISTA A — imagem 2D com cotas
    (se tiver muito móvel: duas imagens 3D)
```

**Listagem = módulo, fechamento, vista, rodapé, tamponamento.** Só esses cinco.

O motor **já produz essa estrutura**. Não é preciso construir, é preciso podar.

## Entregue e medido

| regra | prova |
|---|---|
| base limpa, sem código morto nem função duplicada | 2.346 → 1.925 linhas; saída idêntica nos 12 projetos, com grupo de controle |
| `texturas/` é asset só-leitura (determinismo) | rodada fria e quente dão o mesmo PDF; `git status` não acusa imagem modificada |
| paredes e piso sólidos | parede 0.94 → 0.93 com contraste real; piso 0.78 com contorno |
| parede da frente removida (sem recorte) | parede à frente da face frontal do móvel não entra |
| vista frontal exata | elevação 3° → 0°; arestas verticais no prumo |
| nicho amarcado: móvel com porta nunca é nicho | UMA definição de porta (eram 4); Guilherme Cozinha foi de 1 nicho falso para 0 |
| só nicho gera segunda imagem | saíram costas, rodapé/base, módulo pequeno e "como fica montado" |
| peça escondida não é listada | Priscila Cozinha: Vista A 27 → 21 linhas |
| sem asterisco | 0 em 14 páginas |
| balão de escondida não volta na listagem dividida | `_partes` usa a lista filtrada |
| motor sem referência externa | zero nome de cliente e zero caminho de máquina no código |

Efeito acumulado: Guilherme Cozinha **15 → 12 pranchas**, e o relatório de qualidade passou a
fechar a conta (`12 = 4 + 4 listagens + 4 cotas`).

## O que falta

**1. Detalhe do nicho está ilegível.** Ao desenhar "sozinho no espaço", saem chapas soltas
flutuando em vez de um nicho. Provável correção: manter o módulo a que o nicho pertence, sem
parede e sem chão.

**2. Listagem ainda aceita item fora dos cinco tipos.** Corrediça, suporte e quadro metálico
aparecem. Precisa filtrar por categoria: módulo, fechamento, vista, rodapé, tamponamento.

**3. Paredes laterais invadem a vista frontal.** Com a câmera a zero grau elas aparecem inteiras
pelas bordas. Decidir se saem ou viram faixa fina de referência.

**4. Cotas internas ilegíveis em módulo estreito.** Os números se sobrepõem em escala pequena.

**5. Pranchas que ainda sobram.** Divisor de gaveta e gaveta montada com painéis continuam com
prancha própria. O corte ficou parado por decisão do João.

**6. Sequência espacial (seção 5 da ENGENHARIA) não existe no motor.** Cozinha começa pela pia,
quarto pelo guarda-roupa, escritório pela bancada. Hoje a ordem é a do XML.

**7. Validação contra caderno aprovado nunca foi feita.** É o que falta para sair de "parece
certo" e chegar em "está certo".

## Como trabalhar neste projeto

- **Planejar antes de executar, sempre.** Três ações por bloco, aprovação do João, execução,
  parada, validação gerando um caderno, e só então o bloco seguinte.
- **Medir, não afirmar.** Toda alteração de código se prova mostrando a fonte e rodando os
  projetos. Foi assim que a limpeza de 330 linhas deixou de ser promessa.
- **Sem cópias no código.** Alterar no lugar, nunca criar segunda definição da mesma função.
- **Respostas objetivas**, em lista: o que foi executado, o que não foi.
- **Custo importa.** Rodar o motor no PC é quase de graça; ler PDF de caderno é caro. O ciclo
  barato é gerar, o João apontar, corrigir um ponto, gerar de novo.

## Onde está cada coisa

- Motor: `C:\CLAUDE\motor v34` — e no GitHub, ramo `v32-limpeza`
- Regras do João: `ENGENHARIA.pdf` neste repositório
- Histórico do incidente de 27/09: `TRILHA_MOTOR_CADERNO_26-27-09.md`
- Auditoria das versões v9 a v31: `AUDITORIA_v9_v31.md`
- 12 cadernos gerados em 26/09: `C:\CLAUDE\MARCO v32 - 26-09-2026`
