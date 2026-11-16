"""Protocolo do cliente a partir da RECEITA do médico.

A IA não monta protocolo hormonal. O cliente manda a foto (ou o texto) da receita; a IA de visão lê e devolve os itens
estruturados; o cliente confere e salva. Com isso o app monta a aba Hormônios: ampolas, dose, frequência, calendário e
curva estimada (app/protocolos.py). Origem sempre registrada: médico e data da receita.
"""
from __future__ import annotations

import json
import re

from app.db import Banco, agora
from app.protocolos import COMPOSTOS

ESQUEMA = """
CREATE TABLE IF NOT EXISTS protocolos_cliente (id INTEGER PRIMARY KEY, usuario INTEGER NOT NULL, medico TEXT NOT NULL DEFAULT '',
  data_receita TEXT NOT NULL DEFAULT '', itens TEXT NOT NULL, observacoes TEXT NOT NULL DEFAULT '', foto TEXT NOT NULL DEFAULT '',
  ativo INTEGER NOT NULL DEFAULT 1, criado REAL NOT NULL);
CREATE INDEX IF NOT EXISTS protocolos_cliente_usuario ON protocolos_cliente(usuario, criado);
"""
LER = """Você lê receitas e prescrições médicas de protocolos hormonais, tirzepatida e peptídeos e transcreve EXATAMENTE o que está escrito.
Não sugira, não complete e não corrija doses: só copie. Se algo estiver ilegível, deixe vazio e cite em "ilegivel".
Responda SÓ com JSON:
{"medico":"nome e registro, se houver","data":"AAAA-MM-DD ou vazio","itens":[{"composto":"<id da lista>","nome_na_receita":"como está escrito",
"dose_mg":número por aplicação,"a_cada_dias":número,"semanas":número,"inicio_semana":0,"via":"IM/SC/oral","obs":"horário, local, observação"}],
"observacoes":"orientações gerais da receita","ilegivel":"o que não deu para ler"}
Ids aceitos para "composto": {ids}. Se o composto não estiver na lista, use "outro" e escreva o nome em nome_na_receita."""


def preparar(db: Banco) -> None:
    db.con.executescript(ESQUEMA)


def prompt_leitura() -> str:
    return LER.replace("{ids}", ", ".join(COMPOSTOS))


def itens_validos(itens) -> list[dict]:
    out = []
    for it in (itens if isinstance(itens, list) else [])[:12]:
        if not isinstance(it, dict):
            continue
        c = str(it.get("composto") or "outro")
        try:
            out.append({"composto": c if c in COMPOSTOS else "outro", "nome_na_receita": str(it.get("nome_na_receita") or "")[:120],
                        "dose_mg": max(0.0, float(it.get("dose_mg") or 0)), "a_cada_dias": max(0.25, float(it.get("a_cada_dias") or 7)),
                        "semanas": max(1, int(float(it.get("semanas") or 12))), "inicio_semana": max(0, int(float(it.get("inicio_semana") or 0))),
                        "via": str(it.get("via") or "")[:10], "obs": str(it.get("obs") or "")[:300]})
        except (TypeError, ValueError):
            continue
    return out


def ler_json(txt: str) -> dict:
    txt = re.sub(r"```(json)?", "", txt or "")
    try:
        d = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
    except ValueError:
        return {"itens": [], "ilegivel": "não consegui ler a receita"}
    return {"medico": str(d.get("medico") or "")[:120], "data": str(d.get("data") or "")[:10], "itens": itens_validos(d.get("itens")),
            "observacoes": str(d.get("observacoes") or "")[:2000], "ilegivel": str(d.get("ilegivel") or "")[:500]}


def salvar(db: Banco, usuario: int, d: dict, foto: str = "") -> int:
    itens = itens_validos(d.get("itens"))
    if not itens:
        raise ValueError("nenhum item na receita")
    db.exec("UPDATE protocolos_cliente SET ativo=0 WHERE usuario=?", (usuario,))
    return db.exec("INSERT INTO protocolos_cliente(usuario,medico,data_receita,itens,observacoes,foto,criado) VALUES(?,?,?,?,?,?,?)",
                   (usuario, str(d.get("medico") or "")[:120], str(d.get("data") or "")[:10], json.dumps(itens, ensure_ascii=False),
                    str(d.get("observacoes") or "")[:2000], foto, agora())).lastrowid


def ativo(db: Banco, usuario: int) -> dict | None:
    p = db.um("SELECT * FROM protocolos_cliente WHERE usuario=? AND ativo=1 ORDER BY criado DESC LIMIT 1", (usuario,))
    if p:
        p["itens"] = json.loads(p["itens"])
    return p


def contexto(db: Banco, usuario: int) -> str:
    p = ativo(db, usuario)
    if not p:
        return "Nenhuma receita cadastrada. Se a pessoa já tem prescrição, peça a foto da receita na aba Hormônios."
    def nome(i: dict) -> str:
        oficial = COMPOSTOS.get(i["composto"], ("",))[0]
        if i["nome_na_receita"] and oficial:
            return f"{i['nome_na_receita']} (= {oficial})"
        return i["nome_na_receita"] or oficial or "?"
    linhas = [f"- {nome(i)}: {i['dose_mg']:g} mg a cada {i['a_cada_dias']:g} dias, "
              f"{i['semanas']} semanas{', começa na semana ' + str(i['inicio_semana']) if i['inicio_semana'] else ''}"
              f"{' (' + i['via'] + ')' if i['via'] else ''}{' — ' + i['obs'] if i['obs'] else ''}" for i in p["itens"]]
    return (f"Receita de {p['medico'] or 'médico não identificado'}{' em ' + p['data_receita'] if p['data_receita'] else ''} (transcrita da receita do cliente):\n"
            + "\n".join(linhas) + (f"\nOrientações da receita: {p['observacoes']}" if p["observacoes"] else ""))
