"""Gera relatório A4 em tons de cinza a partir dos resultados locais da POC."""

import csv
from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as PDFImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "outputs/diagnostico"
OUTPUT = ROOT / "documentation/relatorio-poc-comparacao-regras.pdf"
styles = getSampleStyleSheet()
styles.add(ParagraphStyle("BodyPT", fontName="Times-Roman", fontSize=11,
                          leading=15, alignment=TA_JUSTIFY, spaceAfter=8))
styles.add(ParagraphStyle("HeadingPT", fontName="Times-Bold", fontSize=14,
                          leading=18, spaceBefore=10, spaceAfter=8))
styles.add(ParagraphStyle("SmallPT", fontName="Times-Roman", fontSize=9,
                          leading=12, spaceAfter=6))
styles.add(ParagraphStyle("CaptionPT", parent=styles["SmallPT"], alignment=TA_CENTER))
styles.add(ParagraphStyle("TitlePT", fontName="Times-Bold", fontSize=20,
                          leading=24, spaceAfter=12))


def p(text, style="BodyPT"):
    return Paragraph(text, styles[style])


def table(rows, widths):
    content = [[p(str(value), "SmallPT") for value in row] for row in rows]
    result = Table(content, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#999999")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return result


def report(name, rule, threshold="0.20"):
    return json.loads((RESULTS / name / f"{rule}-{threshold}" / "report.json")
                      .read_text(encoding="utf-8"))


def figure(name, rule, width=165):
    """Representação documental: mantém a máscara, substitui cor por hachuras."""
    data = report(name, rule)
    with Image.open(ROOT / data["image"]) as source:
        photo = ImageOps.exif_transpose(source).convert("L")
    with Image.open(RESULTS / name / f"{rule}-0.20" / "candidates.png") as source:
        mask = source.convert("L")
    marks = Image.new("L", photo.size, 0)
    draw = ImageDraw.Draw(marks)
    # Contorno branco sob o traço preto preserva contraste em áreas escuras.
    for offset in range(-photo.height, photo.width, 24):
        draw.line((offset, 0, offset + photo.height, photo.height), fill=255, width=7)
    photo = Image.composite(Image.new("L", photo.size, 255), photo,
                            ImageChops.multiply(mask, marks))
    thin = Image.new("L", photo.size, 0)
    draw = ImageDraw.Draw(thin)
    for offset in range(-photo.height, photo.width, 24):
        draw.line((offset, 0, offset + photo.height, photo.height), fill=255, width=3)
    photo = Image.composite(Image.new("L", photo.size, 0), photo,
                            ImageChops.multiply(mask, thin))
    roi = data["roi_pixels"]
    box = (roi["left"], roi["top"], roi["right"] - 1, roi["bottom"] - 1)
    draw = ImageDraw.Draw(photo)
    draw.rectangle(box, outline=255, width=10)
    draw.rectangle(box, outline=0, width=4)
    photo.thumbnail((900, 1200))
    stream = BytesIO()
    photo.save(stream, format="PNG")
    stream.seek(0)
    return PDFImage(stream, width=width, height=width * photo.height / photo.width)


def pct(value):
    return f"{float(value) * 100:.2f}%".replace(".", ",")


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeGray(0)
    canvas.setLineWidth(0.4)
    canvas.line(22 * mm, 18 * mm, 188 * mm, 18 * mm)
    canvas.setFont("Times-Roman", 9)
    canvas.drawString(22 * mm, 13 * mm, "Mobility Risk Detection | Relatório exploratório da POC")
    canvas.drawRightString(188 * mm, 13 * mm, f"Página {doc.page}")
    canvas.restoreState()


def main():
    with (RESULTS / "summary.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 20:
        raise ValueError("O relatório desta coleta requer as 20 análises das cinco fotos.")
    lookup = {(Path(r["image"]).stem, r["rule"], float(r["min_closeness"])): r for r in rows}
    story = [
        p("Mobility Risk Detection", "TitlePT"),
        p("Relatório de evolução da prova de conceito", "HeadingPT"),
        p("Comparação de regras para identificação de possíveis obstáculos frontais<br/>"
          "Data de elaboração: 17 de novembro de 2026", "SmallPT"),
        Spacer(1, 8),
        p("1. Objetivo e escopo", "HeadingPT"),
        p("Investigar o uso de profundidade monocular para sinalizar possíveis obstáculos "
          "na região frontal de imagens capturadas com smartphone. Esta etapa avalia "
          "uma implementação em Python no computador, em ambientes internos. Ainda "
          "não há aplicativo Android integrado nem avaliação de desempenho em celular."),
        p("O fluxo implementado recebe uma foto, estima profundidade inversa relativa "
          "com Depth Anything V2 Small e aplica uma regra de decisão. A saída inclui "
          "imagem marcada, mapa de profundidade, máscara de candidatos e relatório JSON. "
          "O modelo não fornece, nesta configuração, distância em metros; a regra "
          "também não identifica a classe do objeto nem a probabilidade de colisão."),
        p("2. Regras comparadas", "HeadingPT"),
        p("<b>Referência lateral.</b> Compara cada pixel da região central com a mediana "
          "das laterais na mesma linha. A hipótese é que um obstáculo frontal "
          "apresente profundidade inversa maior que a referência lateral."),
        p("<b>Perfil do chão.</b> Ajusta uma reta às medianas por linha na faixa central "
          "abaixo da região de interesse e extrapola o perfil para as linhas superiores. "
          "Os candidatos são regiões mais próximas que o perfil estimado. A hipótese "
          "é de chão predominantemente plano e visível nessa faixa; não há segmentação "
          "semântica do chão. A regra lateral foi mantida como padrão."),
        table([
            ["Parâmetro", "Configuração da comparação"],
            ["Normalização", "Percentis 2 e 98 do mapa, limitados ao intervalo [0, 1]"],
            ["Região de interesse (ROI)", "35% a 65% da largura; 30% a 80% da altura"],
            ["Proximidade mínima", "Duas configurações fixas: 0,60 e 0,20"],
            ["Contraste mínimo", "0,15 acima da referência escolhida"],
            ["Área para emitir alerta", "Pelo menos 5% dos pixels da ROI satisfazendo os dois critérios"],
        ], [155, 315]),
        p("Os limiares são experimentais. Ausência de alerta não atesta caminho seguro.", "SmallPT"),
        PageBreak(),
        p("3. Procedimento e resultados", "HeadingPT"),
        p("Foram utilizadas cinco fotos próprias: duas cenas fornecidas como livres, "
          "duas com cadeira frontal e uma com cadeira lateral. Os mapas já gerados "
          "foram reutilizados, sem executar novamente o modelo. Duas regras e dois "
          "limiares de proximidade produziram 20 análises. São dados de desenvolvimento, "
          "não um conjunto independente de validação."),
        p("A tabela mostra o percentual da ROI que passou simultaneamente pelos "
          "critérios de proximidade e contraste. Valores de pelo menos 5% geram alerta. "
          "Os valores são arredondados apenas para apresentação."),
    ]
    results_table = [["Foto", "Lateral<br/>0,60", "Lateral<br/>0,20", "Chão<br/>0,60", "Chão<br/>0,20"]]
    for name in ("cadeirafrente1", "cadeirafrente2", "cadeiralado1", "livre1", "livre2"):
        results_table.append([name] + [pct(lookup[name, rule, threshold]["candidate_area_fraction"])
                                      for rule, threshold in (("lateral", .6), ("lateral", .2),
                                                              ("floor", .6), ("floor", .2))])
    story += [table(results_table, [130, 85, 85, 85, 85]), Spacer(1, 10),
              p("4. Diagnósticos adicionados", "HeadingPT"),
              p("O relatório agora separa a proporção de pixels que passou por "
                "proximidade, por contraste e pelos dois critérios. Também registra "
                "percentis do contraste, disponibilidade da referência e parâmetros "
                "do ajuste do chão. Todas as proporções usam a ROI inteira como "
                "denominador; não são probabilidades."),
              p("Exemplo: segunda cadeira frontal, com proximidade mínima de 0,20."),
              table([["Diagnóstico", "Lateral", "Chão"]] + [
                  [label] + [pct(report("cadeirafrente2", rule)["diagnostics"][key])
                             for rule in ("lateral", "floor")]
                  for label, key in (("Passou por proximidade", "closeness_pass_fraction"),
                                     ("Passou por contraste", "contrast_pass_fraction"),
                                     ("Passou pelos dois", "both_pass_fraction"))
              ], [230, 120, 120]),
              Spacer(1, 10),
              p("A comparação lateral perde a segunda cadeira mesmo com 27,36% da "
                "ROI passando por proximidade: só 0,14% passa por contraste. A referência "
                "do chão eleva a interseção para 22,79% e gera alerta. Entretanto, "
                "ela também gera alerta na cena livre1, inexistente na regra lateral. "
                "Assim, não se pode concluir que uma regra seja superior."),
              PageBreak(),
              p("5. Evidências visuais em preto e branco", "HeadingPT"),
              p("Retângulo: região de interesse. Hachuras diagonais: pixels candidatos. "
                "As figuras foram geradas das fotos originais e das mesmas máscaras "
                "da análise, substituindo a marcação colorida por hachuras. Todas "
                "usam proximidade 0,20 e contraste 0,15.", "SmallPT")]
    panels = []
    for name, title in (("cadeirafrente2", "Cadeira frontal 2"), ("livre1", "Cena livre 1")):
        cells = []
        for rule, label in (("lateral", "referência lateral"), ("floor", "perfil do chão")):
            r = report(name, rule)
            status = "Com alerta" if r["status"] == "possivel_obstaculo" else "Sem alerta"
            cells.append([p(f"<b>{title} — {label}</b>", "CaptionPT"), figure(name, rule),
                          p(f"{status}; área candidata: {pct(r['candidate_area_fraction'])}.", "CaptionPT")])
        panels.append(cells)
    panel_table = Table(panels, colWidths=[235, 235])
    panel_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story += [panel_table,
              p("Na cadeira frontal 2, o perfil do chão marca o assento. Em livre1, "
                "marca a borda do armário: a ROI também cobre superfícies que não "
                "representam necessariamente a passagem pretendida.", "SmallPT"),
              PageBreak(),
              p("6. Limitações e verificação", "HeadingPT"),
              p("<b>Geometria da trajetória.</b> A ROI é um retângulo fixo, sem projeção "
                "geométrica do espaço de caminhada. Na foto da cadeira lateral, parte "
                "do assento e da perna invade esse retângulo. O nome do arquivo não "
                "basta para decidir se o alerta é um falso positivo; é necessário "
                "definir previamente o critério de obstáculo frontal."),
              p("<b>Referência do chão.</b> O ajuste exige pelo menos oito linhas de "
                "amostra, inclinação mínima de 0,05 por altura normalizada e mediana "
                "do erro de até 0,05 na profundidade normalizada. Quando o ajuste é "
                "rejeitado, o resultado é inconclusivo. Um ajuste aceito não comprova "
                "a presença de chão; oclusões, móveis e inclinação da câmera podem "
                "violar a hipótese."),
              p("<b>Amostra e desempenho.</b> Cinco imagens não sustentam conclusões "
                "sobre eficácia geral. As cenas já orientaram o desenvolvimento e "
                "devem permanecer separadas de uma coleta futura de avaliação. Os "
                "tempos desta comparação medem leitura de mapas e análise, sem "
                "inferência. Tempos anteriores da ferramenta incluem carregamento "
                "do modelo e não representam FPS ou desempenho no smartphone."),
              p("<b>Verificação de código.</b> Dez testes automatizados passaram. "
                "Cobrem gradiente do chão, obstáculos sintéticos, superfícies laterais "
                "próximas, diagnósticos, entradas inválidas, rejeição do ajuste e "
                "geração dos artefatos pelas duas regras. Não substituem avaliação "
                "com fotos reais."),
              p("7. Próximas etapas", "HeadingPT"),
              p("Definir o critério de obstáculo frontal e registrar os rótulos antes "
                "da análise; coletar cenas novas com e sem obstáculos; manter os "
                "parâmetros fixos na avaliação; contabilizar obstáculos perdidos, "
                "alertas indevidos e resultados inconclusivos. Em uma etapa separada, "
                "medir inferência com o modelo já carregado e, se previsto no escopo, "
                "avaliar o aparelho-alvo."),
              p("8. Reprodutibilidade e referências", "HeadingPT"),
              p("Comparação: <font face='Courier'>python scripts/compare_rules.py</font><br/>"
                "Testes: <font face='Courier'>python -m unittest discover -s tests -v</font><br/>"
                "Dados: <font face='Courier'>outputs/diagnostico/summary.csv</font><br/>"
                "Relatórios e imagens: <font face='Courier'>outputs/diagnostico/</font>", "SmallPT"),
              p("Referência do modelo: Depth Anything V2, repositório oficial.<br/>"
                "https://github.com/DepthAnything/Depth-Anything-V2<br/>"
                "Modelo integrado: depth-anything/Depth-Anything-V2-Small-hf.<br/>"
                "https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf", "SmallPT"),
              p("<b>Conclusão desta etapa:</b> o fluxo de processamento está implementado "
                "e permite comparar hipóteses. A alternativa do chão recuperou um "
                "obstáculo perdido, mas introduziu um alerta em uma cena fornecida "
                "como livre. A abordagem permanece experimental.")]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=(210 * mm, 297 * mm),
                            leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=18 * mm, bottomMargin=24 * mm,
                            title="Mobility Risk Detection — Relatório da POC",
                            author="Projeto Mobility Risk Detection")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
