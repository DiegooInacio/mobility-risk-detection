# Scripts

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
