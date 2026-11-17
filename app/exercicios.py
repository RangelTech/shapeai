"""Biblioteca de exercícios do Shape AI (RAG do treino) + mapa do corpo + rodízio das zonas de aplicação.

Fonte: free-exercise-db (domínio público, Unlicense): 873 exercícios com músculos, equipamento, passos e 2 fotos (início e
fim do movimento), servidas em /s/ex/<id>/0.webp e 1.webp (alternando viram a animação).
A IA NÃO escolhe livre: recebe só os exercícios possíveis no local onde a pessoa treina (decisão do Lucas, 17/11: nada de
máquina articulada para quem treina na praça) e devolve os ids; o servidor confere cada id.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

ARQ = Path(__file__).resolve().parent.parent / "conhecimento" / "exercicios.json"
BASE: list[dict] = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else []
POR_ID = {e["id"]: e for e in BASE}

# onde a pessoa treina -> equipamentos que existem lá
LOCAIS = {
    "academia": ("Academia completa", {"barbell", "dumbbell", "cable", "machine", "body only", "kettlebells", "bands", "e-z curl bar", "medicine ball", "exercise ball", "outro", "other"}),
    "condominio": ("Academia de condomínio / hotel", {"dumbbell", "cable", "machine", "body only", "bands", "exercise ball"}),
    "casa": ("Casa com halteres ou elásticos", {"dumbbell", "body only", "bands", "kettlebells", "exercise ball"}),
    "casa_sem": ("Casa sem equipamento", {"body only"}),
    "praca": ("Praça / barra fixa / calistenia", {"body only", "other", "outro"}),
}
MUSCULOS_PT = {
    "abdominals": "abdômen", "abductors": "abdutores", "adductors": "adutores", "biceps": "bíceps", "calves": "panturrilhas",
    "chest": "peito", "forearms": "antebraços", "glutes": "glúteos", "hamstrings": "posteriores de coxa", "lats": "dorsais",
    "lower back": "lombar", "middle back": "meio das costas", "neck": "pescoço", "quadriceps": "quadríceps", "shoulders": "ombros",
    "traps": "trapézio", "triceps": "tríceps",
}
EQUIP_PT = {"barbell": "barra", "dumbbell": "halteres", "cable": "polia", "machine": "máquina", "body only": "peso do corpo", "kettlebells": "kettlebell",
            "bands": "elástico", "e-z curl bar": "barra W", "medicine ball": "medicine ball", "exercise ball": "bola suíça", "foam roll": "rolo", "other": "barra fixa/outro", "outro": "outro"}


def normalizar_local(v: str | None) -> str:
    v = (v or "").strip().lower()
    return v if v in LOCAIS else {"academia": "academia", "casa": "casa"}.get(v, "academia")


def candidatos(local: str, limite: int = 150) -> list[dict]:
    """Exercícios possíveis no local, priorizando os compostos e os de nível iniciante/intermediário, todos os grupos."""
    equip = LOCAIS[normalizar_local(local)][1]
    ok = [e for e in BASE if e["equip"] in equip and e["cat"] in ("strength", "plyometrics", "cardio", "powerlifting", "stretching")]
    ordem = {"beginner": 0, "intermediate": 1, "expert": 2}
    ok.sort(key=lambda e: (e["cat"] == "stretching", ordem.get(e["nivel"], 1), e["mec"] != "compound", e["nome"]))
    por_musc: dict[str, list] = {}
    for e in ok:
        por_musc.setdefault((e["prim"] or ["outro"])[0], []).append(e)
    out, i = [], 0
    while len(out) < limite and any(i < len(v) for v in por_musc.values()):  # intercala os grupos para cobrir o corpo todo
        for v in por_musc.values():
            if i < len(v) and len(out) < limite:
                out.append(v[i])
        i += 1
    return out


def texto_candidatos(c: list[dict]) -> str:
    return "\n".join(f"{e['id']} | {e['nome']} | {', '.join(MUSCULOS_PT.get(m, m) for m in e['prim'])} | {EQUIP_PT.get(e['equip'], e['equip'])}" for e in c)


def _chave(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def enriquecer(ex: dict, local: str) -> dict:
    """Confere o id que a IA devolveu (ou acha pelo nome) e junta fotos, músculos e passos. Fora do local = troca."""
    e = POR_ID.get(str(ex.get("id") or ""))
    if not e:
        alvo = _chave(str(ex.get("nome_en") or ex.get("nome") or ""))
        e = next((x for x in BASE if _chave(x["nome"]) == alvo), None)
    equip = LOCAIS[normalizar_local(local)][1]
    if e and e["equip"] not in equip:
        e = None  # a IA escolheu algo que não existe onde a pessoa treina: não entra
    if e:
        ex["id"] = e["id"]
        ex["imgs"] = [f"/s/ex/{e['id']}/0.webp", f"/s/ex/{e['id']}/1.webp"]
        ex["musculos"] = e["prim"]
        ex["secundarios"] = e["sec"]
        ex["equipamento"] = EQUIP_PT.get(e["equip"], e["equip"])
        ex["nome_en"] = e["nome"]
    return ex


# ---------------- 1RM ----------------
def um_rm(carga: float, reps: int) -> float:
    """Epley: estimativa de carga máxima para 1 repetição."""
    if reps <= 1:
        return round(carga, 1)
    return round(carga * (1 + reps / 30), 1)


# ---------------- zonas de aplicação (rodízio) ----------------
ZONAS = {
    "im": ["gluteo_d", "gluteo_e", "coxa_d", "coxa_e", "deltoide_d", "deltoide_e"],          # intramuscular
    "sc": ["abdomen_sd", "abdomen_se", "abdomen_id", "abdomen_ie", "coxa_frente_d", "coxa_frente_e"],  # subcutânea (tirzepatida)
}
NOMES_ZONA = {"gluteo_d": "Glúteo direito (quadrante superior externo)", "gluteo_e": "Glúteo esquerdo (quadrante superior externo)",
              "coxa_d": "Coxa direita (lateral)", "coxa_e": "Coxa esquerda (lateral)", "deltoide_d": "Deltoide direito", "deltoide_e": "Deltoide esquerdo",
              "abdomen_sd": "Abdômen superior direito (a 5 cm do umbigo)", "abdomen_se": "Abdômen superior esquerdo (a 5 cm do umbigo)",
              "abdomen_id": "Abdômen inferior direito", "abdomen_ie": "Abdômen inferior esquerdo",
              "coxa_frente_d": "Coxa direita (frente)", "coxa_frente_e": "Coxa esquerda (frente)"}


def proxima_zona(via: str, ultimas: list[str]) -> str:
    """Rodízio fixo: a próxima zona da lista depois da última usada (nunca repete o mesmo ponto em seguida)."""
    lista = ZONAS.get(via, ZONAS["im"])
    ult = next((z for z in ultimas if z in lista), None)
    return lista[(lista.index(ult) + 1) % len(lista)] if ult else lista[0]


def via_do_composto(nome: str) -> str:
    n = (nome or "").lower()
    return "sc" if any(k in n for k in ("tirzepat", "semaglut", "liraglut", "insulin", "hcg", "peptid", "bpc", "retatrut")) else "im"


def hoje() -> str:
    return dt.date.today().isoformat()
