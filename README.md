# Mobility Risk Detection

Projeto de Trabalho de Conclusão de Curso na área de Tecnologia Assistiva, Processamento Digital de Imagens e Visão Computacional.

A proposta é investigar uma solução capaz de utilizar a câmera RGB de um smartphone para identificar possíveis riscos de mobilidade para pessoas com deficiência visual.

A abordagem inicialmente considerada utiliza estimativa monocular de profundidade para gerar mapas de profundidade a partir das imagens da câmera. Esses dados serão utilizados para analisar a região frontal de deslocamento e verificar se existe algum elemento que possa representar risco na trajetória do usuário.

## Objetivo

Investigar a viabilidade do uso de visão computacional e estimativa monocular de profundidade em smartphones para identificação de riscos de mobilidade.

## Estrutura do projeto

```text
mobility-risk-detection/
├── android-app/
├── web-demo/
├── ai/
├── experiments/
├── scripts/
├── documentation/
└── README.md
```

### `android-app`

Aplicativo Android responsável pela captura da câmera, processamento em tempo real e feedback acessível.

### `web-demo`

Demonstração web utilizada para facilitar testes de imagens, câmera, mapas de profundidade e detecção de riscos.

### `ai`

Modelos e algoritmos relacionados à estimativa de profundidade, processamento de imagens e análise de risco.

### `experiments`

Experimentos, benchmarks, métricas e resultados obtidos durante o desenvolvimento.

### `scripts`

Scripts auxiliares para preparação de dados, conversão de modelos e automação de testes.

### `documentation`

Documentação técnica, diagramas, referências e materiais relacionados ao TCC.

## Tecnologias inicialmente consideradas

- Python
- PyTorch
- OpenCV
- Depth Anything V2
- ONNX Runtime
- Kotlin
- Android CameraX

As tecnologias poderão ser alteradas conforme os resultados obtidos durante os experimentos.

## Status

POC experimental em Python para analisar fotos com profundidade relativa, métrica
e segmentação. Inclui uma alternativa de ocupação frontal sem profundidade.
Há comparações exploratórias com fotos próprias; ainda sem validação independente.

### Executar a POC

Requer Python 3.10 ou superior. Na raiz do repositório:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[model]'
mobility-risk caminho/para/foto.jpg --output outputs/teste-01
```

Na primeira execução, os pesos do modelo são baixados do Hugging Face. A execução
usa GPU CUDA quando disponível e CPU nos demais casos. Para forçar CPU, use
`--device cpu`. A instalação padrão do PyTorch pode ser grande; para instalar uma
variante adequada ao equipamento, consulte as [instruções oficiais](https://pytorch.org/get-started/locally/).

Arquivos gerados:

- `overlay.png`: foto com região frontal em amarelo e candidatos em vermelho;
- `depth.png`: visualização de profundidade relativa, com regiões próximas mais claras;
- `depth.npy`: valores brutos do modelo, reutilizáveis nos experimentos;
- `candidates.png`: máscara dos pixels que satisfazem a regra;
- `report.json`: resultado, parâmetros, proporção de candidatos e tempos.

Cada execução sobrescreve os arquivos na pasta escolhida; use uma pasta por foto.
O tempo de profundidade inclui carregamento e eventual download do modelo, e não
deve ser apresentado como latência de inferência contínua.

### Como a regra inicial funciona

1. Estima profundidade inversa relativa com Depth Anything V2 Small: valores maiores
   representam elementos relativamente próximos, sem unidade em metros.
2. Normaliza cada mapa pelos percentis 2 e 98, limitando os valores a `[0, 1]`.
3. Usa como região frontal os 30% centrais da largura, entre 30% e 80% da altura.
4. Compara cada pixel central com a mediana das laterais na mesma linha. Isso busca
   reduzir alertas causados pelo gradiente de profundidade do chão.
5. Marca pixels com valor normalizado de pelo menos `0.60` e contraste lateral de
   pelo menos `0.15`. Se ocuparem ao menos 5% da região frontal, retorna
   `possivel_obstaculo`. Um mapa sem variação retorna `inconclusivo`.

Esses limiares são hipóteses iniciais, ainda sem calibração. Podem ser alterados:

```bash
mobility-risk foto.jpg --min-closeness 0.7 --min-contrast 0.2 --min-area-fraction 0.08
```

A regra compara profundidades relativas dentro da mesma imagem. Não mede distância,
não reconhece objetos e não estima probabilidade de colisão. A região retangular é
uma aproximação visual da área frontal, sem projeção geométrica da trajetória.
Paredes laterais próximas, obstáculos largos, ruído e mudanças na orientação da
câmera podem causar erros. A análise não contempla buracos ou escadas.
`sem_indicio_pela_regra` não significa caminho seguro. Esta POC serve para
experimentos controlados, não para orientar deslocamentos de pessoas.

### Diagnósticos e comparação com perfil do chão

O relatório agora separa os critérios em `diagnostics`:

- `closeness_pass_fraction`: fração da ROI que passou pelo limiar de proximidade;
- `contrast_pass_fraction`: fração que passou pelo contraste com a referência;
- `both_pass_fraction`: fração que passou pelos dois critérios simultaneamente;
- `contrast_percentiles`: distribuição do contraste na ROI;
- `reference_available` e `reason`: disponibilidade da referência e motivo da análise.

As frações usam todos os pixels da ROI como denominador; não são probabilidades.
Quando a referência não pode ser calculada, o contraste e a interseção são `null`,
o resultado é `inconclusivo` e a máscara fica vazia. Mapas sem variação também são
inconclusivos. Os relatórios anteriores não são atualizados automaticamente.

A regra padrão continua sendo `--rule lateral`. A alternativa experimental
`--rule floor` ajusta uma reta às medianas por linha na faixa central abaixo da
ROI (por padrão, os 20% inferiores da foto). Extrapola esse perfil para estimar
o valor esperado do chão nas linhas da ROI e compara os pixels com essa referência,
mantendo os mesmos critérios de proximidade e área mínima.

```bash
mobility-risk fotos/cadeirafrente2.jpeg --rule floor --min-closeness 0.20 \
  --depth-map outputs/comparacao/cadeirafrente2/original/depth.npy \
  --output outputs/chao-cadeira2
```

Essa alternativa supõe chão plano e visível na faixa inferior; não identifica o
chão semanticamente. Exige pelo menos oito linhas de amostra, inclinação do perfil
de pelo menos `0.05` (por altura normalizada) e mediana do erro de ajuste de até
`0.05` (na escala de profundidade normalizada). O ajuste e seus limites ficam em
`floor_fit`. Um ajuste aceito não comprova que a faixa contém chão: paredes,
móveis, câmera inclinada e oclusão podem provocar erros. Ao rejeitar o ajuste,
a regra retorna `inconclusivo`, sem mudar automaticamente para outra regra.

Para comparar as duas regras com os limiares `0.60` e `0.20` nos mapas já salvos:

```bash
python scripts/compare_rules.py
```

O script procura `outputs/comparacao/*/original/depth.npy` e a foto correspondente
em `fotos/`. Salva imagens e relatórios em `outputs/diagnostico/`, além de
`summary.csv`. Não baixa nem executa o modelo. Aceita `--images-dir`, `--maps-dir`
e `--output` para escolher outras pastas. Executar novamente sobrescreve os
resultados no destino; mantenha as fontes separadas do destino.

### Terceira abordagem: profundidade métrica para interiores

```bash
mobility-risk fotos/cadeirafrente2.jpeg --rule metric --output outputs/metric/cadeirafrente2
```

`--rule metric` seleciona automaticamente o modelo
`depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf`. A primeira execução baixa
pesos próprios dessa variante. As regras `lateral` e `floor` continuam usando o
modelo relativo anterior. Requer `transformers>=4.45` nas dependências opcionais
`.[model]`.

A regra métrica usa as seguintes hipóteses e limites iniciais, sem calibração:

1. Procura pixels na ROI com profundidade estimada de até **2,0 m**.
2. Ajusta o perfil do chão em profundidade inversa (`1/metros`), usando a faixa
   central abaixo da ROI. Não normaliza o mapa por percentis para decidir o alerta.
3. Mantém pixels pelo menos **0,30 m mais próximos** que a profundidade do chão
   prevista na mesma linha. Essa diferença é de profundidade, **não de altura**.
4. Agrupa candidatos em componentes com conectividade 4 e remove componentes
   menores que **1% da ROI**. Gera alerta se a área total restante atingir **5%**.

O perfil exige oito linhas, inclinação mínima `0.02` em `1/m` por altura
normalizada e mediana do erro de até `0.02` em `1/m`. Os valores são registrados em
`floor_fit`; são hipóteses experimentais. Linhas com profundidade de chão
extrapolada não positiva em `1/m` ficam sem suporte e não geram candidatos.
`floor_supported_fraction` informa essa cobertura. Sem ajuste aceito ou sem linha
suportada na ROI, o resultado é `inconclusivo`. Um ajuste aceito não demonstra que
a faixa realmente contém chão: móveis, paredes e oclusões ainda podem gerar erros.

Parâmetros disponíveis:

```bash
mobility-risk fotos/cadeirafrente2.jpeg --rule metric \
  --max-distance-m 2.0 --min-floor-gap-m 0.30 \
  --min-component-fraction 0.01 --min-area-fraction 0.05 \
  --output outputs/metric/cadeirafrente2
```

O JSON inclui `regions`, com caixa, área e percentis de profundidade estimada por
componente. As caixas e as máscaras representam regiões geométricas, não classes
de objetos. `raw_candidate_area_fraction` é a fração antes do filtro de componentes;
`candidate_area_fraction` é a fração após o filtro. `depth.png` usa escala fixa de
visualização, de 0 até `--max-distance-m`, com regiões mais próximas mais claras;
valores além do limite ficam pretos. Os valores originais permanecem em `depth.npy`.

As estimativas em metros precisam ser confrontadas com medidas reais. Não são
distâncias garantidas nem uma medição da altura do obstáculo. A ROI ainda é fixa e
não identifica a intenção de deslocamento. Essa abordagem não garante melhora em
outras fotos e não foi validada para navegação.

#### Evitar mistura de unidades

Cada nova execução salva `depth.meta.json`, com tipo de profundidade, origem do
modelo quando conhecida e tamanho da foto. Ao reutilizar `depth.npy`, o programa
confere esses metadados; para mapas antigos, consulta `report.json` na mesma pasta.
Mapas relativos são rejeitados pela regra métrica e vice-versa. Para um `.npy`
externo sem metadados, a regra métrica exige declaração explícita:

```bash
mobility-risk foto.jpeg --rule metric --depth-map mapa-em-metros.npy \
  --depth-kind metric_m --output outputs/mapa-externo
```

Não use essa opção para converter um mapa relativo: ela só declara sua unidade.
Arquivos externos sem unidade declarada continuam sendo tratados como relativos
pelas regras antigas, por compatibilidade. `--min-closeness` e `--min-contrast` são
exclusivos das regras relativas; os parâmetros em metros exigem `--rule metric`.

#### Decisão experimental por largura ocupada

O padrão continua `--decision-mode area`, com área final mínima de 5% da ROI.
A alternativa `--decision-mode width` substitui apenas a decisão final, usando
os mesmos candidatos de profundidade e os mesmos componentes filtrados:

```bash
mobility-risk fotos/cadeira1metro.jpeg --rule metric --decision-mode width \
  --max-distance-m 2.0 --min-width-fraction 0.30 --min-height-fraction 0.02 \
  --output outputs/teste-largura
```

Cada componente precisa ter uma faixa de linhas consecutivas em que os pixels
candidatos ocupem pelo menos 30% da largura da ROI. Nessas linhas, pelo menos 50%
da faixa central (entre 40% e 60% da largura da ROI) também deve estar ocupada.
A faixa precisa ter ao menos 2% da altura da ROI, nunca menos de duas linhas.
O cálculo usa pixels presentes, não a largura da caixa do componente. Componentes
separados não são somados para satisfazer a largura. Esses limites são hipóteses
experimentais, sem calibração ou equivalência com largura física de passagem.

No modo `width`, a área total de 5% deixa de ser a condição de alerta, mas o
filtro de componentes de 1% continua ativo. `--min-area-fraction` permanece no
relatório apenas para comparação diagnóstica nesse modo. O JSON informa
`decision.area_pass`, `decision.width_pass` e o modo selecionado. Cada região
inclui `width_support`, com suporte por linha e comprimento da faixa. A máscara
e o vermelho do overlay continuam mostrando todos os candidatos mantidos, mesmo
quando a regra final não emite alerta; não representam classes de objetos.

O critério pode rejeitar bordas laterais finas, mas também perder obstáculos
estreitos ou fragmentados. Ele não corrige mapas de profundidade nem produz
candidatos que tenham falhado nos filtros anteriores. A redução de área mínima
para 3% e a alternativa de largura foram comparadas com o padrão em 11 fotos,
com alcances de 2 m e 3 m, sem alterar automaticamente o padrão:

```bash
python scripts/evaluate_collection.py \
  --collection experiments/coleta-comparacao-largura.json \
  --profiles experiments/perfis-largura.json \
  --output outputs/comparacao-largura
```

São 66 análises sem nova inferência, usando os mapas métricos já salvos. Para
repetir, use outro destino, pois o script recusa sobrescrever resultados.
Veja [a análise da comparação](experiments/comparacao-largura.md).

#### Comparar com a coleta anterior

```bash
python scripts/compare_metric.py
```

O script usa as fotos identificadas pelos relatórios em
`outputs/diagnostico/*/lateral-0.20/report.json`. Executa a configuração métrica
padrão em cada uma e reúne as quatro configurações anteriores e a nova em
`outputs/metric/summary.csv`. Salva os novos artefatos por foto em `outputs/metric/`.
Use `--reuse-maps` para reanalisar mapas métricos já salvos, sem nova inferência;
os mapas faltantes são gerados. Aceita `--images-dir`, `--baseline-dir`, `--output`
e `--device`. A execução atual carrega o modelo por foto, então os tempos não são
um benchmark de inferência contínua. Os resultados da coleta estão descritos em
[comparacao-metrica-inicial.md](experiments/comparacao-metrica-inicial.md).

### Segmentação de objetos e abordagem híbrida

Instale as dependências opcionais de segmentação:

```bash
python -m pip install -e '.[objects]'
```

As opções `--rule objects` e `--rule hybrid` combinam profundidade métrica com
instâncias de YOLO11n-seg, pré-treinado em classes conhecidas. Os pesos são
baixados na primeira execução para `outputs/models/yolo11n-seg.pt`. Inferência é
local; as fotos não são enviadas a um serviço de reconhecimento.

```bash
mobility-risk fotos/cadeira2metros.jpeg --rule objects --max-distance-m 3.0 \
  --depth-map outputs/coleta02/baseline/cadeira2metros/depth.npy \
  --output outputs/teste-objetos
```

Para cada instância prevista, a decisão padrão exige:

- confiança de segmentação de pelo menos **0,35**;
- máscara dentro da ROI com ao menos **1% da área da ROI**;
- ao menos **10% da máscara total** dentro da ROI;
- ao menos **10% dos pixels da máscara na ROI** na faixa central (40% a 60% da
  largura da ROI);
- ao menos **10% dos pixels da máscara na ROI** dentro de `--max-distance-m`.

O valor padrão da distância continua 2 m. A confiança e a fração próxima podem
ser alteradas com `--min-object-confidence` e `--min-object-near-fraction`. Os
limites são hipóteses iniciais e ficam registrados no JSON. Não são probabilidades
de colisão. A segmentação é inicialmente executada com confiança de 0,15 (ou menor,
se solicitado na decisão) para permitir comparação posterior de limiares.

O modo `objects` agrupa partes pela instância prevista, mesmo desconectadas,
mantendo a máscara fornecida pelo modelo. Não preenche a caixa do objeto, mas a
própria máscara prevista pode conter fundo ou erros. Dispensa o perfil do chão e
os componentes de profundidade: a proximidade é avaliada dentro da máscara da
instância. Isso também significa que chão e paredes não são reconhecidos por
esse ramo. Classes desconhecidas, objetos não detectados e detecções incorretas
continuam sendo limitações. Sem nenhuma instância com confiança suficiente, o
resultado é `inconclusivo`, e não passagem livre.

O modo `hybrid` executa a regra métrica e o ramo por objetos. Emite alerta se
**qualquer um** emitir alerta. Sem alerta, se algum ramo for inconclusivo, a
combinação também é inconclusiva. Só retorna `sem_indicio_pela_regra` se ambos
retornarem esse resultado. Assim, um alerta geométrico de parede não é suprimido
pela ausência de classe conhecida. Essa união preserva também eventuais alertas
indevidos do ramo geométrico; não é um mecanismo de confirmação entre modelos.

```bash
mobility-risk fotos/cadeira2metros.jpeg --rule hybrid --max-distance-m 3.0 \
  --depth-map outputs/coleta02/baseline/cadeira2metros/depth.npy \
  --output outputs/teste-hibrido
```

Nos novos overlays: amarelo delimita a ROI; caixas ciano indicam instâncias
detectadas com confiança suficiente, mas sem alerta; caixas vermelhas indicam
instâncias com alerta. No ramo por objetos, o preenchimento vermelho marca a
**máscara inteira da instância dentro da ROI**, e não somente os pixels próximos.
`near.png` mostra os pixels próximos que sustentam os alertas por objetos.
No híbrido, a marcação também inclui o ramo geométrico quando este emite alerta.
As áreas marcadas têm significados diferentes entre os ramos e não medem eficácia.

O JSON registra classes previstas, confiança, sobreposição, fração próxima,
profundidades estimadas e motivos de rejeição. No híbrido, os relatórios dos dois
ramos estão em `branches`. As instâncias podem ser reutilizadas sem repetir o
segmentador:

```bash
mobility-risk fotos/cadeira2metros.jpeg --rule hybrid --max-distance-m 3.0 \
  --depth-map outputs/teste-objetos/depth.npy \
  --instances outputs/teste-objetos/instances.npz --output outputs/teste-cache
```

`instances.meta.json` confere o hash da foto e a resolução, registra o hash dos
pesos e impede baixar a confiança de decisão abaixo do limiar usado para gerar
o cache. Não converte máscaras de outra imagem. A medição de tempo separa leitura
da profundidade, segmentação (incluindo carregamento ou cache) e análise; não é FPS.

Para comparar geometria, objetos e híbrido com limites de 2 m e 3 m nas 11 fotos:

```bash
python scripts/compare_objects.py
```

O script reutiliza os mapas existentes e executa a segmentação uma vez por foto,
reutilizando as mesmas instâncias nas demais configurações. Aceita `--instances-dir`
com uma pasta contendo `<nome>/instances.npz` para evitar inferências já feitas.
Salva 66 análises, CSV, manifestos e snapshot do código em
`outputs/comparacao-objetos/`. Destino não vazio é recusado; para repetir, escolha
outro `--output`. Veja [a análise desta comparação](experiments/comparacao-objetos.md).

Referência da integração: [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11/)
e [segmentação de instâncias](https://docs.ultralytics.com/tasks/segment/).

### Ocupação frontal sem profundidade

`--rule occupancy` usa somente a segmentação e a posição das máscaras na imagem.
Não carrega o modelo de profundidade, não lê mapas e não gera distâncias.

```bash
python -m pip install -e '.[segmentation]'
mobility-risk fotos/cadeira2metros.jpeg --rule occupancy --output outputs/ocupacao-teste
```

Quem já instalou `.[objects]` também tem as dependências necessárias. A regra
compartilha com o ramo por objetos os critérios espaciais: confiança mínima de
0,35, ao menos 1% da área da ROI por instância, ao menos 10% da máscara total
dentro da ROI e ao menos 10% dos pixels da máscara na ROI na faixa central.
Retira apenas a condição de profundidade. A caixa é desenhada para visualização;
a decisão usa pixels da máscara, sem preencher a caixa ou criar uma zona física.

As proporções `image_area_fraction` e `roi_area_fraction` por instância informam
tamanho aparente. `occupancy_area_fraction` é a união das máscaras aceitas na ROI,
sem contar pixels sobrepostos duas vezes. Esses números não medem distância,
probabilidade de colisão ou eficácia. Em particular, um objeto ao fundo pode
ocupar a região frontal e gerar alerta sem estar fisicamente próximo.

Os estados têm nomes próprios para evitar confundir ocupação com proximidade:

- `ocupacao_frontal_detectada`: ao menos uma instância passou pelos critérios;
- `sem_ocupacao_pela_regra`: há reconhecimento com confiança suficiente, mas nenhuma
  instância passou pelos critérios espaciais; não significa passagem livre;
- `inconclusivo`: nenhuma instância reconhecida com confiança suficiente.

Cada execução salva `overlay.png`, a máscara `occupancy.png`, `report.json` e as
instâncias com metadados. Não há `depth.npy`, `depth.png` ou `near.png`. O overlay
usa amarelo para ROI, vermelho para ocupação e ciano para instâncias confiáveis
que não passaram pelos critérios. Os rótulos são as classes previstas, não
anotações verificadas de cada objeto.

É possível reutilizar as máscaras anteriores, sem executar nenhum modelo:

```bash
mobility-risk fotos/cadeira2metros.jpeg --rule occupancy \
  --instances outputs/comparacao-objetos/objects-2m/cadeira2metros/instances.npz \
  --output outputs/ocupacao-cache
```

Parâmetros opcionais: `--min-object-confidence`, `--min-occupancy-fraction`,
`--min-occupancy-overlap` e `--min-occupancy-central-fraction`. Mapas de profundidade,
limiares em metros e opções das outras decisões são rejeitados. Destinos que
contenham artefatos de profundidade também são rejeitados; escolha uma pasta nova.
As máscaras em cache continuam exigindo a mesma imagem, resolução e confiança
compatível com a inferência que gerou o cache.

Para comparar nas 11 fotos, mantendo exatamente as mesmas máscaras e os mesmos
critérios espaciais:

```bash
python scripts/compare_occupancy.py
```

O script lê as máscaras de `outputs/comparacao-objetos/objects-2m/` e as seis
configurações anteriores em `outputs/comparacao-objetos/summary.csv`. Produz **11
análises novas**, mais **66 referências históricas** no CSV combinado, em
`outputs/comparacao-ocupacao/`. Não faz nova inferência nem lê os mapas de
profundidade referenciados na coleta. Os nomes das imagens não entram na decisão.
Use um novo `--output` para repetir, pois o script recusa sobrescrever a comparação.
Veja [a análise dos resultados](experiments/comparacao-ocupacao.md).

### Região de atenção com margem ao redor do objeto

`--rule attention` usa a caixa delimitadora da máscara e adiciona uma margem 2D
antes de avaliar a sobreposição com a região frontal. O padrão é **15% da largura
e da altura originais em cada lado**. Uma caixa de 100x200 pixels recebe 15 pixels
à esquerda/direita e 30 acima/abaixo, antes do recorte nos limites da imagem.
Arredonda-se para fora para obter pixels inteiros. A margem pode variar de 0 a 1.

```bash
mobility-risk fotos/cadeira2metros.jpeg --rule attention --attention-margin 0.15 \
  --output outputs/teste-atencao
```

É possível usar `--instances` com o cache já gerado, como em `occupancy`, sem
executar o segmentador. A regra não usa profundidade e rejeita parâmetros em
metros. `--min-attention-fraction` controla a parcela mínima da ROI coberta pela
região de atenção (padrão 1%); `--min-attention-overlap`, a parcela mínima da
caixa expandida dentro da ROI (10%); `--min-attention-central-fraction`, o suporte
central da interseção (10%). Mantém confiança mínima de 0,35. O alerta exige todas
as condições por instância; uma simples interseção de um pixel não basta.

O overlay mostra:

- retângulo amarelo: ROI frontal fixa;
- caixa vermelha/ciano: caixa do objeto, conforme acione ou não a regra;
- contorno tracejado laranja: caixa expandida para cada instância confiável;
- preenchimento vermelho: interseção aceita da região de atenção com a ROI.

`attention.png` salva a união dessas interseções. `objects.png` mostra apenas as
máscaras reais das instâncias que acionaram atenção, recortadas à ROI. O JSON
separa `attention_area_fraction` de `object_occupancy_area_fraction` e registra
caixa original, caixa expandida, margem em pixels e motivos de rejeição por objeto.
Os estados são `regiao_atencao_acionada`, `sem_acionamento_pela_regra` e
`inconclusivo`. Não há distância ou indicação de aproximação física.

Uma margem zero ainda usa o interior da caixa inteira e pode incluir fundo ou
buracos do objeto. Por isso, `attention --attention-margin 0` não equivale à
regra `occupancy`, que usa a máscara. Aumentar a margem também altera as razões
de sobreposição; não há garantia de que toda margem maior aumente os acionamentos.
Paredes ou classes não reconhecidas continuam sem cobertura pelo segmentador.

Para comparar as mesmas 11 fotos com máscara, caixa sem margem e margens de 15%
e 30%:

```bash
python scripts/compare_attention.py
```

São 44 análises sem inferência nem mapas. As opções `--collection`,
`--instances-dir`, `--margins` e `--output` permitem escolher entradas e margens.
Destinos não vazios são recusados. Nesta amostra, os acionamentos não mudaram,
apesar do aumento das áreas; veja [a análise da comparação](experiments/comparacao-atencao.md).

### Testes sem baixar o modelo

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Os testes usam mapas sintéticos para verificar obstáculo central, obstáculo lateral,
gradiente do chão, mapa constante, entradas inválidas e geração dos arquivos. Não
medem a eficácia do modelo em fotografias reais.

É possível testar novos limiares reutilizando um mapa já gerado:

```bash
mobility-risk foto.jpg --depth-map outputs/teste-01/depth.npy --output outputs/teste-02
```

O `.npy` deve conter profundidade **inversa relativa**, com as mesmas dimensões da
foto após correção da orientação EXIF. Um mapa em metros não é compatível com as
regras `lateral` e `floor`; ele exige `--rule metric`. Ao reutilizar mapas, o
relatório registra a origem e mantém `model` vazio, porque não houve inferência;
`source_model` preserva a origem quando conhecida nos metadados.

Referência de integração: [Depth Anything V2 Small no Hugging Face](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf).
