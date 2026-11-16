"""Configuração do Shape AI por variáveis de ambiente (segredos em /opt/platform/secrets/shapeai.env)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    dados: str = "/data"
    base_url: str = "https://shape-ai.rangeltech.net"
    llm_base: str = "http://rt-hermes-produtos:8642/v1"   # toda IA pelo Hermes dos produtos (regra do Lucas, 16/11)
    llm_key: str = ""
    llm_modelo: str = "hermes-produtos"
    segredo_sessao: str = "dev"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_senha: str = ""
    smtp_from: str = "Shape AI <contato@rangeltech.net>"
    cakto_segredo: str = ""
    checkouts: dict = field(default_factory=dict)          # {"plus": "https://pay.cakto.com.br/..."}
    planos_por_produto: dict = field(default_factory=dict)  # {"<id produto Cakto>": "plus"}
    admin_key: str = ""
    demo_email: str = ""
    demo_senha: str = ""
    lancamento_ate: str = "2026-12-15"
    dev: bool = False


def carregar() -> Config:
    e = os.environ.get
    return Config(
        dados=e("SHAPEAI_DADOS", "/data"),
        base_url=e("SHAPEAI_BASE_URL", "https://shape-ai.rangeltech.net").rstrip("/"),
        llm_base=e("SHAPEAI_LLM_BASE", "http://rt-hermes-produtos:8642/v1").rstrip("/"),
        llm_key=e("SHAPEAI_LLM_KEY", ""),
        llm_modelo=e("SHAPEAI_LLM_MODELO", "hermes-produtos"),
        segredo_sessao=e("SHAPEAI_SEGREDO_SESSAO", "dev"),
        smtp_host=e("SMTP_HOST", ""),
        smtp_port=int(e("SMTP_PORT", "587") or 587),
        smtp_user=e("SMTP_USER", ""),
        smtp_senha=e("SMTP_PASSWORD", ""),
        smtp_from=e("SHAPEAI_SMTP_FROM", "Shape AI <contato@rangeltech.net>"),
        cakto_segredo=e("SHAPEAI_CAKTO_SEGREDO", ""),
        checkouts=json.loads(e("SHAPEAI_CHECKOUTS", "") or "{}"),
        planos_por_produto=json.loads(e("SHAPEAI_PLANOS_CAKTO", "") or "{}"),
        admin_key=e("SHAPEAI_ADMIN_KEY", ""),
        demo_email=e("SHAPEAI_DEMO_EMAIL", ""),
        demo_senha=e("SHAPEAI_DEMO_SENHA", ""),
        lancamento_ate=e("SHAPEAI_LANCAMENTO_ATE", "2026-12-15"),
        dev=e("SHAPEAI_DEV", "") == "1",
    )
