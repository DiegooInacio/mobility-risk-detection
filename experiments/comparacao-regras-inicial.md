# Comparação exploratória de regras

Foram reutilizados os cinco mapas da coleta inicial, sem nova inferência. Todas
as configurações usaram a mesma ROI, contraste mínimo `0.15` e área mínima `0.05`.
Compararam-se as referências lateral e perfil do chão com proximidade `0.60` e
`0.20`. Esses dados são de desenvolvimento, não um conjunto independente de teste.

Percentual da ROI que satisfez simultaneamente proximidade e contraste:

| Foto | Lateral 0.60 | Lateral 0.20 | Chão 0.60 | Chão 0.20 |
|---|---:|---:|---:|---:|
| cadeirafrente1 | 5,04% | 21,07% | 5,04% | 40,78% |
| cadeirafrente2 | 0,00% | 0,03% | 0,00% | 22,79% |
| cadeiralado1 | 2,95% | 5,50% | 2,97% | 21,58% |
| livre1 | 0,00% | 0,00% | 0,00% | 16,84% |
| livre2 | 0,00% | 0,00% | 0,00% | 0,00% |

Há alerta quando a proporção é pelo menos 5%, usando o valor sem arredondamento.
Os números exatos e relatórios são gerados por `python scripts/compare_rules.py`
em `outputs/diagnostico/summary.csv`; os artefatos locais não são versionados.

## Observações

- A regra lateral com proximidade `0.20` perde a segunda cadeira frontal, mesmo
  com 27,36% da ROI passando por proximidade: apenas 0,14% passa por contraste.
- A referência do chão com proximidade `0.20` marca o assento da segunda cadeira
  frontal, mas também marca a borda do armário em `livre1`, gerando um alerta na
  cena fornecida como livre. Não se pode concluir que essa regra seja superior.
- Em `cadeiralado1`, parte do assento e da perna da cadeira invade a ROI amarela.
  Seu rótulo de obstáculo frontal precisa de um critério explícito; o nome do
  arquivo não basta para classificar o alerta como falso positivo.
- A ROI retangular não projeta geometricamente uma trajetória. Em `livre1`, ela
  também cobre parede e armário, enquanto a abertura da porta está à direita.

Próxima avaliação: definir o critério de obstáculo frontal, manter os parâmetros
fixos e usar cenas novas para avaliar as hipóteses. Guardar esses casos de falha
para comparação, sem reajustar os limiares individualmente por foto.
