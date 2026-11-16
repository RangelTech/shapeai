"""Login com senha (padrão) + login só com código no e-mail (opção) + esqueci a senha (redefinição).

Módulo idêntico em Anima AI, Rendaí, Perfilaí e Atende AI. A senha fica só como hash PBKDF2-SHA256 (200 mil rodadas, sal próprio).
"Entrar com código" e "esqueci a senha" são caminhos diferentes: o primeiro só entra, o segundo troca a senha.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

from fastapi import HTTPException, Request

from app import auth

RODADAS = 200_000
SENHA_MIN = 8
JANELA_S = 15 * 60
MAX_ERROS = 8
_erros: dict[str, list[float]] = {}
_trava = threading.Lock()


def hash_senha(senha: str) -> str:
    sal = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), RODADAS)
    return f"pbkdf2${RODADAS}${sal}${dk.hex()}"


def conferir_senha(guardado: str | None, senha: str) -> bool:
    try:
        _, rod, sal, h = (guardado or "").split("$")
        dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), int(rod))
        return hmac.compare_digest(dk.hex(), h)
    except (ValueError, TypeError):
        return False


def _bloqueado(email: str) -> bool:
    with _trava:
        lst = [t for t in _erros.get(email, []) if time.time() - t < JANELA_S]
        _erros[email] = lst
        return len(lst) >= MAX_ERROS


def _errou(email: str) -> None:
    with _trava:
        _erros.setdefault(email, []).append(time.time())


def _validar_nova(senha: str) -> str:
    senha = str(senha or "")
    if len(senha) < SENHA_MIN:
        raise HTTPException(422, f"a senha precisa de pelo menos {SENHA_MIN} caracteres")
    if len(senha) > 200:
        raise HTTPException(422, "senha longa demais")
    return senha


def registrar(app, db, cfg, mailer, login, usuario) -> None:
    """login(u) -> resposta com cookie; usuario(request) -> usuário logado (401 se não houver)."""
    cols = {r[1] for r in db.con.execute("PRAGMA table_info(usuarios)")}
    if "senha_hash" not in cols:
        db.con.execute("ALTER TABLE usuarios ADD COLUMN senha_hash TEXT")

    def demo_ok(email: str, senha: str) -> bool:
        de, ds = (getattr(cfg, "demo_email", "") or "").lower(), getattr(cfg, "demo_senha", "") or ""
        return bool(de and ds and email == de and hmac.compare_digest(senha, ds))

    @app.post("/api/entrar/senha")
    async def entrar_senha(request: Request):
        b = await request.json()
        email = auth.normalizar_email(b.get("email"))
        senha = str(b.get("senha") or "")
        if not email or not senha:
            raise HTTPException(400, "preencha e-mail e senha")
        if _bloqueado(email):
            raise HTTPException(429, "muitas tentativas; espere 15 minutos ou entre com código no e-mail")
        if demo_ok(email, senha):
            return login(auth.usuario_por_email(db, email))
        u = db.um("SELECT * FROM usuarios WHERE email=?", (email,))
        if not u or not conferir_senha(u.get("senha_hash"), senha):
            _errou(email)
            if u and not u.get("senha_hash"):
                raise HTTPException(400, "essa conta ainda não tem senha: entre com código no e-mail e crie uma")
            raise HTTPException(400, "e-mail ou senha incorretos")
        return login(u)

    @app.get("/api/senha")
    def tem_senha(request: Request):
        u = usuario(request)
        demo = (getattr(cfg, "demo_email", "") or "").lower()  # demo entra pela senha da configuração
        return {"tem_senha": bool(u.get("senha_hash")) or bool(demo and u["email"] == demo), "email": u["email"]}

    @app.post("/api/senha")
    async def definir_senha(request: Request):
        """Cria a senha (conta sem senha) ou troca (pede a atual)."""
        u = usuario(request)
        b = await request.json()
        nova = _validar_nova(b.get("senha"))
        if u.get("senha_hash") and not conferir_senha(u["senha_hash"], str(b.get("atual") or "")):
            raise HTTPException(400, "a senha atual não confere (esqueceu? use 'Esqueci minha senha' na tela de entrar)")
        db.exec("UPDATE usuarios SET senha_hash=? WHERE id=?", (hash_senha(nova), u["id"]))
        return {"ok": True}

    @app.post("/api/senha/esqueci")
    async def esqueci(request: Request):
        b = await request.json()
        email = auth.normalizar_email(b.get("email"))
        if not email:
            raise HTTPException(422, "e-mail inválido")
        extra = {}
        if db.um("SELECT id FROM usuarios WHERE email=?", (email,)):
            cod, motivo = auth.novo_codigo(db, cfg.segredo_sessao, "redefinir:" + email)
            if motivo == "espere":
                raise HTTPException(429, "acabamos de mandar um código; espere alguns segundos")
            mailer.codigo(cfg, email, cod)
            if getattr(cfg, "dev", False):
                extra["codigo_dev"] = cod
        return {"ok": True, **extra}  # mesma resposta exista ou não a conta

    @app.post("/api/senha/redefinir")
    async def redefinir(request: Request):
        b = await request.json()
        email = auth.normalizar_email(b.get("email"))
        if not email:
            raise HTTPException(422, "e-mail inválido")
        nova = _validar_nova(b.get("senha"))
        r = auth.conferir_codigo(db, cfg.segredo_sessao, "redefinir:" + email, str(b.get("codigo") or ""))
        if r != "ok":
            raise HTTPException(400, {"invalido": "código errado", "expirado": "código vencido; peça outro", "tentativas": "muitas tentativas; peça outro código"}[r])
        u = db.um("SELECT * FROM usuarios WHERE email=?", (email,))
        if not u:
            raise HTTPException(400, "código errado")
        db.exec("UPDATE usuarios SET senha_hash=? WHERE id=?", (hash_senha(nova), u["id"]))
        with _trava:
            _erros.pop(email, None)
        return login(u)
