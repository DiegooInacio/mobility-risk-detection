# Terceira abordagem: profundidade métrica indoor

## Implementação

Adicionada a opção `--rule metric`, com o modelo oficial
[Depth Anything V2 Metric Indoor Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf).
Essa variante estima profundidade em metros; não utiliza os mapas relativos
anteriores. A configuração do modelo identifica `depth_estimation_type=metric`
e `max_depth=20`.

A decisão usa profundidade máxima de 2 m e um perfil de chão ajustado em `1/m`
na faixa inferior central. Candidatos precisam estar pelo menos 0,30 m mais
próximos que o perfil previsto e formar componentes de ao menos 1% da ROI. Há
alerta quando a soma dos componentes mantidos ocupa ao menos 5% da ROI. O gap é
diferença de profundidade na imagem, não altura física. Os limites foram definidos
como configuração inicial e mantidos nas cinco imagens, sem ajustes individuais.

São mantidas a mesma ROI retangular e as regras relativas anteriores. A
normalização por percentis não participa da decisão métrica. Novos metadados nos
mapas permitem rejeitar mistura de unidades. Os relatórios passam a listar área,
caixa e percentis de profundidade das regiões conectadas mantidas.

## Execução nas cinco fotos

| Foto | Área final métrica | Regiões mantidas | Resultado |
|---|---:|---:|---|
| cadeirafrente1 | 12,54% | 1 | Possível obstáculo |
| cadeirafrente2 | 19,05% | 1 | Possível obstáculo |
| cadeiralado1 | 21,21% | 2 | Possível obstáculo |
| livre1 | 0,00% | 0 | Sem indício pela regra |
| livre2 | 0,00% | 0 | Sem indício pela regra |

Todos os ajustes do perfil inferior foram aceitos. Isso não comprova que essa
faixa contém exclusivamente chão. A inspeção visual confirma marcação do assento
das duas cadeiras frontais. Em `cadeiralado1`, aparecem marcações tanto na cadeira
que invade a ROI quanto na borda do armário: a separação entre paredes e obstáculos
continua sem solução semântica/geometria explícita da trajetória.

Comparação com profundidade relativa e proximidade 0,20:

- A regra lateral anterior não detectava `cadeirafrente2`; a métrica gera alerta.
- A regra relativa baseada no chão gerava alerta em `livre1`; a métrica não gera.
- A decisão na cadeira lateral continua exigindo critério de rotulagem: sua
  posição nominal lateral não significa ausência de interseção com a ROI.

Os cinco arquivos já eram conhecidos e usados no desenvolvimento. Esses
resultados são exploratórios, não estimativas confiáveis de acurácia. Não houve
comparação das profundidades estimadas com distâncias medidas. A extensão para
outras cenas, iluminação, objetos ou aparelhos ainda precisa de avaliação.

## Reprodução

```bash
python scripts/compare_metric.py
python scripts/compare_metric.py --reuse-maps
python -m unittest discover -s tests -v
```

O script depende das fotos e dos relatórios anteriores em `outputs/diagnostico/`.
Gera `outputs/metric/summary.csv`, com as configurações relativas anteriores e a
métrica, e artefatos por foto. Os mapas e as fotos permanecem fora do Git. Os
tempos incluem carregamento por foto ou leitura de mapa reutilizado, não FPS.
O PDF da etapa anterior foi preservado como registro daquela comparação.
