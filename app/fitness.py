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


NOMES_RIVAIS = ["Rafa", "Bia", "Gui", "Duda", "Léo", "Mari", "Caio", "Lari", "Teo", "Nina", "Davi", "Malu"]


def rivais(usuario_id: int, pontos: int, semana: str, n: int = 6) -> list[dict]:
    """Rivais simulados para dar movimento ao ranking. São SEMPRE marcados como 'rival da IA' na tela (decisão de produto:
    nada de fingir que são pessoas reais). A pontuação acompanha a do usuário, uns um pouco acima, outros abaixo."""
    rnd = random.Random(f"{usuario_id}:{semana}")
    base = max(pontos, 40)
    out = []
    for i, nome in enumerate(rnd.sample(NOMES_RIVAIS, n)):
        fator = [1.18, 1.09, 1.03, 0.94, 0.85, 0.72][i]
        out.append({"nome": f"{nome} (rival da IA)", "pontos": int(base * fator + rnd.randint(-8, 8)), "simulado": True})
    return out
