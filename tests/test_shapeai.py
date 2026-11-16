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
    assert "Nandrolona" in sistema and "Tirzepatida" in sistema and "NÃO monte" in sistema
    comp = c.get("/api/protocolo/compostos").json()["compostos"]
    assert any(x["id"] == "sustanon" for x in comp)
    r = c.post("/api/protocolo/curva", json={"itens": [{"composto": "testosterona_enantato", "dose_mg": 250, "a_cada_dias": 3.5, "semanas": 12},
                                                        {"composto": "sustanon", "dose_mg": 250, "a_cada_dias": 7, "semanas": 8}]}).json()
    assert len(r["series"]) == 2 and max(r["total"]) > 300 and r["total"][0] == 0


def test_receita_vira_protocolo(tmp_path):
    lido = json.dumps({"medico": "Dra. Ana CRM 1", "data": "2026-11-10", "observacoes": "exames na 6a semana",
                       "itens": [{"composto": "testosterona_cipionato", "nome_na_receita": "Deposteron", "dose_mg": 100, "a_cada_dias": 7, "semanas": 8, "via": "IM"},
                                 {"composto": "xyz", "nome_na_receita": "Vitamina D", "dose_mg": 0, "a_cada_dias": 1, "semanas": 8}]})
    vistos = []
    cfg = Config(dados=str(tmp_path), segredo_sessao="s", dev=True)
    c = TestClient(criar_app(cfg, llm=lambda m: (vistos.append(m), "ok")[1], visao=lambda m: lido))
    cod = c.post("/api/entrar/codigo", json={"email": "r@x.com"}).json()["codigo_dev"]
    c.post("/api/entrar", json={"email": "r@x.com", "codigo": cod})
    assert c.get("/api/protocolo").json()["ativo"] is None
    d = c.post("/api/receita/ler", content=JPG, headers={"content-type": "image/jpeg"}).json()
    assert d["medico"].startswith("Dra. Ana") and d["itens"][1]["composto"] == "outro" and d["foto"]
    assert c.post("/api/receita/ler", json={"texto": "Deposteron 100 mg semanal"}).json()["itens"]
    assert c.post("/api/protocolo", json={"itens": []}).status_code == 422
    c.post("/api/protocolo", json=d)
    p = c.get("/api/protocolo").json()["ativo"]
    assert p["itens"][0]["nome"].startswith("Testosterona cipionato") and p["curva"]["total"] and "foto" not in p
    assert "Testosterona" in p["itens"][0]["ficha"]
    c.post("/api/conversa", json={"texto": "me explica minha receita"})
    sistema = vistos[-1][0]["content"]
    assert "Deposteron (= Testosterona cipionato): 100 mg a cada 7 dias" in sistema and "NÃO monte" in sistema and "Blast Iniciante" not in sistema
