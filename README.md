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

POC inicial em Python para analisar fotos, gerar profundidade relativa e destacar
possíveis obstáculos na região frontal. Ainda sem validação com cenas reais.

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
foto após correção da orientação EXIF. Um mapa em metros não é compatível com essa
regra. Ao reutilizar mapas, o relatório registra a origem e não atribui um modelo.

Referência de integração: [Depth Anything V2 Small no Hugging Face](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf).
