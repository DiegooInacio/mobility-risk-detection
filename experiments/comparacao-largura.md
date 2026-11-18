# Comparação do critério de área com suporte por largura

## Hipótese e implementação

O limiar de 5% da área total pode perder candidatos pequenos na imagem. Foi
implementado `--decision-mode width` como alternativa experimental para investigar
obstáculos com suporte horizontal central, mas área total reduzida. A regra de
área continua sendo o padrão; não se declarou uma alternativa superior.

Os candidatos continuam exigindo proximidade, diferença de profundidade do chão
e componente de ao menos 1% da ROI. Cada componente é avaliado individualmente:

- ao menos 30% da largura da ROI ocupada por pixels reais do componente por linha;
- ao menos 50% da faixa central da ROI ocupada nessa linha (faixa entre 40% e 60%
  da largura da ROI);
- essas condições precisam ocorrer por pelo menos 2% da altura da ROI em linhas
  consecutivas, nunca menos de duas linhas.

Não se usa a caixa delimitadora como se estivesse cheia. Componentes desconectados
não são fundidos automaticamente. O limiar total de 5% não participa da decisão
no modo largura, mas é mantido como diagnóstico. A regra ainda depende de escala
aparente e da ROI fixa; não mede largura física nem garante passagem livre.

## Comparação controlada

Foram reutilizados os mapas de 11 imagens: seis da coleta02 e cinco anteriores.
Compararam-se três decisões em cada alcance de 2 m e 3 m:

1. Área final de pelo menos 5%, referência anterior.
2. Área final de pelo menos 3%, alternativa simples de maior sensibilidade.
3. Suporte horizontal central por componente, nova alternativa.

Isso produziu 66 análises. O modelo, o perfil do chão, a diferença mínima de
0,30 m, a ROI e o filtro de componentes de 1% foram mantidos. Os perfis são fixos
para todas as imagens e estão em `experiments/perfis-largura.json`. Esta é uma
comparação de desenvolvimento motivada por falhas conhecidas; não é validação
independente. As distâncias nominais da coleta02 são aproximadas.

## Resultados

S = com alerta; N = sem alerta. Nenhum desses casos ficou inconclusivo.

| Foto | Área 5%, 2 m | Área 3%, 2 m | Largura, 2 m | Área 5%, 3 m | Área 3%, 3 m | Largura, 3 m |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| cadeira1metro | S | S | S | S | S | S |
| cadeira1meiometro | S | S | S | S | S | S |
| cadeira2metros | N | N | N | N | S | N |
| cadeiraadireita1 | N | N | N | N | N | N |
| parciallivre1 | N | N | N | N | N | N |
| livrechichi1 | N | N | N | N | N | N |
| cadeirafrente1 | S | S | S | S | S | S |
| cadeirafrente2 | S | S | S | S | S | S |
| cadeiralado1 | S | S | N | S | S | S |
| livre1 | N | N | N | S | S | N |
| livre2 | N | N | N | S | S | S |

O modo de área padrão a 2 m preservou exatamente as decisões e proporções
candidatas dos resultados anteriores nas 11 imagens.

### O que explica os resultados

- **Terceira cadeira frontal:** com alcance de 2 m, nenhum candidato passa por
  proximidade e diferença do chão simultaneamente. Alterar a decisão final não
  pode recuperar candidatos inexistentes. Com alcance de 3 m, a área candidata
  total chega a 3,57%, dividida em dois componentes. A regra de área de 3% gera
  alerta, mas a de largura falha por falta de suporte central contínuo em cada
  componente. A estrutura vazada da cadeira e a seleção por profundidade podem
  fragmentar o candidato; não se pode interpretar os componentes como objetos.
- **Cadeira lateral antiga:** com alcance de 2 m, o modo largura deixa de alertar
  sobre os candidatos laterais que não apresentam o suporte central exigido. Essa
  redução é observável, mas a própria rotulagem dessa cena é ambígua: a cadeira
  invade parte da ROI.
- **Cenas fornecidas como livres:** ao aumentar o alcance para 3 m, aparecem
  alertas em `livre1` e `livre2` nos modos de área. O modo largura evita o primeiro,
  mas não o segundo. Em `livre2`, a marcação cobre a parede frontal. Uma parede
  pode ser obstáculo real se a direção de caminhada for para ela; portanto, chamar
  todo alerta nessa imagem de falso positivo só pelo nome seria inadequado.

## Conclusão e próximos passos

A alternativa por largura tem efeito no tipo de candidato aceito, mas não
recuperou o caso principal. Reduzir a área para 3% e ampliar o alcance para 3 m
recupera esse caso, porém também amplia os alertas para superfícies nas fotos
anteriores. Não há evidência suficiente para substituir a configuração padrão.

O próximo passo deve investigar a geração e o agrupamento dos candidatos, além
do limiar final: confrontar profundidade com distâncias medidas; definir rótulos
por direção pretendida e distância; avaliar a identificação de objetos/superfícies
para agrupar partes de um mesmo obstáculo e distinguir chão e parede. A falta de
suporte central também pode excluir objetos estreitos; esse risco precisa de
exemplos próprios, não apenas cadeiras. Novas decisões baseadas nestas 11 fotos
precisam ser avaliadas depois em imagens diferentes.

## Artefatos e verificação

- `outputs/comparacao-largura/summary.csv`: todas as configurações e decisões.
- `<perfil>/<foto>/overlay.png`: mesmos candidatos mantidos para o respectivo
  alcance; pode haver vermelho sem alerta, pois a máscara precede a decisão final.
- `<perfil>/<foto>/report.json`: decisões de área e largura, suporte por componente.
- `run.json` e `source_snapshot/`: parâmetros, hashes e código usado na execução.

Os 23 testes passaram. Foram acrescentados cenários sintéticos de região central
com área abaixo de 5%, regiões finas/laterais e suporte horizontal em linhas
isoladas. Nenhum PDF foi gerado nesta etapa.
