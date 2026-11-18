# Região de atenção 2D com margem

## Implementação

Adicionada a regra `--rule attention`: obtém a caixa delimitadora da máscara de
cada instância reconhecida e a expande proporcionalmente à largura e à altura.
O padrão é 15% em cada lado; arredonda-se a margem para fora e recorta-se a caixa
nos limites da imagem. A caixa de origem é derivada dos pixels da máscara, de
forma consistente com as visualizações das etapas anteriores.

A região frontal e a faixa central mantêm os limites anteriores. A decisão exige
confiança de 0,35, interseção de ao menos 1% da ROI, ao menos 10% da caixa expandida
dentro da ROI e suporte central de ao menos 10% dos pixels da interseção. Os
critérios são aplicados por instância. Ausência de reconhecimento confiável é
inconclusiva. São registrados os limites, proporções e motivos de rejeição.

O overlay distingue o objeto da região expandida: caixa original vermelha/ciano,
região de atenção em tracejado laranja, ROI amarela e interseção aceita preenchida
em vermelho. `attention.png` contém as interseções das regiões aceitas;
`objects.png`, as máscaras dos objetos correspondentes dentro da ROI. A expansão
pode acionar atenção mesmo quando a máscara não chega ao centro, mas não determina
proximidade física ou movimento de aproximação em uma foto isolada.

## Experimento

Foram usadas exatamente as máscaras salvas das 11 fotos. Compararam-se quatro
perfis, sem alterar parâmetros por foto ou executar modelos:

1. Ocupação pela máscara, referência da etapa anterior.
2. Caixa com margem zero, para separar o efeito do preenchimento da caixa.
3. Caixa com margem de 15% por lado.
4. Caixa com margem de 30% por lado.

Uma caixa com margem zero não equivale à máscara: ela inclui todo o retângulo,
mesmo onde existem buracos ou fundo. Foram produzidas 44 análises. O número de
fotos independentes continua sendo 11 e todas já são conhecidas no desenvolvimento.

## Resultados

As decisões por imagem foram iguais entre os perfis, considerando a correspondência
entre ocupação e acionamento de atenção: sete positivas, uma negativa segundo a
regra e três inconclusivas. Não são contagens de acertos ou estimativas de eficácia.

| Foto | Ocupação por máscara | Margem 0% | Margem 15% | Margem 30% |
|---|---:|---:|---:|---:|
| cadeira1metro | 67,57% | 100,00% | 100,00% | 100,00% |
| cadeira1meiometro | 33,01% | 63,92% | 78,25% | 91,50% |
| cadeira2metros | 23,91% | 41,41% | 63,13% | 75,38% |
| cadeiraadireita1 | I | I | I | I |
| parciallivre1 | 3,41% | 5,35% | 9,06% | 13,75% |
| livrechichi1 | N | N | N | N |
| cadeirafrente1 | 61,79% | 86,50% | 100,00% | 100,00% |
| cadeirafrente2 | 63,86% | 85,00% | 100,00% | 100,00% |
| cadeiralado1 | 11,20% | 43,89% | 71,67% | 96,11% |
| livre1 | I | I | I | I |
| livre2 | I | I | I | I |

Percentuais indicam a área da ROI coberta pela união das regiões aceitas. Na
primeira coluna são máscaras; nas demais, caixas preenchidas/expandidas. Esses
valores têm significados distintos e não são distâncias, confiança ou qualidade.
I = inconclusivo; N = sem acionamento pela regra.

## Interpretação

- As margens ampliam a região desenhada e a interseção, mas não recuperaram novas
  detecções nem removeram alertas nesta amostra. Não há evidência de melhora geral
  por adicionar 15% ou 30%.
- A cadeira ao fundo em `parciallivre1` continua acionando atenção. Sua área
  selecionada cresce, mas não há informação de que o usuário esteja perto dela.
- As três imagens inconclusivas permanecem assim porque a margem não corrige a
  ausência de reconhecimento confiável.
- A parcela da ROI pode atingir 100% por preenchimento/expansão da caixa mesmo
  que os pixels reais do objeto ocupem menos. Isso não significa bloqueio físico
  de 100% da passagem.
- A expansão pode afetar as razões de sobreposição de maneiras diferentes em
  outras imagens; não se deve presumir monotonicidade do alerta com a margem.

O resultado implementa uma zona de atenção na imagem. Para avaliar aproximação
física seriam necessárias outras evidências, como distâncias medidas sob condições
definidas. A própria intenção de deslocamento e a utilidade de avisar sobre
objetos ao fundo precisam ser definidas antes de rotular novas cenas.

## Reprodução e verificação

```bash
mobility-risk fotos/cadeira2metros.jpeg --rule attention --attention-margin 0.15 \
  --instances outputs/comparacao-objetos/objects-2m/cadeira2metros/instances.npz \
  --output outputs/teste-atencao

python scripts/compare_attention.py
```

O script salva `summary.csv`, `run.json`, `source_snapshot/` e artefatos de cada
perfil em `outputs/comparacao-atencao/`. Recusa destino não vazio; use outro
`--output` para repetir. Nenhuma configuração padrão das regras anteriores foi
alterada.

Os 49 testes passaram. Os novos casos incluem expansão com recorte nas bordas,
arredondamento por pixel, margem que alcança o centro, distinção entre máscara e
caixa, sobreposição sem contagem dupla, baixa confiança, parâmetros inválidos e
comparação sem mapas ou inferência. No teste sintético, a margem pode mudar a
decisão de um objeto lateral; esse efeito ainda não foi observado nas 11 fotos.
