# Segunda coleta: referência para próximas melhorias

Foram analisadas seis imagens novas com o modelo métrico indoor e a configuração
atual: distância máxima de 2 m, diferença de profundidade do chão de 0,30 m,
componentes de no mínimo 1% da ROI e área final mínima de 5%. Nenhum parâmetro
padrão do algoritmo foi alterado nesta coleta.

## Condições e interpretação

O usuário confirmou que os nomes 1 m, 1,5 m e 2 m indicam distâncias aproximadas,
sem medição de referência. Portanto, não permitem calcular erro de profundidade
ou calibrar o modelo em metros. A cadeira de aproximadamente 2 m é um caso
próximo do limite padrão, sem garantia de estar dentro dele.

Também confirmou que o cachorro em `livrechichi1` está fora do caminho pretendido.
As interpretações das demais cenas resultam de inspeção visual. Em `parciallivre1`,
há objetos laterais, incluindo um galão; não se trata de uma imagem sem objetos.
Ausência de alerta não significa reconhecimento de uma passagem segura nem
reconhecimento semântico do cachorro ou dos objetos laterais.

A lista de imagens e essas condições estão em `experiments/coleta02.json`.

## Configuração de referência

| Foto | Área candidata final | Resultado |
|---|---:|---|
| cadeira1metro | 18,51% | Possível obstáculo |
| cadeira1meiometro | 6,19% | Possível obstáculo |
| cadeira2metros | 0,00% | Sem indício pela regra |
| cadeiraadireita1 | 0,00% | Sem indício pela regra |
| parciallivre1 | 0,00% | Sem indício pela regra |
| livrechichi1 | 0,00% | Sem indício pela regra |

Os ajustes do perfil inferior foram aceitos nos seis casos. A inspeção das imagens
marcadas confirma candidatos na cadeira de aproximadamente 1 m e na estrutura
frontal da cadeira de aproximadamente 1,5 m. A terceira cadeira aparece na ROI,
mas não gera candidatos combinando distância de até 2 m e diferença do chão.

Os resultados originais desta execução estão em
`outputs/coleta02/baseline/<nome>/`: `overlay.png`, `depth.npy`, `depth.meta.json`,
`depth.png`, `candidates.png` e `report.json`.

## Sensibilidade ao limite de distância

Reutilizaram-se exatamente os mesmos mapas, variando apenas o limite de distância
estimada: 2 m, 2,5 m e 3 m. Todos os demais parâmetros permaneceram iguais. Trata-se
de análise exploratória motivada pela falha observada, não validação independente
de uma configuração melhor. Nenhum perfil foi promovido automaticamente a padrão.

| Foto | Limite 2 m | Limite 2,5 m | Limite 3 m |
|---|---:|---:|---:|
| cadeira1metro | 18,51% | 41,14% | 48,06% |
| cadeira1meiometro | 6,19% | 15,30% | 22,54% |
| cadeira2metros | 0,00% | 0,00% | 3,57% |
| cadeiraadireita1 | 0,00% | 0,00% | 0,00% |
| parciallivre1 | 0,00% | 0,00% | 0,00% |
| livrechichi1 | 0,00% | 0,00% | 0,00% |

Os percentuais representam área candidata após o filtro de componentes, não
acurácia ou probabilidade. O limiar de alerta continua em 5%. Por isso, aumentar
o alcance para 3 m ainda não gera alerta na terceira cadeira. Não há evidência
nesta comparação de que aumentar o alcance isoladamente resolva o problema.

## O que investigar a seguir

1. **Profundidade estimada versus medida:** obter distâncias reais com referência
   de medição definida. As estimativas aproximadas atuais não sustentam uma correção
   de escala do modelo, especialmente perto do limite de 2 m.
2. **Critério de área:** investigar a dependência do limiar de 5% da ROI em relação
   à distância e ao tamanho aparente do obstáculo. Na configuração de 3 m, a
   terceira cadeira tem candidatos, mas permanece abaixo do limiar. Isso não
   justifica baixar o limiar até acertar essa única foto; é preciso comparar
   sensibilidade e alertas indevidos em outras cenas.
3. **Perfil e região de passagem:** manter avaliação separada das hipóteses sobre
   chão e trajetória; o retângulo central não determina a intenção do usuário.

As seis imagens passam a integrar o conjunto de desenvolvimento/comparação. Depois
de escolher uma mudança com base nelas, será necessário usar outras imagens para
avaliar se a melhoria se mantém. Não se calcula uma taxa geral de eficácia a
partir desta pequena coleta com distâncias aproximadas.

## Reprodução e comparação futura

Com os mapas da configuração original presentes:

```bash
python scripts/evaluate_collection.py
```

O script gera `outputs/coleta02/comparacao/summary.csv`, imagens de cada perfil,
`run.json` com condições e hashes das entradas, e uma cópia dos arquivos de código
em `source_snapshot/`. Ele não executa o modelo e não altera os mapas originais.
Recusa destino não vazio para evitar sobrescrever uma comparação já registrada.
Para repetir, escolha uma pasta nova:

```bash
python scripts/evaluate_collection.py --output outputs/coleta02/repeticao-01
```

Um JSON em `--profiles` pode definir configurações de `MetricConfig`, aplicadas
igualmente a todas as imagens. A opção serve para investigações futuras sem
substituir a configuração de referência; resultados não são escolhidos como
melhores automaticamente. Fotos, mapas, imagens de saída e snapshots continuam
fora do Git em `fotos/` e `outputs/`. Nenhum PDF foi produzido nesta etapa.
