# Ocupação frontal sem profundidade

## Hipótese e recorte

A partir do commit de referência `a8af775`, foi implementada a alternativa
`--rule occupancy` para investigar se a presença e a ocupação aparente de objetos
na região frontal permitem uma POC mais simples. A pergunta passa a ser
"há um objeto reconhecido ocupando a região frontal da imagem?". A análise não
responde se o usuário está fisicamente próximo ou se há risco de colisão.

Não há mapa de profundidade, distância em metros ou zona física ao redor de
objetos nesta regra. A caixa delimita visualmente a instância prevista; a decisão
usa a máscara. O modelo segmentador é o mesmo YOLO11n-seg da etapa anterior.

## Comparação controlada

Foram reutilizadas exatamente as máscaras das 11 imagens da etapa anterior.
Os critérios espaciais foram extraídos para funções compartilhadas entre as
regras por objetos e por ocupação, mantendo os mesmos limiares:

| Critério por instância | Limiar |
|---|---:|
| Confiança de segmentação | 0,35 |
| Parcela da área da ROI ocupada pela máscara | 1% |
| Parcela da máscara total que está dentro da ROI | 10% |
| Parcela da máscara na ROI que está na faixa central | 10% |

A ROI mantém os mesmos limites (35%–65% da largura e 30%–80% da altura), assim
como a faixa central (40%–60% da largura da ROI). A única condição retirada em
relação à regra `objects` é a fração próxima na profundidade. As decisões e as
máscaras das 22 análises históricas por objetos (11 fotos, dois alcances) foram
conferidas novamente e preservadas após a extração das funções compartilhadas.

Há **11 análises novas de ocupação** e **66 referências históricas**, lidas do CSV
anterior. As 77 linhas do CSV combinado não são 77 imagens independentes nem 77
novas inferências. A comparação não executou nenhum modelo ou carregou mapas de
profundidade. Houve também uma execução real independente do segmentador em uma
foto para verificar o caminho sem cache da nova opção.

## Resultados

Na coluna ocupação: O = ocupação frontal detectada; N = sem ocupação pela regra;
I = inconclusivo. Nas referências métricas: S = possível obstáculo; N = sem
indício; I = inconclusivo. Os estados descrevem perguntas diferentes.

| Foto | Objetos 2 m | Objetos 3 m | Ocupação | Área ocupada da ROI |
|---|:---:|:---:|:---:|---:|
| cadeira1metro | S | S | O | 67,57% |
| cadeira1meiometro | S | S | O | 33,01% |
| cadeira2metros | N | S | O | 23,91% |
| cadeiraadireita1 | I | I | I | 0,00% |
| parciallivre1 | N | N | O | 3,41% |
| livrechichi1 | N | N | N | 0,00% |
| cadeirafrente1 | S | S | O | 61,79% |
| cadeirafrente2 | S | S | O | 63,86% |
| cadeiralado1 | S | S | O | 11,20% |
| livre1 | I | I | I | 0,00% |
| livre2 | I | I | I | 0,00% |

Os percentuais são a união das máscaras aceitas dentro da ROI, sem contagem dupla.
Não são acurácia, confiança, distância ou proporção física do caminho bloqueado.

### Interpretação dos casos relevantes

- **Três cadeiras da nova coleta:** todas ocupam a região frontal segundo a regra.
  A terceira deixa de depender do gargalo de profundidade, mas essa mudança não
  demonstra proximidade física. A ocupação aparente cai de 67,57% para 33,01% e
  23,91% nessas três fotos. A tendência é observável nesta sequência, não uma
  calibração; as distâncias foram informadas como aproximadas.
- **`parciallivre1`:** a máscara aceita corresponde a uma cadeira ao fundo, e não
  ao galão lateral. Ela ocupa 3,41% da ROI. A imagem passa a gerar ocupação mesmo
  tendo ficado sem alerta nas regras por objetos de até 2 m e 3 m. É uma limitação
  explícita da remoção da profundidade caso o objetivo seja alertar só para riscos
  próximos; é uma detecção de presença frontal se esse for o recorte escolhido.
- **`livrechichi1`:** o cachorro é reconhecido, mas a máscara fica fora do suporte
  central exigido. O usuário já havia confirmado que está fora do caminho
  pretendido. Isso não demonstra tratamento correto para qualquer animal lateral.
- **`cadeiraadireita1`, `livre1` e `livre2`:** continuam inconclusivas, por ausência
  de detecções confiáveis. Não são contabilizadas como passagens livres ou acertos.
- **`cadeiralado1`:** permanece com ocupação; a máscara prevista invade a faixa
  central. A ambiguidade de trajetória e os erros de máscara não são resolvidos.

## Limites e conclusão desta etapa

A simplificação elimina a etapa de profundidade e permite executar a análise com
um único modelo, ou só com máscaras em cache. O resultado fica explicitamente
restrito à ocupação na imagem. Não foram medidos desempenho móvel, consumo de
memória ou latência comparável de inferência contínua.

Objetos ao fundo podem gerar ocupação. Paredes e classes desconhecidas não passam
a ser cobertas por esta abordagem; ausência de detecção continua inconclusiva.
Tamanho aparente depende de dimensões reais, enquadramento e orientação. Logo,
não se estabelecem faixas de perto/longe ou distâncias a partir dessas fotos.

É uma alternativa concreta para o recorte de identificação de objetos frontais,
com o compromisso de retirar a afirmação de proximidade. A amostra é conhecida e
pequena, sem avaliação independente. Não se alterou automaticamente a regra padrão
nem se ajustou limiar individual por imagem.

## Artefatos e reprodução

```bash
mobility-risk fotos/cadeira2metros.jpeg --rule occupancy \
  --instances outputs/comparacao-objetos/objects-2m/cadeira2metros/instances.npz \
  --output outputs/ocupacao-cache

python scripts/compare_occupancy.py
```

- `outputs/comparacao-ocupacao/occupancy/<foto>/overlay.png`: imagem marcada;
- `occupancy.png`: máscara de ocupação dentro da ROI;
- `report.json`: critérios, proporções e rejeições por instância, sem distâncias;
- `instances.npz` e metadados: cache reutilizável da segmentação;
- `summary.csv`: referências históricas e os 11 novos resultados;
- `run.json` e `source_snapshot/`: parâmetros, hashes, versões e código usado.

O script recusa destino não vazio. Para repetir, use `--output` com outra pasta.
Parâmetros de profundidade são rejeitados pela regra de ocupação, assim como um
destino contendo artefatos de profundidade de outra abordagem.

## Verificação

Os 42 testes automatizados passaram. Os novos cenários cobrem ocupação central,
rejeição lateral e por tamanho, ausência de reconhecimento confiável, máscaras
sobrepostas, proporções por imagem/ROI e independência da profundidade. A
comparação foi testada com o mapa indicado no manifesto deliberadamente ausente,
confirmando que ele não é necessário. O caminho sem cache foi verificado com
segmentador simulado no teste e com inferência real na foto da terceira cadeira.
