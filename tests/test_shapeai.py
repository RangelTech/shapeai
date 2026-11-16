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
    cod = c.post("/api/entrar/codigo", json={"email": "bia@x.com"}).json()["codigo_dev"]
    assert c.post("/api/entrar", json={"email": "bia@x.com", "codigo": cod}).status_code == 200
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


def test_rivais_sempre_marcados():
    r = fitness.rivais(1, 300, "2026-46")
    assert all(x["simulado"] and "rival da IA" in x["nome"] for x in r)
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
    assert any(x.get("voce") for x in rk) and sum(1 for x in rk if x["simulado"]) == 6
    assert c.get("/api/conta").json()["kcal_hoje"] == 450


def test_ergogenico_so_registro_medico(amb):
    c = amb
    assert c.post("/api/prescricoes", json={"nome": "X", "dose": "conforme receita", "dias": [0, 3]}).status_code == 422  # sem aceite médico
    pid = c.post("/api/prescricoes", json={"nome": "Medicação prescrita", "dose": "conforme receita", "dias": [0, 3], "aceite_medico": True, "medico": "Dra. Ana"}).json()["id"]
    j = c.get("/api/prescricoes").json()
    assert "não indica substância" in j["aviso"] and len(j["prescricoes"][0]["semana"]) == 7
    assert c.post(f"/api/prescricoes/{pid}/feito").json()["ok"]
    c.post("/api/conversa", json={"texto": "qual dose de tirzepatida eu tomo?"})
    assert "NUNCA sugira, dose" in VISTOS[-1][0]["content"]
