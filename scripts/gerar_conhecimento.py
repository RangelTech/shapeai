"""Gera conhecimento/base.json (trechos do RAG) a partir das planilhas da doutora (conhecimento/fonte/*.xlsx).

Fonte: material da Dra. do projeto loki (guia de hormônios e peptídeos, planilha de tirzepatida, suplementos, remédios
e exames). As colunas de dose de hormônio e peptídeo NÃO entram: a IA explica, mas a dose vem da receita do cliente. Cada linha de planilha vira um trecho; os roteiros da doutora (suporte no ciclo, TPC, exames por fase,
ésteres) entram como trechos de texto. Rodar de novo sempre que a planilha mudar:  python scripts/gerar_conhecimento.py
"""
from __future__ import annotations

import json
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parent.parent
FONTE = RAIZ / "conhecimento" / "fonte"
SAIDA = RAIZ / "conhecimento" / "base.json"


def linhas(caminho: Path, aba: str) -> list[dict]:
    ws = openpyxl.load_workbook(caminho, data_only=True)[aba]
    rows = [r for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)]
    cab = [str(h).strip() if h else "" for h in rows[0]]
    out = []
    for r in rows[1:]:
        d = {cab[i]: (str(v).strip() if v is not None else "") for i, v in enumerate(r) if i < len(cab) and cab[i]}
        if any(d.values()):
            out.append(d)
    return out


def num(v: str) -> str:
    try:
        f = float(v)
        return str(int(f)) if f.is_integer() else f"{f:.2f}".rstrip("0").rstrip(".")
    except ValueError:
        return v


def main() -> None:
    trechos: list[dict] = []

    def add(titulo: str, texto: str, tags: list[str]) -> None:
        trechos.append({"id": len(trechos) + 1, "titulo": titulo, "tags": tags, "texto": texto.strip()})

    guia = FONTE / "guia_hormonios.xlsx"
    for g in linhas(guia, "Glossário e Avisos"):
        vals = [v for v in g.values() if v]
        if len(vals) >= 2:
            add(f"Glossário: {vals[0]}", " — ".join(vals), ["glossario", vals[0].lower()])

    for h in linhas(guia, "Guia de Hormônios"):
        nome, ester = h.get("Hormônio", ""), h.get("Veículo / Éster", "")
        texto = (f"{nome} — {ester} ({h.get('Uso','')}, família {h.get('Família','')}, {h.get('Tipo','')}). "
                 f"Concentração comum: {h.get('Concentração Comum','')}. "
                 f"Efeitos: {h.get('Efeitos Anabólicos','')} Colaterais: {h.get('Colaterais Principais','')} "
                 f"Nota anabólica {num(h.get('Nota Anabólica (0-10)',''))}/10, nota de colaterais {num(h.get('Nota Colaterais (0-10)',''))}/10, "
                 f"razão benefício/colateral {num(h.get('Razão',''))}.")
        add(f"{nome} {ester}", texto, ["hormonio", nome.lower(), ester.lower(), h.get("Família", "").lower()])

    for p in linhas(guia, "Peptídeos e Auxiliares"):
        nome = p.get("Substância", "")
        texto = (f"{nome} ({p.get('Uso','')}, {p.get('Classe / Família','')}, mecanismo {p.get('Tipo / Mecanismo','')}). "
                 f"Apresentação: {p.get('Veículo / Apresentação','')}, concentração {p.get('Concentração Comum','')}. "
                 f"Efeitos: {p.get('Efeitos de Performance/Anabólicos','')} Colaterais: {p.get('Colaterais Principais','')} "
                 f"Nota de performance {num(p.get('Nota Performance (0-10)',''))}/10, colaterais {num(p.get('Nota Colaterais (0-10)',''))}/10.")
        add(nome, texto, ["peptideo", nome.lower()])

    dra = FONTE / "planilha_dra.xlsx"
    doses = linhas(dra, "DOSES")
    tab = "\n".join(f"- semanas {num(d['INICIO'])} a {num(d['FIM'])}: {d['DOSE']} = {num(d['UI'])} UI na seringa U-100 = {d['ML']} mL" for d in doses)
    add("Tirzepatida: escalonamento de dose da doutora",
        "Tirzepatida (Mounjaro, agonista GIP/GLP-1), 1 aplicação por semana, subcutânea, sempre no mesmo dia. "
        "Escalonamento da doutora (sobe a dose a cada 4 semanas se tolerar bem; se a náusea estiver forte, segura a dose mais 4 semanas):\n"
        f"{tab}\nRegiões: abdômen (5 cm do umbigo), coxa ou parte de trás do braço, alternando o lado. Seringa de insulina U-100 (100 UI = 1 mL).",
        ["tirzepatida", "mounjaro", "glp-1", "emagrecer", "dose"])
    for s in linhas(dra, "SUPLEMENTACAO"):
        add(f"Suplemento: {s.get('Suplemento','')}", f"{s.get('Suplemento','')}: {s.get('Por quê? (pele/cabelo)','')}. Dose comum: {s.get('Dose comum sugerida','')}. {s.get('Observações','')}",
            ["suplemento", "tirzepatida", s.get("Suplemento", "").lower()])
    rem = "\n".join(f"- {r.get('Remedio','')}: {r.get('Por quê? (pele/cabelo)','')} ({r.get('Dose comum sugerida','')})" for r in linhas(dra, "REMEDIOS"))
    add("Tirzepatida: remédios para os efeitos colaterais", f"Para os efeitos gastrointestinais da tirzepatida, a doutora usa:\n{rem}",
        ["tirzepatida", "colateral", "nausea", "diarreia", "remedio"])
    ex = "\n".join(f"- {e['Exame']} ({e['Urgência']}): {e['Indicação']}" for e in linhas(dra, "EXAMES"))
    add("Tirzepatida: exames de acompanhamento", f"Exames que a doutora pede para quem usa tirzepatida:\n{ex}", ["tirzepatida", "exame"])

    add("Ésteres, meia-vida e frequência de aplicação",
        "Cipionato: meia-vida ~7-10 dias, 1x por semana. Enantato: ~5-7 dias, 2x por semana. Propionato: ~1-2 dias, 3x por semana ou dia sim dia não. "
        "Decanoato: ~15 dias, 1x por semana. Undecilenato: muito longo. Quanto mais longo o éster, menos aplicações, mas mais tempo para estabilizar. "
        "Frequência escolhida define o éster: 1x/sem cipionato, 2x/sem enantato, 3x/sem propionato.",
        ["ester", "meia-vida", "frequencia", "aplicacao"])
    add("Suporte durante o ciclo (on-cycle)",
        "Inibidor de aromatase conforme o estradiol do exame; proteção do fígado com TUDCA 500 mg/dia ou NAC 600 mg/dia (principalmente com orais 17-alfa); "
        "coração: ômega-3 2 g/dia + CoQ10 100 mg/dia; proteína 2,0-2,4 g/kg/dia; HCG em ciclos acima de 12 semanas para preservar testículo e fertilidade. "
        "Duração típica: 12 semanas (iniciante/intermediário) a 16 semanas (avançado/atleta).",
        ["ciclo", "on-cycle", "suporte", "aromatase", "tudca", "hcg", "protocolo"])
    add("TPC — terapia pós-ciclo",
        "Começa cerca de 2 semanas após a última aplicação (depende do éster mais longo). Usa moduladores seletivos do receptor de estrogênio (SERMs) "
        "e suporte do fígado, por 4 a 6 semanas, para religar o eixo HPTO. Quem faz TRT ou blast & cruise não faz TPC.",
        ["tpc", "pos-ciclo", "serm", "protocolo"])
    add("Exames para quem usa hormônio",
        "Antes do ciclo: testosterona total e livre, LH, FSH, hemograma, lipidograma, TGO/TGP, PSA (homens), hematócrito, glicemia. "
        "Na 6ª semana: hemograma, lipidograma, TGO/TGP, hematócrito, estradiol, testosterona. "
        "No pós-ciclo/TPC: testosterona total e livre, LH, FSH, hemograma, lipidograma, TGO/TGP, estradiol. Hematócrito alto pede doação de sangue/ajuste.",
        ["exame", "hormonio", "ciclo", "hematocrito"])
    add("Tipos de protocolo",
        "TRT: reposição para hipogonadismo, níveis fisiológicos (300-1000 ng/dL). Primeiro ciclo: só testosterona, 12 semanas, com TPC. "
        "Ciclo com TPC: testosterona como base + 1 composto, termina com TPC. Blast & cruise: blast (fase de ganho, doses altas) alternado com cruise "
        "(manutenção em dose baixa), sem TPC. Mulheres: preferir compostos de baixa virilização (oxandrolona, primobolan) em doses baixas.",
        ["protocolo", "trt", "blast", "cruise", "primeiro ciclo", "mulher"])
    add("Locais de aplicação intramuscular e seringas",
        "Intramuscular: glúteo (quadrante superior externo), ventroglúteo, vasto lateral da coxa e deltoide; alternar os locais. "
        "Seringa de 3-5 mL com agulha 25x7 ou 30x7 para volumes maiores (1x/sem); seringa de 1 mL para doses pequenas (3x/sem). "
        "Subcutânea (tirzepatida, peptídeos): seringa de insulina U-100, agulha curta, ângulo de 90 graus na prega da pele. "
        "Imagens no app: /s/guia/localgluteo.webp, /s/guia/localventregluteo.webp, /s/guia/localvastolateral.webp, /s/guia/localdeltoide.webp, "
        "/s/guia/anguloagulhasubcultaneoeIM.webp, /s/guia/seringa_u100.webp.",
        ["aplicacao", "seringa", "agulha", "intramuscular", "subcutanea", "local"])

    SAIDA.write_text(json.dumps(trechos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(trechos)} trechos em {SAIDA}")


if __name__ == "__main__":
    main()
