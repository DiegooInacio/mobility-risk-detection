# Scripts

## Relatório consolidado da etapa métrica e de segmentação

```bash
python -m pip install -e '.[report]'
python scripts/generate_progress_report.py
```

Gera `documentation/relatorio-poc-profundidade-metrica-e-segmentacao.pdf` no mesmo
padrão A4 em preto e branco do relatório anterior, preservado separadamente.
Consolida as 11 imagens e os experimentos posteriores ao commit `e101bda`.
Depende das saídas em `outputs/coleta02/baseline/`, `outputs/comparacao-largura/`
e `outputs/comparacao-objetos/`, além das fotos originais. A geração não executa
os modelos. O conteúdo descreve esta etapa específica; novas coletas e
conclusões exigem revisão do texto.

## Comparar segmentação de instâncias e geometria

```bash
python -m pip install -e '.[objects]'
python scripts/compare_objects.py
```

Reutiliza os mapas métricos do manifesto
`experiments/coleta-comparacao-largura.json`. Compara regras `metric`, `objects` e
`hybrid`, cada uma com distâncias máximas de 2 m e 3 m. Os demais critérios são
fixos. Faz uma inferência de YOLO11n-seg por foto e reutiliza suas máscaras nas
outras configurações. Não faz nova inferência de profundidade.

Salva relatórios, overlays, instâncias, CSV, hashes e código em
`outputs/comparacao-objetos/`. Use `--output` novo para repetir; destinos não vazios
são recusados. `--collection`, `--segment-model`, `--device` e `--instances-dir`
configuram entradas. `--instances-dir` procura `<nome>/instances.npz` e seu
metadado, validando o hash da foto; as instâncias ausentes são geradas.

Resultados sem objeto reconhecido com confiança suficiente ficam inconclusivos
no ramo por objetos. O modo híbrido preserva os alertas geométricos, incluindo
paredes sem classe reconhecida. Não se calcula acurácia nem se escolhe uma
configuração melhor automaticamente. Veja `experiments/comparacao-objetos.md`.

## Comparar área e largura ocupada

```bash
python scripts/evaluate_collection.py \
  --collection experiments/coleta-comparacao-largura.json \
  --profiles experiments/perfis-largura.json \
  --output outputs/comparacao-largura
```

Aplica seis perfis às mesmas 11 imagens: área de 5%, área de 3% e suporte por
largura, cada um com distância máxima de 2 m e de 3 m. Os caminhos explícitos
`depth_map` no manifesto permitem reunir mapas de coletas diferentes. A análise
não faz nova inferência nem muda o padrão da aplicação. O CSV agora inclui o
grupo de origem, o modo de decisão e os diagnósticos de área e largura.

## Segunda coleta e comparação de configurações

```bash
python scripts/evaluate_collection.py
```

Lê `experiments/coleta02.json` e os mapas métricos existentes em
`outputs/coleta02/baseline/<nome>/depth.npy`. Compara limites de distância de 2 m,
2,5 m e 3 m, mantendo os demais critérios fixos. Não executa o modelo. Gera CSV,
artefatos por perfil e um registro com hashes das entradas e cópia do código em
`outputs/coleta02/comparacao/`. Destino não vazio é recusado para preservar os
resultados; use `--output` com pasta nova para repetir. `--collection` e `--maps-dir`
permitem escolher outra coleta e seus mapas.

`--profiles caminho/perfis.json` aceita, por exemplo,
`{"referencia": {}, "alcance-3m": {"max_distance_m": 3.0}}`. Os parâmetros são os
de `MetricConfig` e cada perfil é aplicado a todas as imagens, sem ajuste individual.
Os testes são exploratórios; o script não atribui acurácia nem seleciona o melhor
perfil automaticamente. Veja `experiments/coleta02-resultados.md`.

## Comparar profundidade métrica com as regras anteriores

```bash
python scripts/compare_metric.py
```

Executa o modelo métrico indoor nas fotos já presentes na comparação em
`outputs/diagnostico/` e reúne resultados em `outputs/metric/summary.csv`. Não
substitui os mapas relativos. A configuração fica fixa em 2 m de profundidade
máxima, diferença mínima de 0,30 m em relação ao chão, componentes de ao menos 1%
da ROI e área final de ao menos 5%. Esses limites ainda não foram calibrados.

Para repetir a análise dos mapas métricos salvos, use `--reuse-maps`; apenas mapas
faltantes exigem inferência. `--images-dir`, `--baseline-dir`, `--output` e
`--device` configuram as pastas e o dispositivo. Os tempos incluem carregamento
do modelo por foto e não devem ser usados como medida de FPS.

## Gerar relatório em PDF

```bash
python -m pip install -e '.[report]'
python scripts/generate_poc_report.py
```

Gera `documentation/relatorio-poc-comparacao-regras.pdf` em A4, com texto e tabelas
em preto e branco e fotos em tons de cinza. As marcações dos candidatos aparecem
como hachuras. Requer os resultados da comparação inicial em
`outputs/diagnostico/`, as cinco fotos e suas máscaras. O relatório descreve essa
coleta específica; novas coletas exigem revisão do texto e das conclusões.

## Comparar regras com mapas existentes

Na raiz do projeto, com a `.venv` ativa:

```bash
python scripts/compare_rules.py
```

Compara `lateral` e `floor`, cada uma com proximidade `0.60` e `0.20`, sem executar
o modelo. A entrada é `outputs/comparacao/*/original/depth.npy` e a foto com mesmo
nome em `fotos/`. O destino é `outputs/diagnostico/`, com um `summary.csv` e os
artefatos de cada configuração. Falha explicitamente se faltar mapa ou houver
foto ausente/ambígua. Não atribui rótulos reais nem calcula acurácia automaticamente.

As opções `--images-dir`, `--maps-dir` e `--output` permitem mudar as pastas.

Esta pasta será destinada a scripts auxiliares utilizados durante o desenvolvimento do projeto.

Alguns exemplos:

- preparação e organização de datasets;
- redimensionamento e conversão de imagens;
- geração de mapas de profundidade;
- execução de testes em lote;
- conversão de modelos;
- exportação para ONNX ou outros formatos;
- geração de métricas e resultados experimentais.

Os scripts desta pasta não fazem parte diretamente da aplicação final, mas auxiliam no processo de desenvolvimento e avaliação.
