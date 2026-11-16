"""Login sem senha: código de 6 dígitos por e-mail, sessão em cookie (só o hash fica no banco)."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from app.db import Banco, agora

CODIGO_VALIDO_S = 15 * 60
SESSAO_S = 60 * 24 * 3600
MAX_TENTATIVAS = 5
REENVIO_MIN_S = 45
RE_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,24}$", re.I)


def normalizar_email(e: str) -> str | None:
    e = (e or "").strip().lower()
    return e if RE_EMAIL.match(e) else None


def _h(segredo: str, valor: str) -> str:
    return hmac.new(segredo.encode(), valor.encode(), hashlib.sha256).hexdigest()


def novo_codigo(db: Banco, segredo: str, email: str) -> tuple[str | None, str]:
    """Gera e guarda o código. Devolve (codigo, motivo). Sem código quando pediu de novo rápido demais."""
    atual = db.um("SELECT enviado FROM codigos WHERE email=?", (email,))
    if atual and agora() - atual["enviado"] < REENVIO_MIN_S:
        return None, "espere"
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    with db.tx() as c:
        c.execute("INSERT INTO codigos(email,hash,expira,tentativas,enviado) VALUES(?,?,?,0,?) "
                  "ON CONFLICT(email) DO UPDATE SET hash=excluded.hash, expira=excluded.expira, tentativas=0, enviado=excluded.enviado",
                  (email, _h(segredo, email + ":" + codigo), agora() + CODIGO_VALIDO_S, agora()))
    return codigo, "ok"


def conferir_codigo(db: Banco, segredo: str, email: str, codigo: str) -> str:
    """'ok' | 'invalido' | 'expirado' | 'tentativas'"""
    r = db.um("SELECT * FROM codigos WHERE email=?", (email,))
    if not r:
        return "invalido"
    if r["expira"] < agora():
        return "expirado"
    if r["tentativas"] >= MAX_TENTATIVAS:
        return "tentativas"
    if not hmac.compare_digest(r["hash"], _h(segredo, email + ":" + re.sub(r"\D", "", codigo or ""))):
        db.exec("UPDATE codigos SET tentativas=tentativas+1 WHERE email=?", (email,))
        return "invalido"
    db.exec("DELETE FROM codigos WHERE email=?", (email,))
    return "ok"


def usuario_por_email(db: Banco, email: str) -> dict:
    u = db.um("SELECT * FROM usuarios WHERE email=?", (email,))
    if u:
        return u
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO usuarios(email,criado) VALUES(?,?)", (email, agora()))
    return db.um("SELECT * FROM usuarios WHERE email=?", (email,))


def criar_sessao(db: Banco, segredo: str, usuario: int) -> str:
    token = secrets.token_urlsafe(32)
    db.exec("INSERT INTO sessoes(hash,usuario,expira) VALUES(?,?,?)", (_h(segredo, token), usuario, agora() + SESSAO_S))
    return token


def usuario_da_sessao(db: Banco, segredo: str, token: str | None) -> dict | None:
    if not token:
        return None
    s = db.um("SELECT usuario, expira FROM sessoes WHERE hash=?", (_h(segredo, token),))
    if not s or s["expira"] < agora():
        return None
    return db.um("SELECT * FROM usuarios WHERE id=?", (s["usuario"],))


def encerrar_sessao(db: Banco, segredo: str, token: str | None) -> None:
    if token:
        db.exec("DELETE FROM sessoes WHERE hash=?", (_h(segredo, token),))


def assinante(u: dict) -> bool:
    return bool(u) and u.get("ativo_ate", 0) > agora()
