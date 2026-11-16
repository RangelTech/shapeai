"""Protocolos: busca no material da doutora (RAG) e curva de concentração estimada (no estilo do steroidplotter).

A base (conhecimento/base.json) sai de scripts/gerar_conhecimento.py a partir das planilhas da doutora do projeto loki.
A busca é léxica (sem embedding): normaliza acento, expande apelidos ("deca", "tren", "mounjaro") e pontua por termo.
A curva usa a função de Bateman por aplicação: liberação do depósito pela meia-vida do éster e eliminação rápida
do hormônio livre. É estimativa visual para comparar ésteres e frequências, não dosagem sanguínea.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path

BASE = json.loads((Path(__file__).resolve().parent.parent / "conhecimento" / "base.json").read_text(encoding="utf-8"))

APELIDOS = {
    "deca": "nandrolona decanoato", "deposteron": "testosterona cipionato", "cipionato": "cipionato testosterona",
    "androxon": "testosterona undecanoato", "nebido": "testosterona undecanoato", "hormus": "testosterona", "durateston": "testosterona sustanon blend", "sustanon": "testosterona blend",
    "enantato": "enantato", "cipionato": "cipionato", "tren": "trembolona", "trembo": "trembolona", "bold": "boldenona",
    "equipoise": "boldenona", "masteron": "drostanolona", "primo": "metenolona primobolan", "primobolan": "metenolona",
    "oxa": "oxandrolona", "anavar": "oxandrolona", "dianabol": "metandienona", "dbol": "metandienona", "hemogenin": "oximetolona",
    "anadrol": "oximetolona", "winstrol": "estanozolol", "stano": "estanozolol", "halotestin": "fluoximesterona",
    "superdrol": "methasterone", "proviron": "mesterolona", "mounjaro": "tirzepatida", "tirze": "tirzepatida",
    "tirzepartida": "tirzepatida", "zepbound": "tirzepatida", "gh": "somatropina", "hgh": "somatropina",
    "slupp": "slu-pp-332", "clem": "clembuterol", "tpc": "tpc pos-ciclo serm", "trt": "trt reposicao",
    "ciclo": "ciclo protocolo", "emagrecer": "tirzepatida emagrecer", "secar": "cutting definicao",
    "aplicar": "aplicacao local seringa", "seringa": "seringa agulha", "exames": "exame", "npp": "fenilpropionato nandrolona",
    "ment": "trestolona", "dhb": "dihydroboldenone", "ozempic": "tirzepatida glp-1", "semaglutida": "glp-1 tirzepatida",
}
VAZIAS = set("a o e de da do das dos em no na nos nas um uma para por com que qual quais quanto como eu meu minha se pode posso tem ser sao".split())


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _termos(s: str, expandir: bool = True) -> list[str]:
    out = []
    for t in re.findall(r"[a-z0-9\-]+", _norm(s)):
        if t in VAZIAS or len(t) < 2:
            continue
        out.append(t)
        if expandir and t in APELIDOS:
            out += [x for x in _termos(APELIDOS[t], False) if x != t]
    return out


_INDICE = [(_norm(t["titulo"] + " " + " ".join(t["tags"])), _norm(t["texto"]), t) for t in BASE]


def buscar(pergunta: str, k: int = 6) -> list[dict]:
    """Os k trechos mais relevantes para a pergunta (título/tags pesam 3x)."""
    termos = _termos(pergunta)
    if not termos:
        return []
    pontos = []
    for cab, corpo, t in _INDICE:
        p = sum(3 * cab.count(x) + min(corpo.count(x), 3) for x in termos if len(x) >= 3 or x in ("gh", "ai"))
        if p:
            pontos.append((p, t))
    pontos.sort(key=lambda x: -x[0])
    return [t for _, t in pontos[:k]]


def contexto_rag(pergunta: str, k: int = 6) -> str:
    achados = buscar(pergunta, k)
    if not achados:
        return ""
    return "\n\n".join(f"[{t['titulo']}]\n{t['texto']}" for t in achados)


# ------------------------------------------------------------------ curva (estilo steroidplotter)
# meia-vida de liberação do depósito (dias) e fração ativa do éster (massa do hormônio / massa do éster)
COMPOSTOS = {
    "testosterona_enantato": ("Testosterona enantato", 4.5, 0.72),
    "testosterona_cipionato": ("Testosterona cipionato", 5.0, 0.70),
    "testosterona_propionato": ("Testosterona propionato", 0.8, 0.83),
    "testosterona_suspensao": ("Testosterona suspensão", 0.1, 1.0),
    "testosterona_undecanoato": ("Testosterona undecanoato", 21.0, 0.63),
    "sustanon": ("Durateston / Sustanon 250", None, None),
    "nandrolona_decanoato": ("Nandrolona decanoato (Deca)", 6.0, 0.64),
    "nandrolona_fenilpropionato": ("Nandrolona fenilpropionato (NPP)", 2.5, 0.67),
    "trembolona_acetato": ("Trembolona acetato", 1.0, 0.87),
    "trembolona_enantato": ("Trembolona enantato", 5.0, 0.70),
    "boldenona_undecilenato": ("Boldenona undecilenato", 14.0, 0.61),
    "drostanolona_propionato": ("Masteron propionato", 0.8, 0.80),
    "drostanolona_enantato": ("Masteron enantato", 5.0, 0.72),
    "metenolona_enantato": ("Primobolan enantato", 5.0, 0.70),
    "dhb_cipionato": ("DHB cipionato", 5.0, 0.69),
    "trestolona_acetato": ("Trestolona acetato (MENT)", 1.0, 0.87),
    "oxandrolona": ("Oxandrolona (oral)", 0.4, 1.0),
    "metandienona": ("Dianabol (oral)", 0.2, 1.0),
    "oximetolona": ("Hemogenin (oral)", 0.35, 1.0),
    "estanozolol_oral": ("Winstrol (oral)", 0.375, 1.0),
    "turanibol": ("Turanibol (oral)", 0.65, 1.0),
    "mesterolona": ("Proviron (oral)", 0.5, 1.0),
    "tirzepatida": ("Tirzepatida", 5.0, 1.0),
    "semaglutida": ("Semaglutida", 7.0, 1.0),
}
SUSTANON = [(30, 0.8, 0.83), (60, 1.5, 0.67), (60, 3.1, 0.72), (100, 7.5, 0.64)]  # por 250 mg: prop, fenilprop, isocaproato, decanoato


def _bateman(t: float, dose: float, meia_vida: float) -> float:
    """Quantidade ativa t dias após a aplicação: sobe rápido (entrada) e cai pela meia-vida do éster/composto."""
    if t <= 0:
        return 0.0
    k_in = math.log(2) / 0.08
    k_out = math.log(2) / max(meia_vida, 0.05)
    if abs(k_in - k_out) < 1e-6:
        k_in *= 1.05
    return dose * k_in / (k_in - k_out) * (math.exp(-k_out * t) - math.exp(-k_in * t))


def curva(itens: list[dict], dias: int | None = None, passo: float = 0.25) -> dict:
    """itens: [{composto, dose_mg, a_cada_dias, semanas, inicio_semana}] -> séries (mg ativos estimados) por composto e total."""
    aplic: list[tuple[str, float, float, float, float]] = []  # (nome, dia, dose ativa, meia-vida, peso)
    fim = 0.0
    for it in itens[:8]:
        chave = str(it.get("composto") or "")
        if chave not in COMPOSTOS:
            continue
        dose = max(0.0, min(float(it.get("dose_mg") or 0), 5000))
        cada = max(0.25, min(float(it.get("a_cada_dias") or 7), 60))
        sem = max(1, min(int(it.get("semanas") or 12), 52))
        ini = max(0, int(it.get("inicio_semana") or 0)) * 7
        nome = COMPOSTOS[chave][0]
        t = float(ini)
        while t < ini + sem * 7 - 1e-9:
            if chave == "sustanon":
                for mg, hv, fr in SUSTANON:
                    aplic.append((nome, t, dose * mg / 250 * fr, hv, 1))
            else:
                _, hv, fr = COMPOSTOS[chave]
                aplic.append((nome, t, dose * fr, hv, 1))
            t += cada
        fim = max(fim, ini + sem * 7)
    total_dias = int(dias or (fim + 28))
    total_dias = max(7, min(total_dias, 420))
    pontos = [round(i * passo, 2) for i in range(int(total_dias / passo) + 1)]
    series: dict[str, list[float]] = {}
    for nome, d0, dose, hv, _ in aplic:
        s = series.setdefault(nome, [0.0] * len(pontos))
        for i, t in enumerate(pontos):
            if t > d0:
                s[i] += _bateman(t - d0, dose, hv)
    total = [round(sum(v[i] for v in series.values()), 1) for i in range(len(pontos))]
    return {"dias": pontos, "series": {k: [round(x, 1 if max(v or [0]) >= 20 else 3) for x in v] for k, v in series.items()}, "total": total,
            "unidade": "mg ativos estimados no organismo", "aviso": "Estimativa farmacocinética para comparar ésteres e frequências; não substitui exame de sangue."}
