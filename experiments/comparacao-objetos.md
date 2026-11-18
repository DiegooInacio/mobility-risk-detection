# Segmentação de instâncias com profundidade métrica

## Objetivo e implementação

A comparação anterior mostrou candidatos desconectados na cadeira mais distante.
Foi adicionado o segmentador pré-treinado YOLO11n-seg para investigar agrupamento
por instância, em vez de supor que cada componente de profundidade seja um objeto.
Foram implementadas duas novas regras, sem mudar o padrão da aplicação:

- `objects`: decide a partir de máscaras previstas e profundidade métrica;
- `hybrid`: emite alerta se a regra geométrica ou a regra por objetos emitir.

O modelo de profundidade é o mesmo Depth Anything V2 Metric Indoor Small. A
segmentação é local e os mapas métricos existentes foram reutilizados. Não foi
treinado ou ajustado um modelo com as fotos do projeto.

## Regra por instância

Cada máscara deve satisfazer todas as condições fixas:

| Critério | Limiar |
|---|---|
| Confiança do segmentador | Pelo menos 0,35 |
| Pixels da máscara dentro da ROI | Pelo menos 1% da área da ROI |
| Parcela da máscara total dentro da ROI | Pelo menos 10% |
| Parcela da máscara na ROI dentro da faixa central | Pelo menos 10% |
| Pixels da máscara na ROI até a distância máxima | Pelo menos 10% |

A faixa central corresponde a 40%–60% da largura da ROI; a ROI continua sendo o
mesmo retângulo anterior. Cada instância é avaliada separadamente. Partes
desconectadas de uma mesma máscara são agrupadas, sem preencher artificialmente
os buracos da máscara. A máscara prevista pode, porém, incluir fundo, ter buracos
incorretos ou omitir partes do objeto.

O ramo dispensa perfil de chão, componentes conectados e área total mínima de 5%.
Não há segmentação semântica de todas as superfícies: chão, paredes e objetos
desconhecidos podem não ter classe reconhecida. Confiança de segmentação não é
probabilidade de colisão. As distâncias continuam estimadas e sem calibração.

Sem nenhuma instância acima da confiança mínima, o resultado é inconclusivo. A
ausência de objeto detectado não é interpretada como passagem livre.

## Modo híbrido

Preserva a regra geométrica para superfícies ou objetos sem classe conhecida.
Seu operador é união, não confirmação entre modelos:

1. Se qualquer ramo alerta, a combinação alerta.
2. Sem alerta, se qualquer ramo for inconclusivo, a combinação é inconclusiva.
3. Só retorna sem indício quando ambos os ramos retornam sem indício.

Isso preserva também alertas geométricos possivelmente indevidos. A regra não
usa a ausência de classe para remover um alerta de parede. Os dois relatórios
ficam disponíveis separadamente em `branches`.

## Experimento nas 11 imagens

Compararam-se geometria, objetos e híbrido com distâncias máximas de 2 m e 3 m,
totalizando 66 análises. As máscaras de cada foto foram geradas uma vez e
reutilizadas nas configurações. Não foram ajustados parâmetros por imagem.

S = alerta; N = sem indício pela respectiva regra; I = inconclusivo. N não significa
segurança. Os nomes das cenas não são usados pelo algoritmo para decidir.

| Foto | Geometria 2 m | Objetos 2 m | Híbrido 2 m | Geometria 3 m | Objetos 3 m | Híbrido 3 m |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| cadeira1metro | S | S | S | S | S | S |
| cadeira1meiometro | S | S | S | S | S | S |
| cadeira2metros | N | N | N | N | S | S |
| cadeiraadireita1 | N | I | I | N | I | I |
| parciallivre1 | N | N | N | N | N | N |
| livrechichi1 | N | N | N | N | N | N |
| cadeirafrente1 | S | S | S | S | S | S |
| cadeirafrente2 | S | S | S | S | S | S |
| cadeiralado1 | S | S | S | S | S | S |
| livre1 | N | I | I | S | I | S |
| livre2 | N | I | I | S | I | S |

### Evidência principal

Em `cadeira2metros`, o segmentador prevê `chair` com confiança aproximada de 0,85.
Com alcance de 2 m, nenhum pixel dessa máscara na ROI está dentro do limite
estimado; a nova abordagem não corrige esse gargalo de profundidade. Com alcance
de 3 m, cerca de 15,7% desses pixels estão dentro do limite e a regra por instância
gera alerta. A regra geométrica de área de 5% não gerava alerta nessa mesma
configuração, embora tivesse candidatos: a área permanecia em aproximadamente
3,57% da ROI, fragmentada em componentes.

Esse resultado demonstra um efeito do agrupamento/decisão por instância nesta
imagem. Não demonstra que o alcance padrão deveria passar a 3 m, nem corrige a
distância do modelo: a distância nominal de 2 m foi informada como aproximada.

### Cobertura e falhas observadas

- Em `cadeiraadireita1`, a predição disponível foi `dining table` com confiança
  aproximada de 0,328, abaixo de 0,35. O ramo por objetos é inconclusivo; não se
  registra o caso como acerto de reconhecimento de cadeira lateral.
- Em `livre1`, a predição `toilet` teve confiança aproximada de 0,343 e também
  foi rejeitada. Em `livre2`, não houve instância detectada. Os resultados do ramo
  por objetos são inconclusivos. A ausência de vermelho não prova que uma parede
  seja segura ou que tenha sido classificada como parede.
- Com alcance de 3 m, o híbrido mantém os alertas geométricos nas duas imagens
  acima. Em `livre2`, há uma parede frontal; sua classificação como alerta
  indevido depende da direção pretendida e do critério de rotulagem.
- Em `livrechichi1`, houve predição `dog`, fora da faixa central e sem pixels até
  o limite estimado de 3 m. O usuário confirmou que o cachorro está fora do
  caminho pretendido. Não é evidência de que todo animal lateral será tratado
  corretamente.
- Em `cadeiralado1`, aparecem predições `chair` e `bench` com máscaras que passam
  pelos critérios. Não se deve concluir que são dois obstáculos distintos sem
  anotação manual. Máscaras sobrepostas são unidas, sem contar área duas vezes.

## Visualização e artefatos

- `overlay.png`: ROI amarela; caixas ciano para instâncias com confiança suficiente
  sem alerta; caixas vermelhas para instâncias com alerta. O preenchimento vermelho
  do ramo por objetos cobre a máscara inteira do objeto dentro da ROI.
- `near.png`: somente os pixels próximos das instâncias com alerta; permite
  distinguir o suporte de profundidade da máscara agrupada.
- `instances.npz` e `instances.meta.json`: máscaras, classes, confiança, hash da
  imagem e dos pesos, resolução e parâmetros de inferência. O cache não permite
  usar as máscaras de outra foto nem pedir confiança abaixo do limiar de geração.
- `report.json`: decisões e rejeições por instância; ramos separados no híbrido;
  tempos de leitura de profundidade, segmentação e análise.
- `summary.csv`, `run.json` e `source_snapshot/`: comparação e registro do código.

As proporções de área não têm o mesmo significado entre métodos: a geometria
marca candidatos de profundidade, enquanto o ramo por objetos marca a máscara
agrupada da instância aceita. Não se usa área marcada como medida de qualidade.

## Verificação e conclusão

Os 34 testes automatizados passaram. Além dos cenários anteriores, cobrem partes
desconectadas de uma instância, fração próxima por objeto, rejeição lateral,
confiança insuficiente, cache associado à foto, sobreposição sem contagem dupla,
preservação de alertas geométricos e integração dos seis perfis com uma única
inferência de segmentação por foto.

Há um ganho exploratório no agrupamento da cadeira mais distante com alcance
estimado de 3 m. Permanecem a dependência da profundidade, a cobertura limitada
das classes, erros de reconhecimento e casos inconclusivos. A amostra é pequena,
conhecida no desenvolvimento e sem distâncias de referência medidas. Não se
atribui eficácia geral nem se altera automaticamente a configuração padrão.

## Reprodução

```bash
python -m pip install -e '.[objects]'
python scripts/compare_objects.py
```

Para repetir sem refazer as máscaras, escolhendo novo destino:

```bash
python scripts/compare_objects.py \
  --instances-dir outputs/comparacao-objetos/objects-2m \
  --output outputs/comparacao-objetos-repeticao
```

Referências: [YOLO11](https://docs.ultralytics.com/models/yolo11/) e
[segmentação de instâncias Ultralytics](https://docs.ultralytics.com/tasks/segment/).
