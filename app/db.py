"""Banco do Shape AI: SQLite num volume (/data). Hora em epoch (s)."""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, criado REAL NOT NULL,
  plano TEXT NOT NULL DEFAULT 'teste', ativo_ate REAL NOT NULL DEFAULT 0, pedido TEXT);
CREATE TABLE IF NOT EXISTS codigos (email TEXT PRIMARY KEY, hash TEXT NOT NULL, expira REAL NOT NULL, tentativas INTEGER NOT NULL DEFAULT 0, enviado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessoes (hash TEXT PRIMARY KEY, usuario INTEGER NOT NULL, expira REAL NOT NULL);
CREATE TABLE IF NOT EXISTS eventos_cakto (id TEXT PRIMARY KEY, recebido REAL NOT NULL, corpo TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assinaturas (usuario INTEGER PRIMARY KEY, plano TEXT NOT NULL, ativo_ate REAL NOT NULL, pedido TEXT);

-- quem a pessoa é e o que quer (a IA lê tudo isto antes de responder)
CREATE TABLE IF NOT EXISTS perfis (usuario INTEGER PRIMARY KEY, nome TEXT NOT NULL, sexo TEXT NOT NULL, nascimento TEXT NOT NULL,
  altura_cm REAL NOT NULL, atividade TEXT NOT NULL, objetivo TEXT NOT NULL, rotina TEXT NOT NULL DEFAULT '', restricoes TEXT NOT NULL DEFAULT '',
  dias_treino INTEGER NOT NULL DEFAULT 4, minutos_treino INTEGER NOT NULL DEFAULT 60, local_treino TEXT NOT NULL DEFAULT 'academia',
  meta_peso REAL, meta_bf REAL, atualizado REAL NOT NULL);
-- medidas com data (peso, pescoço, cintura, quadril...) e o BF calculado
CREATE TABLE IF NOT EXISTS medidas (id INTEGER PRIMARY KEY, usuario INTEGER NOT NULL, data TEXT NOT NULL, peso REAL, pescoco REAL, cintura REAL,
  quadril REAL, braco REAL, coxa REAL, bf REAL, criado REAL NOT NULL);
CREATE INDEX IF NOT EXISTS medidas_usuario ON medidas(usuario, data);
-- fotos: evolução do corpo, prato, prova de academia
CREATE TABLE IF NOT EXISTS fotos (nome TEXT PRIMARY KEY, usuario INTEGER NOT NULL, tipo TEXT NOT NULL, legenda TEXT NOT NULL DEFAULT '', criado REAL NOT NULL);
CREATE INDEX IF NOT EXISTS fotos_usuario ON fotos(usuario, tipo, criado);
-- planos gerados pela IA (treino e dieta da semana)
CREATE TABLE IF NOT EXISTS planos (id INTEGER PRIMARY KEY, usuario INTEGER NOT NULL, tipo TEXT NOT NULL, dados TEXT NOT NULL, criado REAL NOT NULL);
CREATE INDEX IF NOT EXISTS planos_usuario ON planos(usuario, tipo, criado);
-- gamificação: cada check-in vale pontos (treino feito, prato fotografado, medida, água...)
CREATE TABLE IF NOT EXISTS checkins (id INTEGER PRIMARY KEY, usuario INTEGER NOT NULL, tipo TEXT NOT NULL, dia TEXT NOT NULL, ref TEXT NOT NULL DEFAULT '',
  pontos INTEGER NOT NULL, kcal REAL NOT NULL DEFAULT 0, criado REAL NOT NULL, UNIQUE(usuario, tipo, dia, ref));
CREATE INDEX IF NOT EXISTS checkins_usuario ON checkins(usuario, dia);
-- ergogênicos: SÓ o registro do que o médico prescreveu (lembrete e calendário); o app não sugere substância nem dose
CREATE TABLE IF NOT EXISTS prescricoes (id INTEGER PRIMARY KEY, usuario INTEGER NOT NULL, nome TEXT NOT NULL, dose TEXT NOT NULL,
  dias TEXT NOT NULL, horario TEXT NOT NULL DEFAULT '', medico TEXT NOT NULL DEFAULT '', observacao TEXT NOT NULL DEFAULT '', criado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS aplicacoes (id INTEGER PRIMARY KEY, prescricao INTEGER NOT NULL, usuario INTEGER NOT NULL, dia TEXT NOT NULL, criado REAL NOT NULL,
  UNIQUE(prescricao, dia));
CREATE TABLE IF NOT EXISTS mensagens (id INTEGER PRIMARY KEY, usuario INTEGER NOT NULL, papel TEXT NOT NULL, texto TEXT NOT NULL, criado REAL NOT NULL);
CREATE INDEX IF NOT EXISTS mensagens_usuario ON mensagens(usuario, criado);
"""


class Banco:
    def __init__(self, caminho: str):
        self._trava = threading.Lock()
        self.con = sqlite3.connect(caminho, check_same_thread=False, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript(ESQUEMA)

    @contextmanager
    def tx(self):
        with self._trava:
            self.con.execute("BEGIN IMMEDIATE")
            try:
                yield self.con
                self.con.execute("COMMIT")
            except BaseException:
                self.con.execute("ROLLBACK")
                raise

    def exec(self, sql: str, args: tuple = ()):
        with self._trava:
            return self.con.execute(sql, args)

    def um(self, sql: str, args: tuple = ()) -> dict | None:
        with self._trava:
            r = self.con.execute(sql, args).fetchone()
        return dict(r) if r else None

    def todos(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._trava:
            return [dict(r) for r in self.con.execute(sql, args).fetchall()]


def agora() -> float:
    return time.time()
