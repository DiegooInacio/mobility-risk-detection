# Documentation

## Relatórios da POC

- [Comparação inicial de regras](relatorio-poc-comparacao-regras.pdf): profundidade
  relativa, referência lateral e perfil do chão.
- [Profundidade métrica e segmentação](relatorio-poc-profundidade-metrica-e-segmentacao.pdf):
  consolidação dos experimentos posteriores ao commit `e101bda`, com 11 imagens,
  critérios de área/largura, segmentação por instância e união híbrida.
- [Ocupação frontal sem profundidade](relatorio-poc-ocupacao-frontal.pdf): complemento
  sobre a simplificação para segmentação e critérios espaciais, com resultados,
  limites e pontos de alinhamento antes da próxima coleta.

Os PDFs usam A4 em preto e branco, com imagens em tons de cinza e marcações em
hachuras. Para gerar o segundo relatório, instale `.[report]` e execute
`python scripts/generate_progress_report.py`. São necessários os CSVs, relatórios,
máscaras e fotos locais descritos nos scripts de comparação.

Para gerar o complemento de ocupação, execute
`python scripts/generate_occupancy_report.py`. Ele usa as saídas locais das
comparações por objetos e por ocupação, sem executar modelos. O plano de 20 fotos
nesse documento é uma proposta de próxima avaliação, não um experimento realizado.

Esta pasta será utilizada para armazenar materiais relacionados à documentação do projeto e do TCC.

Poderá conter:

- diagramas de arquitetura;
- fluxos de desenvolvimento;
- trabalhos relacionados;
- referências bibliográficas;
- documentação técnica;
- anotações de reuniões;
- PDFs utilizados durante a definição do projeto;
- versões preliminares de textos do artigo.

Documentos grandes ou temporários poderão ser mantidos fora do repositório quando necessário.
