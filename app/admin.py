"""Painel de administrador (/admin): clientes, planos e as skills da IA editáveis, sem deploy.

Mesmo módulo em todos os produtos da Rangel Tech. Login único (usuário e senha em RT_ADMIN_USUARIO / RT_ADMIN_SENHA,
guardados no cofre pessoal) com cookie assinado de 12 h.
As skills nascem dos arquivos skills/*.md do repositório (semente) e passam a morar no banco; o texto salvo no painel
vale na próxima resposta, porque o app manda a skill no prompt de sistema de cada chamada ao Hermes.
"Restaurar" volta ao arquivo do repositório; toda gravação guarda a versão anterior no histórico.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.db import Banco, agora

SEMENTES = Path(__file__).resolve().parent.parent / "skills"
COOKIE = "rt_admin"
ESQUEMA = """
CREATE TABLE IF NOT EXISTS skills (nome TEXT PRIMARY KEY, conteudo TEXT NOT NULL, atualizado REAL NOT NULL, por TEXT NOT NULL DEFAULT 'repositorio');
CREATE TABLE IF NOT EXISTS skills_historico (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, conteudo TEXT NOT NULL, salvo REAL NOT NULL);
"""


def preparar(db: Banco) -> None:
    db.con.executescript(ESQUEMA)
    for f in sorted(SEMENTES.glob("*.md")):
        db.exec("INSERT OR IGNORE INTO skills(nome,conteudo,atualizado) VALUES(?,?,?)", (f.stem, f.read_text(encoding="utf-8"), agora()))


def skill(db: Banco, nome: str) -> str:
    r = db.um("SELECT conteudo FROM skills WHERE nome=?", (nome,))
    return r["conteudo"] if r else ""


def rotas(db: Banco, segredo: str, consulta_clientes: str, usuario: str | None = None, senha: str | None = None, seguro: bool = True) -> APIRouter:
    usuario = usuario if usuario is not None else os.environ.get("RT_ADMIN_USUARIO", "")
    senha = senha if senha is not None else os.environ.get("RT_ADMIN_SENHA", "")
    r = APIRouter(prefix="/api/admin")

    def assinar(exp: int) -> str:
        return f"{exp}.{hmac.new(segredo.encode(), f'admin:{usuario}:{exp}'.encode(), hashlib.sha256).hexdigest()}"

    def checar(request: Request) -> None:
        v = request.cookies.get(COOKIE, "")
        exp = v.split(".")[0]
        if not usuario or not senha or not exp.isdigit() or int(exp) < time.time() or not hmac.compare_digest(v, assinar(int(exp))):
            raise HTTPException(401, "entre no painel")

    @r.post("/entrar")
    async def entrar(request: Request):
        b = await request.json()
        ok_u = hmac.compare_digest(str(b.get("usuario") or ""), usuario)
        ok_s = hmac.compare_digest(str(b.get("senha") or ""), senha)
        if not usuario or not senha or not (ok_u and ok_s):
            time.sleep(1)
            raise HTTPException(401, "usuário ou senha incorretos")
        resp = JSONResponse({"ok": True})
        resp.set_cookie(COOKIE, assinar(int(time.time()) + 12 * 3600), httponly=True, secure=seguro, samesite="strict", max_age=12 * 3600)
        return resp

    @r.post("/sair")
    def sair():
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE)
        return resp

    @r.get("/resumo")
    def resumo(request: Request):
        checar(request)
        clientes = db.todos(consulta_clientes)
        return {"clientes": clientes, "total": len(clientes), "ativos": sum(1 for c in clientes if c.get("ativo"))}

    @r.get("/skills")
    def listar(request: Request):
        checar(request)
        return {"skills": db.todos("SELECT nome, atualizado, por, length(conteudo) tamanho FROM skills ORDER BY nome")}

    @r.get("/skills/{nome}")
    def ver(nome: str, request: Request):
        checar(request)
        s = db.um("SELECT * FROM skills WHERE nome=?", (nome,))
        if not s:
            raise HTTPException(404, "skill não encontrada")
        s["historico"] = db.todos("SELECT id, salvo, length(conteudo) tamanho FROM skills_historico WHERE nome=? ORDER BY salvo DESC LIMIT 30", (nome,))
        return s

    def guardar_antiga(nome: str) -> None:
        antigo = db.um("SELECT conteudo FROM skills WHERE nome=?", (nome,))
        if antigo:
            db.exec("INSERT INTO skills_historico(nome,conteudo,salvo) VALUES(?,?,?)", (nome, antigo["conteudo"], agora()))

    @r.put("/skills/{nome}")
    async def salvar(nome: str, request: Request):
        checar(request)
        b = await request.json()
        txt = str(b.get("conteudo") or "")
        if not txt.strip() or len(txt) > 200_000:
            raise HTTPException(422, "conteúdo vazio ou grande demais")
        guardar_antiga(nome)
        db.exec("INSERT INTO skills(nome,conteudo,atualizado,por) VALUES(?,?,?,'painel') ON CONFLICT(nome) DO UPDATE SET conteudo=excluded.conteudo, atualizado=excluded.atualizado, por='painel'",
                (nome, txt, agora()))
        return {"ok": True}

    @r.post("/skills/{nome}/restaurar")
    def restaurar(nome: str, request: Request):
        checar(request)
        f = SEMENTES / f"{nome}.md"
        if not f.exists():
            raise HTTPException(404, "sem arquivo no repositório")
        guardar_antiga(nome)
        db.exec("UPDATE skills SET conteudo=?, atualizado=?, por='repositorio' WHERE nome=?", (f.read_text(encoding="utf-8"), agora(), nome))
        return {"ok": True}

    @r.get("/skills/{nome}/historico/{hid}")
    def versao(nome: str, hid: int, request: Request):
        checar(request)
        h = db.um("SELECT * FROM skills_historico WHERE id=? AND nome=?", (hid, nome))
        if not h:
            raise HTTPException(404, "versão não encontrada")
        return h

    return r
