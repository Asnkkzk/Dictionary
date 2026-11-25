# -*- coding: utf-8 -*-
"""SQLite 本地词典存储：words（词条）+ history（历史）。"""
import os
import json
import sqlite3
import threading
import datetime

from . import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word        TEXT NOT NULL UNIQUE,   -- 小写索引键
    display     TEXT NOT NULL,          -- 原始展示形式
    phonetic    TEXT DEFAULT '',
    translation TEXT DEFAULT '',        -- 中文/英文翻译
    definition  TEXT DEFAULT '',        -- JSON: [{pos, def, example}]
    source      TEXT DEFAULT 'user',    -- local/free/official/user
    created_at  TEXT,
    updated_at  TEXT
);
CREATE TABLE IF NOT EXISTS history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word        TEXT NOT NULL,
    display     TEXT DEFAULT '',
    translation TEXT DEFAULT '',
    looked_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_words_word ON words(word);
CREATE INDEX IF NOT EXISTS idx_history_looked ON history(looked_at);
"""


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _conn():
    c = sqlite3.connect(config.db_path(), timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock:
        c = _conn()
        try:
            c.executescript(SCHEMA)
            c.commit()
        finally:
            c.close()


def _row_to_word(row):
    return {
        "word": row["word"],
        "display": row["display"],
        "phonetic": row["phonetic"] or "",
        "translation": row["translation"] or "",
        "definition": row["definition"] or "",
        "source": row["source"] or "",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


# ---------------- 词条 ----------------

def get_word(word):
    with _lock:
        c = _conn()
        try:
            row = c.execute(
                "SELECT * FROM words WHERE word=?", (word.lower().strip(),)
            ).fetchone()
            return _row_to_word(row) if row else None
        finally:
            c.close()


def upsert_word(word, display=None, phonetic="", translation="",
                definition="", source="user"):
    word = word.strip()
    key = word.lower()
    display = display or word
    now = _now()
    if isinstance(definition, (list, dict)):
        definition = json.dumps(definition, ensure_ascii=False)
    with _lock:
        c = _conn()
        try:
            row = c.execute("SELECT id FROM words WHERE word=?", (key,)).fetchone()
            if row:
                c.execute(
                    "UPDATE words SET display=?, phonetic=?, translation=?, "
                    "definition=?, source=?, updated_at=? WHERE word=?",
                    (display, phonetic, translation, definition, source, now, key),
                )
            else:
                c.execute(
                    "INSERT INTO words (word, display, phonetic, translation, "
                    "definition, source, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (key, display, phonetic, translation, definition, source, now, now),
                )
            c.commit()
        finally:
            c.close()
    return key


def delete_word(word):
    with _lock:
        c = _conn()
        try:
            c.execute("DELETE FROM words WHERE word=?", (word.lower().strip(),))
            c.commit()
        finally:
            c.close()


def list_words(letter=None):
    """按字母序返回全部词条；letter 为单个字母时仅返回该字母开头。"""
    with _lock:
        c = _conn()
        try:
            if letter and letter != "全部":
                rows = c.execute(
                    "SELECT * FROM words WHERE word LIKE ? ORDER BY word COLLATE NOCASE",
                    (letter.lower() + "%",),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM words ORDER BY word COLLATE NOCASE"
                ).fetchall()
            return [_row_to_word(r) for r in rows]
        finally:
            c.close()


def search_words(q):
    q = q.strip()
    if not q:
        return list_words()
    like = "%" + q.lower() + "%"
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT * FROM words WHERE word LIKE ? OR translation LIKE ? "
                "ORDER BY word COLLATE NOCASE",
                (like, like),
            ).fetchall()
            return [_row_to_word(r) for r in rows]
        finally:
            c.close()


def count_words():
    with _lock:
        c = _conn()
        try:
            return c.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        finally:
            c.close()


def all_word_keys():
    with _lock:
        c = _conn()
        try:
            rows = c.execute("SELECT word FROM words").fetchall()
            return {r["word"] for r in rows}
        finally:
            c.close()


def random_word():
    with _lock:
        c = _conn()
        try:
            row = c.execute(
                "SELECT * FROM words ORDER BY RANDOM() LIMIT 1"
            ).fetchone()
            return _row_to_word(row) if row else None
        finally:
            c.close()


# ---------------- 历史 ----------------

def add_history(word, display=None, translation=""):
    limit = config.get().get("history_limit", 200)
    word = word.strip()
    now = _now()
    with _lock:
        c = _conn()
        try:
            c.execute(
                "INSERT INTO history (word, display, translation, looked_at) "
                "VALUES (?,?,?,?)",
                (word.lower(), display or word, translation, now),
            )
            # 只保留最近 N 条
            c.execute(
                "DELETE FROM history WHERE id NOT IN "
                "(SELECT id FROM history ORDER BY id DESC LIMIT ?)",
                (limit,),
            )
            c.commit()
        finally:
            c.close()


def list_history(limit=None):
    limit = limit or config.get().get("history_limit", 200)
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [
                {
                    "word": r["word"],
                    "display": r["display"],
                    "translation": r["translation"],
                    "looked_at": r["looked_at"],
                }
                for r in rows
            ]
        finally:
            c.close()


def clear_history():
    with _lock:
        c = _conn()
        try:
            c.execute("DELETE FROM history")
            c.commit()
        finally:
            c.close()
