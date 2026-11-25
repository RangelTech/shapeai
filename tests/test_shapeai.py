from produtos_core.teste import entrar
import json
import os

os.environ["SHAPEAI_SEM_APP"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import fitness  # noqa: E402
from app.config import Config  # noqa: E402
from app.main import criar_app  # noqa: E402

VISTOS = []
JPG = b"\xff\xd8\xff\xe0" + b"0" * 200


def llm_falso(msgs):
    VISTOS.append(msgs)
    u = msgs[-1]["content"]
    if "treino da semana" in u:
        return json.dumps({"dias": [{"dia": "Segunda", "foco": "Peito", "exercicios": [{"nome": "Supino reto", "series": 4, "reps": "10", "descanso_s": 90, "equipamento": "barra", "dica": "x"}]}]})
    if "dieta dos 7 dias" in u:
        return 'Segue: {"dias":[{"dia":"Segunda","refeicoes":[{"horario":"07:00","nome":"Café","itens":[{"alimento":"ovo","quantidade":"3","kcal":210}],"kcal":210}],"kcal_total":210}],}'
    return "Bora! Hoje foca na proteína."


@pytest.fixture
def amb(tmp_path):
    cfg = Config(dados=str(tmp_path), segredo_sessao="s", dev=True, cakto_segredo="ck", planos_por_produto={"p-pro": "pro"})
    c = TestClient(criar_app(cfg, llm=llm_falso))
    entrar(c, "bia@x.com")
    return c


def test_bf_marinha_e_gasto():
    bf = fitness.gordura_marinha("m", 180, 38, 85)
    assert 13 <= bf <= 17 and fitness.categoria_bf("m", bf) in ("atlético", "em forma")
    assert 20 <= fitness.gordura_marinha("f", 165, 32, 72, 98) <= 30
    g = fitness.gasto("m", 80, 180, 30, "moderado", "emagrecer")
    assert g["tmb"] == round(10 * 80 + 6.25 * 180 - 5 * 30 + 5) and g["calorias_alvo"] < g["gasto_diario"] and g["proteina_g"] == 176
    assert fitness.progresso(90, 85, 80) == 50
    with pytest.raises(ValueError):
        fitness.gordura_marinha("f", 165, 32, 72)


def test_rivais_parecem_jogadores():
    r = fitness.rivais(1, 300, "2026-46")
    assert len(r) == 6 and all("IA" not in x["nome"] and "simulado" not in x for x in r)
    rk = sorted(r + [{"nome": "Você", "pontos": 300, "voce": True}], key=lambda x: -x["pontos"])
    a = fitness.alerta(rk)
    assert a["tipo"] == "ameaca" and a["diferenca"] <= 15
    assert r == fitness.rivais(1, 300, "2026-46")


def test_calculadora_publica(amb):
    r = TestClient(amb.app).post("/api/calcular", json={"sexo": "m", "altura_cm": 178, "peso": 82, "idade": 30, "pescoco": 39, "cintura": 90, "atividade": "moderado", "objetivo": "emagrecer"})
    assert r.status_code == 200 and r.json()["bf"] > 10 and r.json()["calorias_alvo"] > 1500


def test_fluxo_completo(amb):
    c = amb
    assert c.post("/api/medidas", json={"peso": 82}).status_code == 409
    c.put("/api/perfil", json={"nome": "Bia Souza", "sexo": "f", "nascimento": "1994-04-10", "altura_cm": 165, "atividade": "moderado", "objetivo": "emagrecer",
                              "rotina": "trabalho 8h-17h, treino 18h", "meta_peso": 62, "meta_bf": 24})
    m = c.post("/api/medidas", json={"data": "2026-11-01", "peso": 70, "pescoco": 32, "cintura": 76, "quadril": 100}).json()
    assert m["medida"]["bf"] and m["gasto"]["calorias_alvo"] and m["ganhou"] == fitness.PONTOS["medida"]
    m = c.post("/api/medidas", json={"data": "2026-11-15", "peso": 66, "pescoco": 32, "cintura": 72, "quadril": 98}).json()
    assert m["metas"]["peso"]["pct"] == 50 and m["ganhou"] == 0  # 2ª medida no mesmo dia não pontua de novo
    t = c.post("/api/plano/treino").json()
    assert t["dias"][0]["exercicios"][0]["video"].startswith("https://www.youtube.com/results?search_query=")
    assert "Calorias alvo" in VISTOS[-1][0]["content"]
    assert c.post("/api/plano/treino").status_code == 402  # refazer é do Pro
    assert c.post("/api/plano/dieta").status_code == 402
    c.post("/api/cakto", json={"secret": "ck", "event": "purchase_approved", "data": {"id": "1", "customer": {"email": "bia@x.com"}, "product": {"id": "p-pro"}}})
    d = c.post("/api/plano/dieta").json()
    assert d["dias"][0]["refeicoes"][0]["horario"] == "07:00"
    assert c.post("/api/checkin", json={"tipo": "treino", "ref": "segunda"}).json()["ganhou"] == 20
    f = c.post("/api/fotos?tipo=refeicao&kcal=450", content=JPG).json()
    assert f["ganhou"] == 10 and c.get(f["url"]).status_code == 200
    assert c.post("/api/fotos?tipo=evolucao", content=b"texto").status_code == 422
    rk = c.get("/api/ranking").json()["ranking"]
    assert any(x.get("voce") for x in rk) and len(rk) == 7 and not any("simulado" in x for x in rk)
    assert c.get("/api/conta").json()["kcal_hoje"] == 450


def test_protocolo_rag_e_curva(amb):
    c = amb
    pid = c.post("/api/prescricoes", json={"nome": "Testosterona enantato", "dose": "250 mg", "dias": [0, 3]}).json()["id"]
    j = c.get("/api/prescricoes").json()
    assert len(j["prescricoes"][0]["semana"]) == 7 and c.post(f"/api/prescricoes/{pid}/feito").json()["ok"]
    c.post("/api/conversa", json={"texto": "qual a dose de deca pra iniciante e como fica a tirzepatida?"})
    sistema = VISTOS[-1][0]["content"]
    assert "Nandrolona" in sistema and "Tirzepatida" in sistema
    assert "Antes de montar qualquer protocolo" in sistema
    assert "Emissão da prescrição" in sistema
    comp = c.get("/api/protocolo/compostos").json()["compostos"]
    assert any(x["id"] == "sustanon" for x in comp)
    r = c.post("/api/protocolo/curva", json={"itens": [{"composto": "testosterona_enantato", "dose_mg": 250, "a_cada_dias": 3.5, "semanas": 12},
                                                        {"composto": "sustanon", "dose_mg": 250, "a_cada_dias": 7, "semanas": 8}]}).json()
    assert len(r["series"]) == 2 and max(r["total"]) > 300 and r["total"][0] == 0


def test_chat_salva_prescricao_no_protocolo(tmp_path):
    estruturado = json.dumps({"pronto": True, "paciente": "Paciente Teste", "medico": "Dra. Ana CRM 1", "data": "2026-11-10",
                              "observacoes": "exames na 6a semana", "itens": [{"composto": "testosterona_cipionato",
                              "nome_na_receita": "Deposteron", "dose_mg": 100, "a_cada_dias": 7, "semanas": 8, "via": "IM"}]})
    vistos = []
    def llm_prescricao(msgs):
        vistos.append(msgs)
        return estruturado if msgs[0]["content"].startswith("Converta a prescrição") else "Proposta para Paciente Teste: Deposteron 100 mg semanal por 8 semanas."
    cfg = Config(dados=str(tmp_path), segredo_sessao="s", dev=True)
    c = TestClient(criar_app(cfg, llm=llm_prescricao))
    entrar(c, "r@x.com")
    assert c.get("/api/protocolo").json()["ativo"] is None
    r = c.post("/api/conversa", json={"texto": "Gere uma prescrição de Deposteron para Paciente Teste"}).json()
    assert r["prescricao_id"] and "Prescrição salva" in r["resposta"]
    p = c.get("/api/protocolo").json()["ativo"]
    assert p["paciente"] == "Paciente Teste" and p["itens"][0]["nome"].startswith("Testosterona cipionato")
    assert p["curva"]["total"] and "foto" not in p
    assert "Testosterona" in p["itens"][0]["ficha"]
    assert "Imprimir prescrição" in c.get("/painel").text
    c.post("/api/conversa", json={"texto": "me explica minha receita"})
    sistema = vistos[-1][0]["content"]
    assert "Deposteron (= Testosterona cipionato): 100 mg a cada 7 dias" in sistema
    assert "Prescrição ativa salva" in sistema


# ---------------- biblioteca de exercícios (RAG por local), séries/1RM e zonas de aplicação (spec 45 D.9.2) ----------------
from app import exercicios  # noqa: E402


def test_praca_nunca_recebe_maquina():
    c = exercicios.candidatos("praca")
    assert c and all(e["equip"] in ("body only", "other", "outro") for e in c)
    maquina = next(e for e in exercicios.BASE if e["equip"] == "machine")
    ex = exercicios.enriquecer({"id": maquina["id"], "nome": "Cadeira extensora"}, "praca")
    assert "imgs" not in ex  # a IA escolheu máquina para quem treina na praça: o servidor não aceita
    ok = exercicios.enriquecer({"id": c[0]["id"]}, "praca")
    assert ok["imgs"][0].endswith("/0.webp") and ok["musculos"]


def test_treino_usa_a_lista_do_local_e_traz_animacao(amb):
    c = amb
    c.put("/api/perfil", json={"nome": "Bia", "sexo": "f", "nascimento": "1994-04-10", "altura_cm": 165, "atividade": "moderado", "objetivo": "emagrecer",
                              "local_treino": "praca", "dias_treino": 3})
    flexao = next(e for e in exercicios.candidatos("praca") if e["prim"])
    VISTOS.clear()
    c.post("/api/plano/treino")
    prompt = VISTOS[-1][-1]["content"]
    assert "Use SOMENTE exercícios desta lista" in prompt and flexao["id"] in prompt and "máquina" not in prompt


def test_series_1rm_e_zonas(amb):
    c = amb
    r = c.post("/api/series", json={"exercicio": "Pushups", "nome": "Flexão", "carga": 0, "reps": 15}).json()
    assert r["rm_atual"] == 0
    r = c.post("/api/series", json={"exercicio": "Barbell_Squat", "nome": "Agachamento", "carga": 100, "reps": 6}).json()
    assert r["rm_atual"] == 120.0 and r["rm_max"] == 120.0
    assert c.post("/api/series", json={"exercicio": "x", "carga": 9999, "reps": 1}).status_code == 422
    z = c.get("/api/zonas", params={"composto": "Tirzepatida"}).json()
    assert z["via"] == "sc" and z["proxima"] == "abdomen_sd"
    z = c.post("/api/zonas", json={"composto": "Tirzepatida", "zona": "abdomen_sd"}).json()
    assert z["proxima"] == "abdomen_se"  # rodízio: nunca o mesmo ponto em seguida
    z = c.get("/api/zonas", params={"composto": "Enantato de testosterona"}).json()
    assert z["via"] == "im" and z["proxima"] == "gluteo_d"
    assert c.post("/api/zonas", json={"composto": "Enantato de testosterona", "zona": "abdomen_sd"}).status_code == 422
