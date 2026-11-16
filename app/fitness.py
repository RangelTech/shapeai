"""Cálculos do Shape AI, sem IA: gordura corporal (Marinha dos EUA), gasto calórico (Mifflin-St Jeor), macros, progresso e pontos.
A IA (Hermes) monta treino e dieta EM CIMA destes números; ela não inventa caloria nem BF.
"""
from __future__ import annotations

import math
import random

ATIVIDADE = {"sedentario": 1.2, "leve": 1.375, "moderado": 1.55, "intenso": 1.725, "atleta": 1.9}
OBJETIVOS = {"emagrecer": -0.20, "definir": -0.12, "manter": 0.0, "ganhar_massa": 0.10}

PONTOS = {"treino": 20, "refeicao_foto": 10, "medida": 15, "foto_evolucao": 25, "agua": 5, "sono": 5}
NIVEIS = [(0, "Iniciante"), (200, "Focado"), (600, "Disciplinado"), (1200, "Atleta"), (2500, "Máquina"), (5000, "Lenda")]


def gordura_marinha(sexo: str, altura_cm: float, pescoco: float, cintura: float, quadril: float | None = None) -> float:
    """% de gordura pelo método da Marinha dos EUA (medidas em cm). Mulher precisa do quadril."""
    if sexo == "m":
        if cintura <= pescoco:
            raise ValueError("a cintura precisa ser maior que o pescoço")
        bf = 495 / (1.0324 - 0.19077 * math.log10(cintura - pescoco) + 0.15456 * math.log10(altura_cm)) - 450
    else:
        if not quadril:
            raise ValueError("para mulheres o cálculo usa também o quadril")
        if cintura + quadril <= pescoco:
            raise ValueError("medidas inconsistentes")
        bf = 495 / (1.29579 - 0.35004 * math.log10(cintura + quadril - pescoco) + 0.22100 * math.log10(altura_cm)) - 450
    return round(max(2.0, min(bf, 60.0)), 1)


def categoria_bf(sexo: str, bf: float) -> str:
    faixas = [(6, "essencial"), (14, "atlético"), (18, "em forma"), (25, "médio"), (99, "acima do ideal")] if sexo == "m" else \
             [(14, "essencial"), (21, "atlético"), (25, "em forma"), (32, "médio"), (99, "acima do ideal")]
    return next(n for lim, n in faixas if bf < lim)


def gasto(sexo: str, peso: float, altura_cm: float, idade: int, atividade: str, objetivo: str) -> dict:
    tmb = 10 * peso + 6.25 * altura_cm - 5 * idade + (5 if sexo == "m" else -161)
    tdee = tmb * ATIVIDADE.get(atividade, 1.375)
    alvo = tdee * (1 + OBJETIVOS.get(objetivo, 0.0))
    alvo = max(alvo, 1500 if sexo == "m" else 1200)  # piso de segurança
    prot_kg = 2.2 if objetivo in ("emagrecer", "definir") else 1.8
    proteina = round(prot_kg * peso)
    gordura = round(0.8 * peso)
    carbo = max(0, round((alvo - proteina * 4 - gordura * 9) / 4))
    return {"tmb": round(tmb), "gasto_diario": round(tdee), "calorias_alvo": round(alvo), "proteina_g": proteina, "gordura_g": gordura,
            "carboidrato_g": carbo, "agua_ml": round(peso * 35)}


def progresso(inicio: float, atual: float, alvo: float) -> int:
    """0 a 100: quanto do caminho até a meta já foi feito."""
    total = alvo - inicio
    if abs(total) < 1e-6:
        return 100
    return int(max(0, min(100, round((atual - inicio) / total * 100))))


def nivel(pontos: int) -> dict:
    atual = [n for n in NIVEIS if pontos >= n[0]][-1]
    prox = next((n for n in NIVEIS if n[0] > pontos), None)
    return {"nivel": atual[1], "pontos": pontos, "proximo": prox[1] if prox else None, "faltam": (prox[0] - pontos) if prox else 0}


NOMES_RIVAIS = ["Rafael M.", "Bianca S.", "Guilherme A.", "Duda R.", "Leonardo P.", "Mariana C.", "Caio F.", "Larissa T.", "Thiago N.",
                "Nina V.", "Davi L.", "Malu O.", "Bruna K.", "Felipe G.", "Camila D.", "Pedro H."]


def rivais(usuario_id: int, pontos: int, semana: str, dia_semana: int = 0, n: int = 6) -> list[dict]:
    """Atletas de motivação (NPCs, como bots de jogo) que dão competição ao ranking. Aparecem como jogadores normais
    (decisão do Lucas, 16/11; os termos de uso avisam que o ranking inclui atletas virtuais). Eles também avançam
    com os dias da semana, então quem para de treinar é ultrapassado; um deles fica sempre logo atrás do usuário."""
    rnd = random.Random(f"{usuario_id}:{semana}")
    ritmo = 18 + 22 * dia_semana                 # quanto um atleta constante faria até hoje
    base = max(pontos, ritmo, 30)
    out = []
    for i, nome in enumerate(rnd.sample(NOMES_RIVAIS, n)):
        fator = [1.22, 1.1, 1.04, 0.0, 0.83, 0.7][i]
        pts = max(0, pontos - rnd.randint(4, 14)) if fator == 0 else int(base * fator + rnd.randint(-6, 6))
        out.append({"nome": nome, "pontos": max(pts, int(ritmo * 0.6) if fator else pts)})
    return out


def alerta(ranking: list[dict]) -> dict | None:
    """Quem está colado no usuário (atrás ou na frente): vira aviso no painel e provocação do coach."""
    i = next((k for k, x in enumerate(ranking) if x.get("voce")), None)
    if i is None:
        return None
    eu = ranking[i]
    atras = ranking[i + 1] if i + 1 < len(ranking) else None
    frente = ranking[i - 1] if i > 0 else None
    if atras and eu["pontos"] - atras["pontos"] <= 15:
        d = eu["pontos"] - atras["pontos"]
        return {"tipo": "ameaca", "nome": atras["nome"], "diferenca": d,
                "texto": f"{atras['nome']} está a {d} ponto{'s' if d != 1 else ''} de você. Não deixa passar: treina hoje!"}
    if frente:
        d = frente["pontos"] - eu["pontos"]
        return {"tipo": "alvo", "nome": frente["nome"], "diferenca": d,
                "texto": f"Faltam {d} ponto{'s' if d != 1 else ''} para passar {frente['nome']}. Um treino resolve."}
    return {"tipo": "lider", "nome": "", "diferenca": 0, "texto": "Você está em 1º lugar na semana. Segura a coroa!"}
