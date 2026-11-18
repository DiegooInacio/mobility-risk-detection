"""Consolida a etapa métrica e de segmentação em PDF A4 em preto e branco."""

import csv
from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps
from reportlab.lib.units import mm
from reportlab.platypus import Image as PDFImage, PageBreak, SimpleDocTemplate, Spacer, Table, TableStyle

from generate_poc_report import ROOT, footer, p, pct, table

OUTPUT = ROOT / "documentation/relatorio-poc-profundidade-metrica-e-segmentacao.pdf"


def read_report(path):
    return json.loads((ROOT / path / "report.json").read_text(encoding="utf-8"))


def load_rows(path, count):
    with (ROOT / path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != count:
        raise ValueError(f"Esperava {count} resultados em {path}, encontrados {len(rows)}.")
    return rows


def monochrome_figure(path, width=165):
    report = read_report(path)
    with Image.open(ROOT / report["image"]) as source:
        photo = ImageOps.exif_transpose(source).convert("L")
    with Image.open(ROOT / path / "candidates.png") as source:
        mask = source.convert("L")
    for stroke_width, color in ((7, 255), (3, 0)):
        stripes = Image.new("L", photo.size, 0)
        draw = ImageDraw.Draw(stripes)
        for offset in range(-photo.height, photo.width, 24):
            draw.line((offset, 0, offset + photo.height, photo.height), fill=255, width=stroke_width)
        photo = Image.composite(Image.new("L", photo.size, color), photo,
                                ImageChops.multiply(mask, stripes))
    roi = report["roi_pixels"]
    box = (roi["left"], roi["top"], roi["right"] - 1, roi["bottom"] - 1)
    draw = ImageDraw.Draw(photo)
    draw.rectangle(box, outline=255, width=10)
    draw.rectangle(box, outline=0, width=4)
    photo.thumbnail((900, 1200))
    stream = BytesIO()
    photo.save(stream, format="PNG")
    stream.seek(0)
    return PDFImage(stream, width=width, height=width * photo.height / photo.width)


def status(value):
    return {"possivel_obstaculo": "S", "sem_indicio_pela_regra": "N", "inconclusivo": "I"}[value]


def decision_table(rows, profiles):
    names = list(dict.fromkeys(Path(row["image"]).stem for row in rows))
    lookup = {(Path(row["image"]).stem, row["profile"]): row for row in rows}
    matrix = [["Foto"] + [label for _, label in profiles]]
    for name in names:
        matrix.append([name] + [status(lookup[name, profile]["status"]) for profile, _ in profiles])
    return table(matrix, [140] + [55] * len(profiles))


def main():
    width_rows = load_rows("outputs/comparacao-largura/summary.csv", 66)
    object_rows = load_rows("outputs/comparacao-objetos/summary.csv", 66)
    story = [
        p("Mobility Risk Detection", "TitlePT"),
        p("Evolução da prova de conceito", "HeadingPT"),
        p("Profundidade métrica, critérios geométricos e segmentação de instâncias<br/>"
          "Data: 17/11/2026 | Referência anterior: commit e101bda", "SmallPT"),
        Spacer(1, 8),
        p("1. Objetivo e delimitação", "HeadingPT"),
        p("Este relatório consolida os experimentos posteriores à etapa de comparação "
          "entre profundidade relativa e perfil do chão. O objetivo é investigar a "
          "identificação de possíveis obstáculos frontais em fotografias de smartphone, "
          "com processamento local no computador."),
        p("Foram utilizados 11 arquivos de imagem distintos: cinco fotos anteriores e "
          "seis de uma nova coleta. As distâncias de 1 m, 1,5 m e 2 m indicadas nos "
          "nomes são aproximadas, conforme confirmação do usuário. Não há medidas de "
          "referência para avaliar o erro da profundidade. As imagens são conhecidas "
          "durante o desenvolvimento e não formam uma validação independente."),
        p("2. Abordagens implementadas", "HeadingPT"),
        table([
            ["Abordagem", "Pergunta investigada"],
            ["Profundidade métrica indoor", "Limites em metros ajudam a reduzir a dependência da normalização relativa por foto?"],
            ["Área e largura ocupada", "Um critério geométrico alternativo recupera candidatos pequenos ou fragmentados?"],
            ["Segmentação de instâncias", "Uma máscara por objeto permite reunir partes que a profundidade separa em componentes?"],
            ["União híbrida", "É possível incorporar alertas por objeto preservando os alertas geométricos?"],
        ], [155, 315]),
        Spacer(1, 10),
        p("A implementação mantém as regras anteriores para comparação. São salvos "
          "mapas, máscaras, imagens marcadas, decisões por critério e relatórios JSON. "
          "Scripts de comparação registram parâmetros, hashes das entradas e cópias "
          "do código utilizado. As fotos e as saídas intermediárias permanecem locais."),
        p("O trabalho ainda não inclui APK, análise de vídeos, avaliação de desempenho "
          "no smartphone ou demonstração de navegação segura. A alternativa de "
          "ocupação frontal sem profundidade é uma hipótese para a próxima etapa, "
          "ainda não avaliada nesta versão."),
        PageBreak(),
        p("3. Profundidade métrica e nova coleta", "HeadingPT"),
        p("Foi integrado Depth Anything V2 Metric Indoor Small, cuja saída estima "
          "profundidade em metros. A regra usa pixels de até 2 m, ao menos 0,30 m "
          "mais próximos que um perfil estimado do chão. O perfil é ajustado em "
          "profundidade inversa na faixa central inferior. Mantêm-se componentes "
          "de pelo menos 1% da região de interesse (ROI); a área final mínima é 5%."),
        p("A ROI ocupa 35%–65% da largura e 30%–80% da altura da imagem. A diferença "
          "de 0,30 m é de profundidade na imagem, não altura acima do chão. Um ajuste "
          "aceito do perfil não comprova que a faixa realmente contém chão."),
        p("Nas cinco fotos anteriores, a abordagem detectou as duas cadeiras frontais "
          "e deixou as duas cenas fornecidas como livres sem alerta. Na cadeira "
          "lateral, também houve marcação na borda do armário. Na nova coleta, com "
          "os mesmos limites, os resultados foram:"),
    ]
    collection = json.loads((ROOT / "experiments/coleta02.json").read_text(encoding="utf-8"))
    metric_table = [["Foto", "Área candidata", "Alerta"]]
    for record in collection["images"]:
        name = Path(record["image"]).stem
        r = read_report(f"outputs/coleta02/baseline/{name}")
        metric_table.append([name, pct(r["candidate_area_fraction"]), status(r["status"])])
    story += [table(metric_table, [240, 125, 105]), Spacer(1, 10),
              p("A terceira cadeira aparece dentro da ROI, mas não gera candidatos "
                "combinando profundidade de até 2 m e diferença do chão. Aumentar "
                "apenas o alcance para 2,5 m não muda esse resultado. Com alcance "
                "de 3 m, a área final chega a 3,57%, ainda abaixo dos 5% exigidos."),
              p("Nas outras três fotos novas, a passagem central foi interpretada como "
                "aparentemente livre. O usuário confirmou que o cachorro está fora "
                "do caminho pretendido. Ausência de alerta não significa reconhecimento "
                "correto de todos os objetos ou certificação de passagem livre."),
              p("As áreas são proporções de pixels da ROI, não acurácia ou probabilidade. "
                "S = alerta; N = sem indício pela regra; I = inconclusivo.", "SmallPT"),
              PageBreak(),
              p("4. Área mínima versus suporte por largura", "HeadingPT"),
              p("Compararam-se área mínima de 5%, área mínima de 3% e decisão por "
                "largura. Cada alternativa foi avaliada com alcance de 2 m e 3 m, "
                "mantendo os demais critérios. Isso produziu 66 análises das mesmas "
                "11 imagens; não são 66 exemplos independentes."),
              p("A alternativa por largura exige, por componente, ocupação de pelo "
                "menos 30% da largura da ROI, suporte na faixa central e uma sequência "
                "de linhas de ao menos 2% da altura da ROI. Usa pixels reais do "
                "componente, não a área preenchida de sua caixa."),
              decision_table(width_rows, [
                  ("area5-2m", "Área 5%<br/>2 m"), ("area3-2m", "Área 3%<br/>2 m"),
                  ("largura-2m", "Largura<br/>2 m"), ("area5-3m", "Área 5%<br/>3 m"),
                  ("area3-3m", "Área 3%<br/>3 m"), ("largura-3m", "Largura<br/>3 m")]),
              Spacer(1, 10),
              p("A largura reduziu um alerta lateral ambíguo com alcance de 2 m, mas "
                "não recuperou a terceira cadeira: seus candidatos ficaram separados "
                "e sem suporte central suficiente. A combinação de área de 3% e "
                "alcance de 3 m recuperou o caso, mas ampliou alertas nas fotos "
                "anteriores. Não se demonstrou uma configuração superior."),
              p("As cenas livre1 e livre2 contêm superfícies na região central. Em "
                "livre2, o alerta marca a parede frontal, que pode ser um obstáculo "
                "real se a direção pretendida for para ela. O nome do arquivo não "
                "é suficiente para classificar automaticamente o alerta como erro.", "SmallPT"),
              PageBreak(),
              p("5. Segmentação de objetos e união híbrida", "HeadingPT"),
              p("Foi integrado YOLO11n-seg para prever máscaras e classes de instâncias. "
                "A regra por objeto exige confiança de 0,35; máscara com ao menos 1% "
                "da ROI; ao menos 10% da máscara total na ROI; suporte central; e "
                "ao menos 10% dos pixels da máscara na ROI dentro da distância máxima. "
                "Ela agrupa partes pela instância, sem depender da área total de 5%."),
              p("O modo híbrido alerta se qualquer ramo alertar. Sem alerta, fica "
                "inconclusivo se algum ramo for inconclusivo. Assim, a ausência de "
                "uma classe reconhecida não suprime alertas geométricos de paredes. "
                "Foram feitas outras 66 análises, reutilizando as mesmas 11 fotos."),
              decision_table(object_rows, [
                  ("metric-2m", "Geom.<br/>2 m"), ("objects-2m", "Objetos<br/>2 m"),
                  ("hybrid-2m", "Híbrido<br/>2 m"), ("metric-3m", "Geom.<br/>3 m"),
                  ("objects-3m", "Objetos<br/>3 m"), ("hybrid-3m", "Híbrido<br/>3 m")]),
              Spacer(1, 10),
              p("A terceira cadeira foi prevista como chair, com confiança de cerca "
                "de 0,85. Com alcance de 3 m, aproximadamente 15,7% de seus pixels "
                "na ROI atendem à proximidade e há alerta por objeto. Na mesma "
                "configuração, a geometria continuava sem alerta. Com limite de 2 m, "
                "a cadeira permanece fora do critério estimado de proximidade."),
              p("Os casos inconclusivos incluem ausência de detecção ou confiança "
                "insuficiente. Houve predições incorretas, como dining table na "
                "cadeira lateral. Não há segmentação de todas as superfícies nem "
                "cobertura garantida de classes desconhecidas.", "SmallPT"),
              PageBreak(),
              p("6. Evidências visuais", "HeadingPT"),
              p("As quatro figuras usam alcance estimado de 3 m. Retângulo: ROI. "
                "Hachuras: máscara candidata da respectiva abordagem. Na geometria, "
                "pode haver candidatos sem alerta. No ramo por objetos, a máscara "
                "agrupada não corresponde apenas aos pixels próximos; as áreas "
                "marcadas não medem eficácia e não são diretamente comparáveis.", "SmallPT")]
    panels = []
    for name, title in (("cadeira2metros", "Cadeira mais distante"), ("livre2", "Parede frontal em livre2")):
        cells = []
        configurations = (("metric-3m", "geometria"), ("objects-3m", "objetos")) if name == "cadeira2metros" else (
            ("objects-3m", "objetos"), ("hybrid-3m", "híbrido"))
        for profile, label in configurations:
            path = f"outputs/comparacao-objetos/{profile}/{name}"
            r = read_report(path)
            state = {"S": "Com alerta", "N": "Sem indício", "I": "Inconclusivo"}[status(r["status"])]
            cells.append([p(f"<b>{title} — {label}</b>", "CaptionPT"),
                          monochrome_figure(path), p(state, "CaptionPT")])
        panels.append(cells)
    panel_table = Table(panels, colWidths=[235, 235])
    panel_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story += [panel_table,
              p("O agrupamento por instância recupera a cadeira nesta configuração. "
                "A ausência de classe reconhecida para a parede gera inconclusivo "
                "no ramo por objetos; o híbrido preserva o alerta geométrico.", "SmallPT"),
              PageBreak(),
              p("7. Conclusões e limites da evidência", "HeadingPT"),
              p("<b>Ganho observado.</b> Profundidade métrica melhorou resultados das "
                "fotos iniciais; nas imagens novas, surgiram limitações. Agrupamento "
                "por instância recuperou um obstáculo que a regra de área perdia, "
                "comparando o mesmo alcance de 3 m. São ganhos pontuais, sem "
                "estimativa confiável de eficácia geral."),
              p("<b>Gargalos.</b> A decisão depende da profundidade estimada, da "
                "trajetória aproximada por retângulo, da definição de alerta e da "
                "cobertura do segmentador. Confiança do modelo não é probabilidade "
                "de colisão. Alterar limiares pode recuperar um caso e ampliar "
                "alertas em outros. A união híbrida preserva também possíveis "
                "alertas indevidos da geometria."),
              p("<b>Verificação.</b> Os 34 testes automatizados passaram. Cobrem "
                "critérios geométricos, unidades dos mapas, componentes, suporte "
                "por largura, partes desconectadas de uma instância, sobreposição "
                "sem contagem dupla, identidade do cache, união híbrida e geração "
                "dos artefatos. Eles verificam a implementação, não a eficácia "
                "em situações reais."),
              p("8. Próxima etapa proposta", "HeadingPT"),
              p("Antes de escolher limiares definitivos, medir distâncias com referência "
                "de captura definida e rotular obstáculos pela direção pretendida. "
                "Como simplificação a investigar, avaliar presença e ocupação de "
                "objetos na região frontal sem usar profundidade. Esse experimento "
                "ainda não integra os resultados deste relatório: tamanho aparente "
                "ou sobreposição na imagem não determina distância física por si só."),
              p("9. Reprodução e referências", "HeadingPT"),
              p("Testes: <font face='Courier'>python -m unittest discover -s tests -v</font><br/>"
                "Comparação métrica: <font face='Courier'>python scripts/compare_metric.py</font><br/>"
                "Área/largura: <font face='Courier'>scripts/evaluate_collection.py</font>, "
                "com os manifestos documentados no README.<br/>"
                "Objetos/híbrido: <font face='Courier'>python scripts/compare_objects.py</font><br/>"
                "Gerar este relatório: <font face='Courier'>python scripts/generate_progress_report.py</font>", "SmallPT"),
              p("Os CSVs, JSONs, mapas, máscaras e snapshots ficam em outputs/. "
                "As análises em Markdown ficam em experiments/. A reprodução dos "
                "experimentos requer as fotos e os mapas locais, não versionados.", "SmallPT"),
              p("Fontes dos modelos:<br/>"
                "https://github.com/DepthAnything/Depth-Anything-V2<br/>"
                "https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf<br/>"
                "https://docs.ultralytics.com/models/yolo11/", "SmallPT")]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=(210*mm, 297*mm),
                            leftMargin=22*mm, rightMargin=22*mm,
                            topMargin=18*mm, bottomMargin=24*mm,
                            title="Mobility Risk Detection — Profundidade métrica e segmentação",
                            author="Projeto Mobility Risk Detection")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
