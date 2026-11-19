"""Shape AI: personal e nutricionista com IA (Hermes), gamificado. API + páginas no mesmo serviço.

A pessoa conta a rotina e a meta, registra medidas (o BF sai pelo método da Marinha), e a IA monta treino e dieta da semana
em cima das calorias e macros calculados aqui (app/fitness.py). Check-ins dão pontos, nível e sequência; o ranking mistura
pessoas reais com atletas de motivação gerados pela IA (decisão do Lucas, 16/11: aparecem como jogadores normais).
Protocolos (hormônio, tirzepatida, peptídeos): o chat responde e propõe com o material da doutora do projeto loki
(RAG em app/protocolos.py), inclusive montando protocolos por perfil com as dosagens de referência das
planilhas; o painel mostra a curva estimada de cada composto, no estilo do steroidplotter.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import logging
import os
import re
import urllib.parse
import uuid
from pathlib import Path

import httpx
from starlette.concurrency import run_in_threadpool
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import admin, auth, fitness, mailer, protocolos, receita, senha_rotas, exercicios
from app.config import Config, carregar
from app.db import Banco, agora

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("shapeai")
COOKIE = "shapeai_s"
ESTATICO = Path(__file__).resolve().parent.parent / "static"
TZ = dt.timezone(dt.timedelta(hours=-3))
GRATIS_MSGS_DIA = 10
MAX_FOTO = 12 * 1024 * 1024

PLANOS = {
    "pro": {"nome": "Pro", "preco": 39.90, "depois": 59.90,
            "itens": ["Treino da semana com vídeo de cada exercício", "Dieta dia a dia com horários e calorias", "Chat sem limite com o seu coach",
                      "Tabela de substituições pelo chat", "Ranking, níveis e sequência"]},
    "elite": {"nome": "Elite", "preco": 79.90, "depois": 119.90,
              "itens": ["Tudo do Pro", "Planos refeitos toda semana conforme a evolução", "Linha do tempo de fotos ilimitada",
                        "Protocolo hormonal e de tirzepatida com gráfico da curva", "Calendário de aplicações com lembrete", "Prioridade na fila da IA"]},
}

CABECA = """Você é o Shape AI, coach premium da Rangel Tech. Siga a skill shape-ai abaixo em tudo.
Responda SEMPRE à última mensagem do cliente. A RECEITA DO CLIENTE é a verdade sobre os compostos: se uma resposta sua
anterior na conversa disser outra coisa, ela estava errada; corrija sem repetir o erro.
=== SKILL shape-ai ===
{skill}
=== FIM DA SKILL ===
CONTEXTO:
{contexto}
RECEITA DO CLIENTE:
{solicitacoes}
MATERIAL DE REFERÊNCIA (planilha, trechos relevantes):
{material}"""


def criar_app(cfg: Config | None = None, llm=None, visao=None) -> FastAPI:
    cfg = cfg or carregar()
    os.makedirs(cfg.dados, exist_ok=True)
    db = Banco(os.path.join(cfg.dados, "shapeai.db"))
    receita.preparar(db)
    admin.preparar(db)

    def persona(**kw) -> str:
        """Prompt de sistema: a skill shape-ai (editável no /admin) + contexto, prescrição e material."""
        return CABECA.format(skill=admin.skill(db, "shape-ai"), **kw)
    FOTOS = Path(cfg.dados) / "fotos"
    FOTOS.mkdir(exist_ok=True)
    app = FastAPI(title="Shape AI", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.cfg, app.state.db = cfg, db

    def tentar_json(pedido: list[dict], max_tokens: int, vezes: int = 3) -> dict:
        """Plano em JSON: a IA às vezes devolve texto fora do formato; tenta de novo antes de devolver erro."""
        for i in range(vezes):
            try:
                return json_da_ia(chamar_llm(pedido, max_tokens))
            except HTTPException:
                if i == vezes - 1:
                    raise
        return {}

    def chamar_llm(mensagens: list[dict], max_tokens: int = 900) -> str:
        if llm:
            return llm(mensagens)
        r = httpx.post(cfg.llm_base + "/chat/completions", headers={"Authorization": f"Bearer {cfg.llm_key}"}, timeout=300,
                       json={"model": cfg.llm_modelo, "messages": mensagens, "temperature": 0.6, "max_tokens": max_tokens})
        r.raise_for_status()
        return (r.json()["choices"][0]["message"]["content"] or "").strip()

    def json_da_ia(txt: str) -> dict:
        m = re.search(r"\{.*\}", txt or "", re.S)
        if not m:
            raise HTTPException(502, "a IA não devolveu o plano no formato certo; tente de novo")
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)), strict=False)
        except ValueError:
            raise HTTPException(502, "a IA não devolveu o plano no formato certo; tente de novo")

    if cfg.demo_email:
        u = auth.usuario_por_email(db, cfg.demo_email.lower())
        db.exec("INSERT INTO assinaturas(usuario,plano,ativo_ate) VALUES(?,?,?) ON CONFLICT(usuario) DO UPDATE SET plano=excluded.plano, ativo_ate=excluded.ativo_ate",
                (u["id"], "elite", agora() + 3650 * 86400))

    # ------------------------------------------------ ajudantes
    def usuario(request: Request, obrigatorio: bool = True) -> dict | None:
        u = auth.usuario_da_sessao(db, cfg.segredo_sessao, request.cookies.get(COOKIE))
        if not u and obrigatorio:
            raise HTTPException(401, "entre na sua conta")
        return u

    def plano_de(u: dict) -> str | None:
        a = db.um("SELECT * FROM assinaturas WHERE usuario=?", (u["id"],))
        return a["plano"] if a and a["ativo_ate"] > agora() else None

    def exigir_plano(u: dict, oque: str):
        if not plano_de(u):
            raise HTTPException(402, f"{oque} faz parte do plano Pro")

    def hoje() -> str:
        return dt.datetime.now(TZ).date().isoformat()

    def semana() -> str:
        y, w, _ = dt.datetime.now(TZ).isocalendar()
        return f"{y}-{w:02d}"

    def perfil(u: dict) -> dict | None:
        return db.um("SELECT * FROM perfis WHERE usuario=?", (u["id"],))

    def idade(p: dict) -> int:
        n = dt.date.fromisoformat(p["nascimento"])
        h = dt.date.today()
        return h.year - n.year - ((h.month, h.day) < (n.month, n.day))

    def pontos_total(uid: int, desde_dia: str | None = None) -> int:
        q, a = "SELECT COALESCE(SUM(pontos),0) n FROM checkins WHERE usuario=?", [uid]
        if desde_dia:
            q, a = q + " AND dia>=?", a + [desde_dia]
        return int(db.um(q, tuple(a))["n"])

    def sequencia(uid: int) -> int:
        dias = {r["dia"] for r in db.todos("SELECT DISTINCT dia FROM checkins WHERE usuario=? AND dia>=?", (uid, (dt.date.today() - dt.timedelta(days=120)).isoformat()))}
        d, n = dt.datetime.now(TZ).date(), 0
        if d.isoformat() not in dias:
            d -= dt.timedelta(days=1)
        while d.isoformat() in dias:
            n, d = n + 1, d - dt.timedelta(days=1)
        return n

    def pontuar(u: dict, tipo: str, ref: str = "", kcal: float = 0) -> int:
        p = fitness.PONTOS.get(tipo, 0)
        try:
            db.exec("INSERT INTO checkins(usuario,tipo,dia,ref,pontos,kcal,criado) VALUES(?,?,?,?,?,?,?)", (u["id"], tipo, hoje(), ref, p, kcal, agora()))
            return p
        except Exception:  # noqa: BLE001  (mesmo check-in no mesmo dia não pontua duas vezes)
            return 0

    def resumo(u: dict) -> dict:
        p = perfil(u)
        meds = db.todos("SELECT * FROM medidas WHERE usuario=? ORDER BY data, id", (u["id"],))
        ult, prim = (meds[-1] if meds else None), (meds[0] if meds else None)
        out = {"perfil": p, "medida": ult, "plano": plano_de(u), "pontos": fitness.nivel(pontos_total(u["id"])), "sequencia": sequencia(u["id"]),
               "hoje": db.todos("SELECT tipo, ref, pontos, kcal FROM checkins WHERE usuario=? AND dia=?", (u["id"], hoje()))}
        if p and ult and ult.get("peso"):
            out["gasto"] = fitness.gasto(p["sexo"], ult["peso"], p["altura_cm"], idade(p), p["atividade"], p["objetivo"])
            if ult.get("bf"):
                out["categoria_bf"] = fitness.categoria_bf(p["sexo"], ult["bf"])
            metas = {}
            if p.get("meta_peso") and prim.get("peso"):
                metas["peso"] = {"inicio": prim["peso"], "atual": ult["peso"], "alvo": p["meta_peso"], "pct": fitness.progresso(prim["peso"], ult["peso"], p["meta_peso"])}
            bfs = [m for m in meds if m.get("bf")]
            if p.get("meta_bf") and bfs:
                metas["bf"] = {"inicio": bfs[0]["bf"], "atual": bfs[-1]["bf"], "alvo": p["meta_bf"], "pct": fitness.progresso(bfs[0]["bf"], bfs[-1]["bf"], p["meta_bf"])}
            out["metas"] = metas
        out["kcal_hoje"] = round(sum(c["kcal"] for c in out["hoje"]))
        return out

    def contexto(u: dict) -> str:
        r = resumo(u)
        p = r["perfil"]
        if not p:
            return "A pessoa ainda não preencheu o perfil."
        m = r["medida"] or {}
        g = r.get("gasto") or {}
        return (f"{p['nome']}, {'homem' if p['sexo'] == 'm' else 'mulher'}, {idade(p)} anos, {p['altura_cm']} cm, objetivo: {p['objetivo']}, atividade: {p['atividade']}.\n"
                f"Rotina: {p['rotina'] or 'não informada'}. Restrições/preferências: {p['restricoes'] or 'nenhuma'}.\n"
                f"Treina {p['dias_treino']}x/semana, {p['minutos_treino']} min, em: {exercicios.LOCAIS[exercicios.normalizar_local(p['local_treino'])][0]}.\n"
                f"Última medida: peso {m.get('peso')} kg, BF {m.get('bf')}% ({r.get('categoria_bf', '?')}), cintura {m.get('cintura')} cm.\n"
                f"Calorias alvo {g.get('calorias_alvo')} kcal; proteína {g.get('proteina_g')} g, carboidrato {g.get('carboidrato_g')} g, gordura {g.get('gordura_g')} g; água {g.get('agua_ml')} ml.\n"
                f"Metas: peso {p.get('meta_peso')} kg, BF {p.get('meta_bf')}%. Nível {r['pontos']['nivel']}, sequência de {r['sequencia']} dias.\n"
                f"Ranking da semana: {(fitness.alerta(placar(u)) or {}).get('texto', 'sem dados')}")

    def video(nome: str) -> str:
        return "https://www.youtube.com/results?search_query=" + urllib.parse.quote(f"{nome} execução correta shorts")

    @app.exception_handler(json.JSONDecodeError)
    async def corpo_invalido(request: Request, exc: Exception):
        return JSONResponse({"detail": "corpo inválido (envie JSON)"}, status_code=400)

    @app.get("/health")
    def health():
        return {"ok": True}

    # ------------------------------------------------ login
    def _login(u: dict) -> JSONResponse:
        token = auth.criar_sessao(db, cfg.segredo_sessao, u["id"])
        resp = JSONResponse({"ok": True})
        resp.set_cookie(COOKIE, token, max_age=auth.SESSAO_S, httponly=True, secure=not cfg.dev, samesite="lax", path="/")
        return resp

    @app.post("/api/entrar/codigo")
    async def pedir_codigo(request: Request):
        b = await request.json()
        email = auth.normalizar_email(b.get("email"))
        if not email:
            raise HTTPException(422, "e-mail inválido")
        cod, motivo = auth.novo_codigo(db, cfg.segredo_sessao, email)
        if motivo == "espere":
            raise HTTPException(429, "acabamos de mandar um código; espere alguns segundos")
        out = {"ok": True, "enviado": mailer.codigo(cfg, email, cod)}
        if cfg.dev:
            out["codigo_dev"] = cod
        return out

    @app.post("/api/entrar")
    async def entrar(request: Request):
        b = await request.json()
        email = auth.normalizar_email(b.get("email"))
        if not email:
            raise HTTPException(422, "e-mail inválido")
        r = auth.conferir_codigo(db, cfg.segredo_sessao, email, str(b.get("codigo") or ""))
        if r != "ok":
            raise HTTPException(400, {"invalido": "código errado", "expirado": "código vencido; peça outro", "tentativas": "muitas tentativas; peça outro código"}[r])
        return _login(auth.usuario_por_email(db, email))

    senha_rotas.registrar(app, db, cfg, mailer, _login, usuario)

    @app.post("/api/sair")
    def sair(request: Request):
        auth.encerrar_sessao(db, cfg.segredo_sessao, request.cookies.get(COOKIE))
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @app.get("/api/planos")
    def planos():
        return {"planos": [{"codigo": k, **v, "checkout": cfg.checkouts.get(k) or "", "lancamento_ate": cfg.lancamento_ate} for k, v in PLANOS.items()]}

    @app.post("/api/calcular")
    async def calcular_publico(request: Request):
        """Calculadora da página (sem login): BF + calorias."""
        b = await request.json()
        try:
            sexo = "f" if str(b.get("sexo")) == "f" else "m"
            alt, peso, idade_ = float(b["altura_cm"]), float(b["peso"]), int(b["idade"])
            bf = fitness.gordura_marinha(sexo, alt, float(b["pescoco"]), float(b["cintura"]), float(b.get("quadril") or 0) or None)
        except (KeyError, TypeError, ValueError) as e:
            claro = isinstance(e, ValueError) and any(p in str(e) for p in ("cintura", "quadril", "medidas"))
            raise HTTPException(422, str(e) if claro else "confira as medidas")
        return {"bf": bf, "categoria": fitness.categoria_bf(sexo, bf),
                **fitness.gasto(sexo, peso, alt, idade_, str(b.get("atividade") or "moderado"), str(b.get("objetivo") or "emagrecer"))}

    # ------------------------------------------------ perfil, medidas, metas
    @app.get("/api/conta")
    def conta(request: Request):
        u = usuario(request)
        return {"email": u["email"], "tem_senha": bool(u.get("senha_hash")), **resumo(u), "planos": planos()["planos"]}

    @app.put("/api/perfil")
    async def salvar_perfil(request: Request):
        u = usuario(request)
        b = await request.json()
        try:
            dt.date.fromisoformat(str(b.get("nascimento")))
            alt = float(b.get("altura_cm"))
        except (TypeError, ValueError):
            raise HTTPException(422, "confira a data de nascimento e a altura")
        if not 120 <= alt <= 230:
            raise HTTPException(422, "altura em centímetros (ex.: 175)")
        num = lambda k: float(b[k]) if b.get(k) not in (None, "") else None  # noqa: E731
        db.exec("""INSERT INTO perfis(usuario,nome,sexo,nascimento,altura_cm,atividade,objetivo,rotina,restricoes,dias_treino,minutos_treino,local_treino,meta_peso,meta_bf,atualizado)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(usuario) DO UPDATE SET nome=excluded.nome, sexo=excluded.sexo, nascimento=excluded.nascimento,
                   altura_cm=excluded.altura_cm, atividade=excluded.atividade, objetivo=excluded.objetivo, rotina=excluded.rotina, restricoes=excluded.restricoes,
                   dias_treino=excluded.dias_treino, minutos_treino=excluded.minutos_treino, local_treino=excluded.local_treino, meta_peso=excluded.meta_peso,
                   meta_bf=excluded.meta_bf, atualizado=excluded.atualizado""",
                (u["id"], str(b.get("nome") or "").strip()[:80] or "Você", "f" if b.get("sexo") == "f" else "m", str(b.get("nascimento")), alt,
                 b.get("atividade") if b.get("atividade") in fitness.ATIVIDADE else "moderado",
                 b.get("objetivo") if b.get("objetivo") in fitness.OBJETIVOS else "emagrecer",
                 str(b.get("rotina") or "")[:600], str(b.get("restricoes") or "")[:400], max(1, min(int(b.get("dias_treino") or 4), 7)),
                 max(15, min(int(b.get("minutos_treino") or 60), 180)), exercicios.normalizar_local(b.get("local_treino")),
                 num("meta_peso"), num("meta_bf"), agora()))
        return resumo(u)

    @app.post("/api/medidas")
    async def nova_medida(request: Request):
        u = usuario(request)
        p = perfil(u)
        if not p:
            raise HTTPException(409, "preencha o perfil antes")
        b = await request.json()
        num = lambda k: float(b[k]) if b.get(k) not in (None, "") else None  # noqa: E731
        data = str(b.get("data") or hoje())
        bf = None
        if num("pescoco") and num("cintura") and (p["sexo"] == "m" or num("quadril")):
            try:
                bf = fitness.gordura_marinha(p["sexo"], p["altura_cm"], num("pescoco"), num("cintura"), num("quadril"))
            except ValueError as e:
                raise HTTPException(422, str(e))
        db.exec("INSERT INTO medidas(usuario,data,peso,pescoco,cintura,quadril,braco,coxa,bf,criado) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (u["id"], data, num("peso"), num("pescoco"), num("cintura"), num("quadril"), num("braco"), num("coxa"), bf, agora()))
        ganho = pontuar(u, "medida")
        return {**resumo(u), "ganhou": ganho}

    @app.get("/api/medidas")
    def medidas(request: Request):
        u = usuario(request)
        return {"medidas": db.todos("SELECT * FROM medidas WHERE usuario=? ORDER BY data, id", (u["id"],))}

    # ------------------------------------------------ fotos (evolução, prato, academia)
    @app.post("/api/fotos")
    async def subir_foto(request: Request):
        u = usuario(request)
        tipo = request.query_params.get("tipo") or "evolucao"
        if tipo not in ("evolucao", "refeicao", "academia"):
            raise HTTPException(422, "tipo de foto inválido")
        if tipo == "evolucao" and plano_de(u) != "elite" and db.um("SELECT COUNT(*) n FROM fotos WHERE usuario=? AND tipo='evolucao'", (u["id"],))["n"] >= 6:
            raise HTTPException(402, "a linha do tempo ilimitada é do plano Elite")
        dados = await request.body()
        if not dados or len(dados) > MAX_FOTO:
            raise HTTPException(413, "foto vazia ou maior que 12 MB")
        if not (dados[:3] == b"\xff\xd8\xff" or dados[:8] == b"\x89PNG\r\n\x1a\n" or dados[8:12] == b"WEBP"):
            raise HTTPException(422, "mande JPG, PNG ou WEBP")
        nome = uuid.uuid4().hex + ".jpg"
        (FOTOS / nome).write_bytes(dados)
        db.exec("INSERT INTO fotos(nome,usuario,tipo,legenda,criado) VALUES(?,?,?,?,?)", (nome, u["id"], tipo, str(request.query_params.get("legenda") or "")[:200], agora()))
        kcal = float(request.query_params.get("kcal") or 0) if tipo == "refeicao" else 0
        ganho = pontuar(u, {"evolucao": "foto_evolucao", "refeicao": "refeicao_foto", "academia": "treino"}[tipo], ref=nome if tipo == "refeicao" else "", kcal=kcal)
        return {"nome": nome, "url": f"/api/fotos/{nome}", "ganhou": ganho}

    @app.get("/api/fotos")
    def fotos(request: Request, tipo: str = "evolucao"):
        u = usuario(request)
        return {"fotos": [{**f, "url": f"/api/fotos/{f['nome']}"} for f in db.todos("SELECT * FROM fotos WHERE usuario=? AND tipo=? ORDER BY criado", (u["id"], tipo))]}

    @app.get("/api/fotos/{nome}")
    def ver_foto(nome: str, request: Request):
        u = usuario(request)
        if not re.fullmatch(r"[0-9a-f]{32}\.jpg", nome) or not db.um("SELECT 1 FROM fotos WHERE nome=? AND usuario=?", (nome, u["id"])):
            raise HTTPException(404, "não encontrado")
        return FileResponse(FOTOS / nome)

    # ------------------------------------------------ planos da IA (treino e dieta)
    @app.post("/api/plano/treino")
    def gerar_treino(request: Request):
        u = usuario(request)
        if not perfil(u):
            raise HTTPException(409, "preencha o perfil antes")
        if not plano_de(u) and db.um("SELECT 1 FROM planos WHERE usuario=? AND tipo='treino'", (u["id"],)):
            raise HTTPException(402, "refazer o treino toda semana é do plano Pro")
        pedido = [{"role": "system", "content": persona(contexto=contexto(u), solicitacoes="(não se aplica)", material="(não se aplica)")},
                  {"role": "user", "content": "Monte o meu treino da semana respeitando dias, minutos e o LOCAL onde eu treino. No máximo 6 exercícios por dia; "
                                              "dica com até 8 palavras. Use SOMENTE exercícios desta lista (são os possíveis no meu local), copiando o id exato:\n"
                                              f"{exercicios.texto_candidatos(exercicios.candidatos(perfil(u)['local_treino']))}\n"
                                              "Responda SÓ com JSON, sem texto antes ou depois: "
                                              '{"dias":[{"dia":"Segunda","foco":"...","exercicios":[{"id":"<id da lista>","nome":"<nome em português>","series":4,"reps":"10-12","descanso_s":60,'
                                              '"dica":"..."}]}],"observacoes":"..."}'}]
        d = tentar_json(pedido, 5000)
        local = perfil(u)["local_treino"]
        for dia in d.get("dias") or []:
            dia["exercicios"] = [exercicios.enriquecer(ex, local) for ex in (dia.get("exercicios") or [])]
            for ex in dia["exercicios"]:
                ex["video"] = video(str(ex.get("nome_en") or ex.get("nome") or ""))
            dia["musculos"] = sorted({m for ex in dia["exercicios"] for m in ex.get("musculos", [])})
        pid = db.exec("INSERT INTO planos(usuario,tipo,dados,criado) VALUES(?,?,?,?)", (u["id"], "treino", json.dumps(d, ensure_ascii=False), agora())).lastrowid
        return {"id": pid, **d}

    @app.post("/api/plano/dieta")
    def gerar_dieta(request: Request):
        u = usuario(request)
        exigir_plano(u, "A dieta dia a dia")
        r = resumo(u)
        if not r.get("gasto"):
            raise HTTPException(409, "registre o seu peso nas medidas antes")
        pedido_dieta = [{"role": "system", "content": persona(contexto=contexto(u), solicitacoes="(não se aplica)", material="(não se aplica)")},
                          {"role": "user", "content": f"Monte a minha dieta dos 7 dias com horários pela minha rotina, perto de {r['gasto']['calorias_alvo']} kcal/dia "
                                                      f"e {r['gasto']['proteina_g']} g de proteína. Comida brasileira, fácil de achar. Responda SÓ com JSON: "
                                                      '{"dias":[{"dia":"Segunda","refeicoes":[{"horario":"07:00","nome":"Café da manhã","itens":[{"alimento":"...",'
                                                      '"quantidade":"...","kcal":0}],"kcal":0}],"kcal_total":0}],"dicas":"..."}'}]
        d = tentar_json(pedido_dieta, 6000)
        pid = db.exec("INSERT INTO planos(usuario,tipo,dados,criado) VALUES(?,?,?,?)", (u["id"], "dieta", json.dumps(d, ensure_ascii=False), agora())).lastrowid
        return {"id": pid, **d}

    @app.get("/api/plano/{tipo}")
    def ver_plano(tipo: str, request: Request):
        u = usuario(request)
        p = db.um("SELECT * FROM planos WHERE usuario=? AND tipo=? ORDER BY criado DESC LIMIT 1", (u["id"], tipo))
        return {"id": p["id"], "criado": p["criado"], **json.loads(p["dados"])} if p else {}

    # ------------------------------------------------ check-ins, ranking
    @app.post("/api/checkin")
    async def checkin(request: Request):
        u = usuario(request)
        b = await request.json()
        tipo = str(b.get("tipo") or "")
        if tipo not in ("treino", "agua", "sono"):
            raise HTTPException(422, "check-in inválido")
        ganho = pontuar(u, tipo, ref=str(b.get("ref") or "")[:80])
        return {**resumo(u), "ganhou": ganho}

    def placar(u: dict) -> list[dict]:
        hoje_ = dt.datetime.now(TZ).date()
        ini = (hoje_ - dt.timedelta(days=hoje_.weekday())).isoformat()
        reais = db.todos("""SELECT c.usuario, COALESCE(p.nome,'Atleta') nome, SUM(c.pontos) pontos FROM checkins c LEFT JOIN perfis p ON p.usuario=c.usuario
                            WHERE c.dia>=? GROUP BY c.usuario ORDER BY pontos DESC LIMIT 30""", (ini,))
        meus = next((r["pontos"] for r in reais if r["usuario"] == u["id"]), 0)

        def curto(nome: str) -> str:
            p = nome.split()
            return p[0] + (f" {p[-1][0]}." if len(p) > 1 else "")
        lista = [{"nome": curto(r["nome"]) + (" (você)" if r["usuario"] == u["id"] else ""), "pontos": int(r["pontos"]), "voce": r["usuario"] == u["id"]} for r in reais]
        if not any(x["voce"] for x in lista):
            lista.append({"nome": "Você", "pontos": 0, "voce": True})
        lista += fitness.rivais(u["id"], meus, semana(), hoje_.weekday())
        lista.sort(key=lambda x: (-x["pontos"], not x.get("voce")))
        return [{**x, "posicao": i + 1} for i, x in enumerate(lista)]

    # ------------------------------------------------ biblioteca, séries (1RM) e zonas de aplicação
    @app.get("/api/locais")
    def locais():
        return {"locais": [{"id": k, "nome": v[0]} for k, v in exercicios.LOCAIS.items()], "musculos": exercicios.MUSCULOS_PT}

    def serie_resumo(u: dict, ex: str) -> dict:
        hist = db.todos("SELECT carga, reps, criado FROM series WHERE usuario=? AND exercicio=? ORDER BY criado", (u["id"], ex))
        pts = [{"dia": dt.date.fromtimestamp(h["criado"]).isoformat(), "rm": exercicios.um_rm(h["carga"], h["reps"]), "carga": h["carga"], "reps": h["reps"]} for h in hist]
        return {"exercicio": ex, "series": pts[-30:], "rm_atual": pts[-1]["rm"] if pts else None, "rm_max": max((x["rm"] for x in pts), default=None)}

    @app.post("/api/series")
    async def registrar_serie(request: Request):
        u = usuario(request)
        b = await request.json()
        ex = str(b.get("exercicio") or "")[:80]
        try:
            carga, reps = float(b.get("carga") or 0), int(b.get("reps") or 0)
        except (TypeError, ValueError):
            raise HTTPException(422, "carga e repetições em números")
        if not ex or not 0 <= carga <= 600 or not 1 <= reps <= 100:
            raise HTTPException(422, "confira a carga (kg) e as repetições")
        db.exec("INSERT INTO series(usuario,exercicio,nome,carga,reps,criado) VALUES(?,?,?,?,?,?)", (u["id"], ex, str(b.get("nome") or ex)[:80], carga, reps, agora()))
        return serie_resumo(u, ex)

    @app.get("/api/series")
    def ver_series(request: Request, ex: str = ""):
        u = usuario(request)
        if ex:
            return serie_resumo(u, ex)
        ult = db.todos("SELECT exercicio, nome, MAX(criado) c FROM series WHERE usuario=? GROUP BY exercicio ORDER BY c DESC LIMIT 20", (u["id"],))
        return {"exercicios": [serie_resumo(u, x["exercicio"]) | {"nome": x["nome"]} for x in ult]}

    def zonas_de(u: dict, composto: str) -> dict:
        via = exercicios.via_do_composto(composto)
        ult = db.todos("SELECT zona, dia, composto FROM zonas_aplicadas WHERE usuario=? AND via=? ORDER BY criado DESC LIMIT 12", (u["id"], via))
        return {"via": via, "zonas": exercicios.ZONAS[via], "nomes": exercicios.NOMES_ZONA, "proxima": exercicios.proxima_zona(via, [a["zona"] for a in ult]), "ultimas": ult}

    @app.get("/api/zonas")
    def ver_zonas(request: Request, composto: str = ""):
        return zonas_de(usuario(request), composto)

    @app.post("/api/zonas")
    async def registrar_zona(request: Request):
        u = usuario(request)
        b = await request.json()
        comp = str(b.get("composto") or "")[:60]
        via = exercicios.via_do_composto(comp)
        zona = str(b.get("zona") or "")
        if zona not in exercicios.ZONAS[via]:
            raise HTTPException(422, "zona inválida para esta via de aplicação")
        db.exec("INSERT INTO zonas_aplicadas(usuario,composto,via,zona,dia,criado) VALUES(?,?,?,?,?,?)", (u["id"], comp, via, zona, exercicios.hoje(), agora()))
        return zonas_de(u, comp)

    @app.get("/api/ranking")
    def ranking(request: Request):
        u = usuario(request)
        lista = placar(u)
        return {"semana": semana(), "ranking": lista, "alerta": fitness.alerta(lista)}

    # ------------------------------------------------ protocolo: curva estimada (estilo steroidplotter) e calendário
    @app.get("/api/protocolo/compostos")
    def compostos():
        return {"compostos": [{"id": k, "nome": v[0]} for k, v in protocolos.COMPOSTOS.items()]}

    def ficha(chave: str) -> str:
        nome = protocolos.COMPOSTOS.get(chave, ("",))[0].split(" (")[0].split(" ")[0].lower()
        alvo = next((t for t in protocolos.BASE if nome and nome in t["titulo"].lower()), None)
        return alvo["texto"] if alvo else ""

    @app.get("/api/protocolo")
    def meu_protocolo(request: Request):
        u = usuario(request)
        p = receita.ativo(db, u["id"])
        if not p:
            return {"ativo": None}
        for i in p["itens"]:
            i["nome"] = protocolos.COMPOSTOS.get(i["composto"], (i["nome_na_receita"] or "Outro",))[0]
            i["ficha"] = ficha(i["composto"])
        plot = [i for i in p["itens"] if i["composto"] in protocolos.COMPOSTOS]
        p["curva"] = protocolos.curva(plot) if plot else None
        p.pop("foto", None)
        return {"ativo": p}

    @app.post("/api/protocolo")
    async def salvar_protocolo(request: Request):
        u = usuario(request)
        b = await request.json()
        try:
            pid = receita.salvar(db, u["id"], b, str(b.get("foto") or "")[:40])
        except ValueError as e:
            raise HTTPException(422, str(e))
        return {"id": pid}

    @app.post("/api/protocolo/curva")
    async def curva(request: Request):
        usuario(request)
        b = await request.json()
        return protocolos.curva(b.get("itens") or [], b.get("dias"))

    @app.get("/api/prescricoes")
    def prescricoes(request: Request):
        u = usuario(request)
        ini = dt.datetime.now(TZ).date() - dt.timedelta(days=dt.datetime.now(TZ).weekday())
        dias = [(ini + dt.timedelta(days=i)).isoformat() for i in range(7)]
        itens = db.todos("SELECT * FROM prescricoes WHERE usuario=? ORDER BY criado", (u["id"],))
        feitas = {(a["prescricao"], a["dia"]) for a in db.todos("SELECT prescricao, dia FROM aplicacoes WHERE usuario=? AND dia>=?", (u["id"], dias[0]))}
        for p in itens:
            p["dias"] = json.loads(p["dias"])
            p["semana"] = [{"dia": d, "previsto": dt.date.fromisoformat(d).weekday() in p["dias"], "feito": (p["id"], d) in feitas} for d in dias]
        return {"prescricoes": itens, "aviso": "Seu protocolo: marque cada aplicação e acompanhe os exames da fase."}

    @app.post("/api/prescricoes")
    async def nova_prescricao(request: Request):
        u = usuario(request)
        b = await request.json()
        nome, dose = str(b.get("nome") or "").strip()[:80], str(b.get("dose") or "").strip()[:80]
        dias = sorted({int(d) for d in b.get("dias") or [] if str(d).isdigit() and 0 <= int(d) <= 6})
        if not nome or not dose or not dias:
            raise HTTPException(422, "informe o nome, a dose e os dias")
        pid = db.exec("INSERT INTO prescricoes(usuario,nome,dose,dias,horario,medico,observacao,criado) VALUES(?,?,?,?,?,?,?,?)",
                      (u["id"], nome, dose, json.dumps(dias), str(b.get("horario") or "")[:5], str(b.get("medico") or "")[:80],
                       str(b.get("observacao") or "")[:300], agora())).lastrowid
        return {"id": pid}

    @app.post("/api/prescricoes/{pid}/feito")
    def prescricao_feita(pid: int, request: Request):
        u = usuario(request)
        if not db.um("SELECT 1 FROM prescricoes WHERE id=? AND usuario=?", (pid, u["id"])):
            raise HTTPException(404, "não encontrado")
        try:
            db.exec("INSERT INTO aplicacoes(prescricao,usuario,dia,criado) VALUES(?,?,?,?)", (pid, u["id"], hoje(), agora()))
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True}

    @app.delete("/api/prescricoes/{pid}")
    def apagar_prescricao(pid: int, request: Request):
        u = usuario(request)
        db.exec("DELETE FROM aplicacoes WHERE prescricao=? AND usuario=?", (pid, u["id"]))
        db.exec("DELETE FROM prescricoes WHERE id=? AND usuario=?", (pid, u["id"]))
        return {"ok": True}

    # ------------------------------------------------ chat com o coach
    @app.get("/api/conversa")
    def conversa(request: Request):
        u = usuario(request)
        return {"mensagens": db.todos("SELECT papel, texto, criado FROM mensagens WHERE usuario=? ORDER BY criado DESC, id DESC LIMIT 60", (u["id"],))[::-1]}

    @app.post("/api/conversa")
    async def falar(request: Request):
        u = usuario(request)
        b = await request.json()
        texto = str(b.get("texto") or "").strip()[:1500]
        if not texto:
            raise HTTPException(422, "escreva a sua pergunta")
        if not plano_de(u):
            ini = dt.datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            if db.um("SELECT COUNT(*) n FROM mensagens WHERE usuario=? AND papel='usuario' AND criado>=?", (u["id"], ini))["n"] >= GRATIS_MSGS_DIA:
                raise HTTPException(402, f"as {GRATIS_MSGS_DIA} mensagens grátis de hoje acabaram; no Pro o chat é sem limite")
        hist = db.todos("SELECT papel, texto FROM mensagens WHERE usuario=? ORDER BY criado DESC, id DESC LIMIT 14", (u["id"],))[::-1]
        material = protocolos.contexto_rag(" ".join([m["texto"] for m in hist[-2:] if m["papel"] == "usuario"] + [texto])) or "(nada específico; responda pelo seu conhecimento)"
        msgs = [{"role": "system", "content": persona(contexto=contexto(u), solicitacoes=receita.contexto(db, u["id"]), material=material)}]
        msgs += [{"role": "user" if m["papel"] == "usuario" else "assistant", "content": m["texto"]} for m in hist]
        msgs.append({"role": "user", "content": texto})
        db.exec("INSERT INTO mensagens(usuario,papel,texto,criado) VALUES(?,?,?,?)", (u["id"], "usuario", texto, agora()))
        try:
            resposta = await run_in_threadpool(chamar_llm, msgs, 3000)
        except Exception:  # noqa: BLE001
            raise HTTPException(502, "o coach não respondeu agora; tente de novo em instantes")
        prescricao_id = None
        # Pedido explícito de emissão: a conversa continua natural, e uma segunda chamada
        # estrutura a prescrição para o mesmo registro que abastece a aba Hormônios.
        verbo_emissao = re.search(r"\b(gerar|gere|criar|crie|monte|montar|prescreva|prescrever|emita|emitir)\b", texto, re.I)
        alvo_prescricao = re.search(r"\b(prescri[cç][aã]o|receita|ciclo|protocolo|tirzepatida|mounjaro|horm[oô]nio)\b", texto, re.I)
        emitir = verbo_emissao and alvo_prescricao
        if emitir:
            instrucao = """Converta a prescrição/protocolo que você acabou de propor em JSON para o prontuário.
Use somente os medicamentos e dados clínicos que já constam na conversa e na sua proposta. Não invente nem complete dose, intervalo ou duração; se algum campo necessário estiver ausente, devolva pronto=false e lista os campos em faltantes.
Formato EXATO: {"pronto":true,"paciente":"nome do paciente, se informado","medico":"","data":"AAAA-MM-DD","observacoes":"","itens":[{"composto":"id conhecido ou outro","nome_na_receita":"nome","dose_mg":0,"a_cada_dias":7,"semanas":1,"inicio_semana":0,"via":"IM/SC/oral","obs":""}],"faltantes":[]}
Cada item exige dose_mg maior que zero e a_cada_dias e semanas explicitamente definidos. Não inclua explicações fora do JSON."""
            estruturar = [{"role": "system", "content": instrucao},
                          {"role": "user", "content": "Pedido do médico: " + texto + "\nProposta da IA: " + resposta}]
            try:
                bruto = await run_in_threadpool(chamar_llm, estruturar, 1800)
                dado = json_da_ia(bruto)
                brutos = dado.get("itens") or []
                itens = receita.itens_validos(brutos)
                try:
                    campos_clinicos = all(float(x["dose_mg"]) > 0 and float(x["a_cada_dias"]) > 0
                                          and int(float(x["semanas"])) > 0 for x in brutos)
                except (TypeError, ValueError, KeyError):
                    campos_clinicos = False
                completos = dado.get("pronto") is True and itens and len(itens) == len(brutos) and campos_clinicos
                if completos:
                    if not str(dado.get("data") or "").strip():
                        dado["data"] = dt.datetime.now(TZ).date().isoformat()
                    prescricao_id = receita.salvar(db, u["id"], {**dado, "itens": itens})
                    resposta += "\n\nPrescrição salva na aba Hormônios. O botão Imprimir prepara o documento para assinatura."
                elif dado.get("faltantes"):
                    resposta += "\n\nAinda não salvei a prescrição: faltam dados explícitos para " + ", ".join(map(str, dado["faltantes"])) + "."
                else:
                    resposta += "\n\nNão consegui registrar a prescrição: a IA não devolveu todos os campos em formato válido."
            except Exception:  # noqa: BLE001
                logging.exception("falha ao estruturar prescrição do chat")
                resposta += "\n\nNão consegui registrar a prescrição agora. Tente novamente."
        db.exec("INSERT INTO mensagens(usuario,papel,texto,criado) VALUES(?,?,?,?)", (u["id"], "ia", resposta, agora()))
        return {"resposta": resposta, "prescricao_id": prescricao_id}

    # ------------------------------------------------ Cakto
    @app.post("/api/cakto")
    async def cakto(request: Request):
        cru = await request.body()
        try:
            b = json.loads(cru)
        except ValueError:
            raise HTTPException(400, "json")
        if not cfg.cakto_segredo or not hmac.compare_digest(str(b.get("secret") or ""), cfg.cakto_segredo):
            raise HTTPException(401, "segredo")
        evento = str(b.get("event") or "")
        dados = b.get("data") or {}
        if isinstance(dados, list):
            dados = dados[0] if dados else {}
        eid = str(dados.get("id") or hashlib.sha256(cru).hexdigest()[:24]) + ":" + evento
        if db.um("SELECT 1 FROM eventos_cakto WHERE id=?", (eid,)):
            return {"ok": True, "repetido": True}
        db.exec("INSERT INTO eventos_cakto(id,recebido,corpo) VALUES(?,?,?)", (eid, agora(), cru.decode("utf-8", "replace")[:20000]))
        email = auth.normalizar_email((dados.get("customer") or {}).get("email"))
        plano = cfg.planos_por_produto.get(str((dados.get("product") or {}).get("id") or ""))
        if not email or plano not in PLANOS:
            return {"ok": True, "ignorado": "sem email ou produto desconhecido"}
        u = auth.usuario_por_email(db, email)
        a = db.um("SELECT * FROM assinaturas WHERE usuario=?", (u["id"],))
        if evento in ("purchase_approved", "subscription_renewed", "subscription_created"):
            base = max(agora(), a["ativo_ate"] if a else 0)
            db.exec("INSERT INTO assinaturas(usuario,plano,ativo_ate,pedido) VALUES(?,?,?,?) ON CONFLICT(usuario) DO UPDATE SET plano=excluded.plano, ativo_ate=excluded.ativo_ate, pedido=excluded.pedido",
                    (u["id"], plano, base + 32 * 86400, str(dados.get("id") or "")))
            return {"ok": True, "liberado": email}
        if evento in ("refund", "chargeback", "subscription_canceled", "subscription_cancelled"):
            db.exec("UPDATE assinaturas SET ativo_ate=? WHERE usuario=?", (agora(), u["id"]))
            return {"ok": True, "revogado": email}
        return {"ok": True, "ignorado": evento}

    app.include_router(admin.rotas(db, cfg.segredo_sessao, """SELECT u.email, u.criado, a.plano, a.ativo_ate, (a.ativo_ate > strftime('%s','now')) ativo
        FROM usuarios u LEFT JOIN assinaturas a ON a.usuario=u.id ORDER BY u.criado DESC""", seguro=not cfg.dev))

    @app.get("/admin", response_class=HTMLResponse)
    def pagina_admin():
        return FileResponse(ESTATICO / "admin.html")

    app.mount("/s", StaticFiles(directory=ESTATICO), name="estatico")

    @app.get("/", response_class=HTMLResponse)
    def inicio():
        return FileResponse(ESTATICO / "index.html")

    @app.get("/painel", response_class=HTMLResponse)
    def painel():
        return FileResponse(ESTATICO / "painel.html")

    return app


app = criar_app() if os.environ.get("SHAPEAI_SEM_APP") != "1" else None
