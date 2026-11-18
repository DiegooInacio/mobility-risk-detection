"""Relatório complementar A4 em preto e branco: ocupação frontal sem profundidade."""

from collections import Counter
from datetime import datetime

from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer, Table, TableStyle

from generate_poc_report import ROOT, footer, p, pct, table
from generate_progress_report import load_rows, monochrome_figure

OUTPUT = ROOT / "documentation/relatorio-poc-ocupacao-frontal.pdf"


def main():
    rows = load_rows("outputs/comparacao-ocupacao/summary.csv", 77)
    current = [row for row in rows if row["profile"] == "occupancy"]
    if len(current) != 11 or len({row["image"] for row in current}) != 11:
        raise ValueError("O relatório requer os 11 resultados distintos de ocupação.")
    states = Counter(row["status"] for row in current)
    lookup = {(row["image"], row["profile"]): row for row in rows}
    legend = {"possivel_obstaculo": "S", "sem_indicio_pela_regra": "N",
              "inconclusivo": "I", "ocupacao_frontal_detectada": "O", "sem_ocupacao_pela_regra": "N"}
    date = datetime.now().strftime("%d/%m/%Y")
    story = [
        p("Mobility Risk Detection", "TitlePT"),
        p("Ocupação frontal sem profundidade", "HeadingPT"),
        p(f"Relatório complementar para discussão com o orientador<br/>"
          f"Data: {date} | Referência anterior: commit a8af775", "SmallPT"),
        Spacer(1, 8),
        p("1. Objetivo desta etapa", "HeadingPT"),
        p("Investigar uma simplificação da POC: identificar objetos reconhecidos que "
          "ocupam uma região frontal da imagem, usando apenas segmentação. A pergunta "
          "passa a ser se há ocupação visual nessa região. Não se estima distância "
          "em metros, proximidade física ou probabilidade de colisão."),
        p("A motivação foi retirar a dependência da profundidade, que bloqueava "
          "algumas detecções. A nova regra foi implementada como alternativa, mantendo "
          "as abordagens anteriores para comparação. A caixa em torno do objeto é "
          "uma representação na imagem, não uma zona física ao redor dele."),
        p("2. Como a regra funciona", "HeadingPT"),
        p("O segmentador YOLO11n-seg fornece máscaras, caixas, classes previstas e "
          "confiança. Cada máscara é comparada com a região de interesse (ROI). "
          "A decisão usa pixels da máscara, sem preencher a caixa. Objetos aceitos "
          "são destacados e suas áreas são unidas sem contar sobreposições duas vezes."),
        table([
            ["Critério por instância", "Configuração fixa"],
            ["Confiança mínima", "0,35"],
            ["Área mínima ocupada dentro da ROI", "1% da área da ROI"],
            ["Parcela da máscara total dentro da ROI", "Pelo menos 10%"],
            ["Suporte da máscara na faixa central", "Pelo menos 10% dos pixels da máscara na ROI"],
            ["ROI e faixa central", "ROI: 35%–65% da largura e 30%–80% da altura; faixa central: 40%–60% da largura da ROI"],
        ], [245, 225]),
        Spacer(1, 9),
        p("Os critérios espaciais são os mesmos da regra anterior por objetos; foi "
          "retirada a condição de distância. Os limites continuam experimentais, "
          "sem ajuste individual por foto. Uma imagem nova usa apenas o segmentador; "
          "máscaras salvas permitem executar a análise sem nenhum modelo."),
        PageBreak(),
        p("3. Procedimento e resultados", "HeadingPT"),
        p("Foram reutilizadas as mesmas máscaras de 11 fotos conhecidas no "
          "desenvolvimento. Houve 11 análises novas de ocupação e a leitura de 66 "
          "referências históricas. As 77 linhas do CSV combinado não representam "
          "77 imagens independentes ou novas inferências. A comparação não executou "
          "modelos nem leu mapas de profundidade."),
        p("S = alerta da regra por objetos com profundidade; O = ocupação frontal "
          "detectada; N = ausência de indício/ocupação segundo a respectiva regra; "
          "I = inconclusivo. Os estados respondem a perguntas diferentes. Nenhum N "
          "significa passagem segura.", "SmallPT"),
    ]
    matrix = [["Foto", "Objetos<br/>2 m", "Objetos<br/>3 m", "Ocupação", "Área da ROI<br/>ocupada"]]
    for row in current:
        image = row["image"]
        name = image.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        matrix.append([name, legend[lookup[image, "objects-2m"]["status"]],
                       legend[lookup[image, "objects-3m"]["status"]], legend[row["status"]],
                       pct(row["region_fraction"])])
    story += [table(matrix, [155, 65, 65, 75, 110]), Spacer(1, 10),
              p(f"Nesta coleta, houve ocupação em {states['ocupacao_frontal_detectada']} fotos, "
                f"ausência de ocupação pela regra em {states['sem_ocupacao_pela_regra']} e "
                f"resultado inconclusivo em {states['inconclusivo']}. Essas contagens "
                "descrevem saídas, não acertos, falsos positivos ou acurácia."),
              p("As cinco cadeiras frontais foram sinalizadas. A cadeira antes "
                "descartada pelo limite de 2 m passou a gerar ocupação. Entretanto, "
                "a cadeira distante ao fundo de parciallivre1 também gerou ocupação. "
                "Isso demonstra a retirada do filtro de profundidade, não a resolução "
                "da estimativa de proximidade."),
              p("A ocupação das três cadeiras da nova coleta foi 67,57%, 33,01% e "
                "23,91%. A tendência de tamanho aparente é observável nessas imagens, "
                "mas suas distâncias são aproximadas. Não se pode converter esses "
                "percentuais em metros ou faixas confiáveis de perto/longe.", "SmallPT"),
              PageBreak(),
              p("4. Exemplos visuais", "HeadingPT"),
              p("Retângulo: região de interesse. Hachuras: máscara selecionada pela "
                "respectiva regra. A linha superior compara a mesma foto antes e "
                "depois da retirada da profundidade. A linha inferior mostra uma "
                "limitação e um resultado inconclusivo. Ausência de hachuras não "
                "atesta que a passagem está livre.", "SmallPT")]
    panels = []
    examples = [
        [("Cadeira — objetos até 2 m", "outputs/comparacao-objetos/objects-2m/cadeira2metros", "candidates.png", "Sem indício pela regra métrica"),
         ("Mesma cadeira — ocupação", "outputs/comparacao-ocupacao/occupancy/cadeira2metros", "occupancy.png", "Ocupação frontal detectada")],
        [("Cadeira ao fundo — parciallivre1", "outputs/comparacao-ocupacao/occupancy/parciallivre1", "occupancy.png", "Ocupação, sem afirmar proximidade"),
         ("Parede frontal — livre2", "outputs/comparacao-ocupacao/occupancy/livre2", "occupancy.png", "Inconclusivo: sem instância confiável")],
    ]
    for row in examples:
        cells = []
        for title, path, mask, caption in row:
            cells.append([p(f"<b>{title}</b>", "CaptionPT"),
                          monochrome_figure(path, mask_name=mask), p(caption, "CaptionPT")])
        panels.append(cells)
    figures = Table(panels, colWidths=[235, 235])
    figures.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story += [figures,
              p("A presença de objetos ao fundo é compatível com ocupação na imagem, "
                "mas pode gerar alertas indesejados se o objetivo for apenas avisar "
                "sobre obstáculos próximos. Paredes e classes desconhecidas não "
                "passam a ser reconhecidas por esta simplificação.", "SmallPT"),
              PageBreak(),
              p("5. Conclusões e limites", "HeadingPT"),
              p("A POC agora dispõe de uma alternativa funcional de ocupação frontal "
                "sem profundidade. Ela remove uma etapa de processamento e sinaliza "
                "objetos que o filtro métrico descartava, mas também sinaliza objetos "
                "ao fundo. Continua dependente da cobertura e dos erros do segmentador. "
                "Não foi demonstrada eficácia geral nem desempenho no smartphone."),
              p("Os 42 testes automatizados passaram, incluindo independência da "
                "profundidade e rejeição de parâmetros em metros nessa regra. As 22 "
                "decisões e máscaras anteriores por objetos foram preservadas. Os "
                "testes verificam o código; as 11 fotos conhecidas não substituem "
                "uma avaliação independente."),
              p("6. Pontos para alinhar com o orientador", "HeadingPT"),
              table([
                  ["Ponto", "Decisão necessária"],
                  ["Objetivo da versão", "Identificar objetos frontais ou afirmar proximidade? A regra atual sustenta apenas o primeiro recorte."],
                  ["Objeto distante ao fundo", "Sua presença deve gerar aviso ou é indesejada? Definir antes de rotular novas fotos."],
                  ["Região de passagem", "Explicitar a direção pretendida e como tratar objetos laterais ou paredes na região central."],
                  ["Resultado inconclusivo", "Registrar como resultado próprio; não contabilizar automaticamente como passagem livre ou acerto."],
              ], [150, 320]),
              p("7. Proposta de avaliação seguinte — ainda não realizada", "HeadingPT"),
              p("Coletar 20 fotos novas em dois ou três ambientes: seis com objeto "
                "central, seis com objeto lateral, quatro com passagem livre e "
                "quatro com objeto distante ao fundo. Incluir objetos diferentes "
                "das cadeiras atuais e padronizar câmera, altura e orientação. "
                "Anotar se o alerta é desejável antes de executar, manter os "
                "parâmetros fixos e registrar alertas úteis, indesejados, ausências "
                "de alerta e casos inconclusivos."),
              p("Reprodução e materiais", "HeadingPT"),
              p("Análise: <font face='Courier'>python scripts/compare_occupancy.py</font><br/>"
                "Testes: <font face='Courier'>python -m unittest discover -s tests -v</font><br/>"
                "Dados: <font face='Courier'>outputs/comparacao-ocupacao/summary.csv</font><br/>"
                "Texto técnico: <font face='Courier'>experiments/comparacao-ocupacao.md</font><br/>"
                "Modelo: https://docs.ultralytics.com/models/yolo11/", "SmallPT")]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=(210*mm, 297*mm),
                            leftMargin=22*mm, rightMargin=22*mm,
                            topMargin=18*mm, bottomMargin=24*mm,
                            title="Mobility Risk Detection — Ocupação frontal sem profundidade",
                            author="Projeto Mobility Risk Detection")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
