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

Projeto em fase inicial de pesquisa e definição da arquitetura.
