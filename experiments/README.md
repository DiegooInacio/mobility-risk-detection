# Avaliação inicial

Objetivo: investigar se a heurística distingue obstáculos centrais de cenas sem
obstáculos frontais, em ambiente interno controlado.

1. Fotografar corredor livre, caixa/cadeira ao centro e obstáculo na lateral,
   mantendo inicialmente posição e orientação da câmera consistentes.
2. Registrar manualmente se há obstáculo frontal, além de iluminação, posição do
   objeto e distância medida para contextualização. A POC não estima metros.
3. Separar fotos para ajustar os limiares de outras fotos para avaliar a regra.
   Evitar distribuir fotos quase idênticas da mesma captura entre os dois grupos.
4. Executar a ferramenta, escolhendo uma pasta de saída por foto.
5. Contar verdadeiros positivos, falsos positivos, falsos negativos, verdadeiros
   negativos e resultados inconclusivos, sem descartar os inconclusivos do registro.
6. Guardar exemplos de falhas e os parâmetros usados junto aos resultados.

Os testes sintéticos de `tests/` verificam propriedades da implementação. A
validação da hipótese depende desse conjunto separado de fotos reais.
