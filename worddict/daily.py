# -*- coding: utf-8 -*-
"""每日一词：从内置词库中选择尚未收藏的词。"""
import random
import datetime

from . import database
from . import config as cfg

BUILTIN = [
    ("abandon", "放弃；抛弃"),
    ("brilliant", "杰出的；明亮的"),
    ("curious", "好奇的；求知欲强的"),
    ("diligent", "勤奋的，用功的"),
    ("elegant", "优雅的，雅致的"),
    ("fascinate", "使着迷，强烈吸引"),
    ("generous", "慷慨的，大方的"),
    ("harmony", "和谐，融洽"),
    ("inspire", "鼓舞，激励；启发"),
    ("journey", "旅行，旅程"),
    ("knowledge", "知识，学问"),
    ("magnificent", "壮丽的，宏伟的"),
    ("persistent", "坚持不懈的；持续的"),
    ("resilient", "有韧性的，能复原的"),
    ("serendipity", "意外发现珍奇事物的运气"),
    ("tranquil", "宁静的，平静的"),
    ("versatile", "多才多艺的；用途广泛的"),
    ("wisdom", "智慧，才智"),
]


def _today():
    return datetime.date.today().isoformat()


def shown_today():
    return cfg.get()["daily_word"].get("last_shown") == _today()


def mark_shown():
    cfg.set_value("daily_word.last_shown", _today())


def pick():
    settings = cfg.get()["daily_word"]
    cached = settings.get("selection", {})
    owned = database.all_word_keys()
    if (cached.get("date") == _today() and cached.get("word")
            and cached["word"].strip().lower() not in owned):
        return cached["word"], cached.get("translation", "")
    candidates = [item for item in BUILTIN if item[0].lower() not in owned]
    if not candidates:
        return None
    previous = cached.get("word")
    choices = [item for item in candidates if item[0] != previous] or candidates
    word, translation = random.choice(choices)
    cfg.set_value("daily_word.selection", {"date": _today(), "word": word,
                                           "translation": translation})
    return word, translation


def summary():
    result = pick()
    if result is None:
        return "每日词库中的单词已全部收藏"
    w, t = result
    return "%s  %s" % (w, t) if t else w
