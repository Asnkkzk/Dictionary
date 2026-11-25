# -*- coding: utf-8 -*-
"""三级翻译链路：本地词典 -> 免费在线 -> 官方 API。

结果统一为 dict：
{
  "word": str,           # 展示形式
  "phonetic": str,       # 音标
  "translation": str,    # 译文
  "definitions": [ {pos, def, example}, ... ],
  "source": "local"|"free"|"official"|"none",
  "from_lang": "en"|"zh",
}
"""
import re
import hashlib
import random
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests

from . import database
from . import config as cfg

TIMEOUT = 5.0
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WordDict/1.0"

_CJK = re.compile(r"[\u4e00-\u9fff]")


def is_cjk(s):
    return bool(_CJK.search(s))


def _clean_word(text):
    """清洗选中的文本，判断是否为合法“单词/短语”。"""
    s = text.strip()
    s = s.strip(",.!?;:()[]{}<>\"'“”‘’《》")
    if not s:
        return None
    if "\n" in s or "\r" in s or "\t" in s:
        return None
    max_len = cfg.get()["popup"].get("max_phrase_len", 60)
    if len(s) > max_len:
        return None
    # 含 CJK 视为中文词；否则必须是字母/数字/连字符/撇号/空格组成
    if is_cjk(s):
        if len(s) > 20:
            return None
        return s
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9'’\-\. ]*", s):
        return None
    return s


# ---------------- 本地 ----------------

def _lookup_local(word):
    rec = database.get_word(word)
    if not rec:
        return None
    defs = []
    try:
        defs = _parse_definitions(rec.get("definition"))
    except Exception:
        defs = []
    return {
        "word": rec["display"],
        "phonetic": rec.get("phonetic", ""),
        "translation": rec.get("translation", ""),
        "definitions": defs,
        "source": "local",
        "from_lang": "zh" if is_cjk(rec["display"]) else "en",
    }


def _parse_definitions(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        data = raw
    else:
        data = json_loads(raw)
    out = []
    for d in data:
        if isinstance(d, dict):
            out.append({
                "pos": d.get("pos", ""),
                "def": d.get("def", ""),
                "example": d.get("example", ""),
            })
    return out


def json_loads(s):
    import json
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return []


# ---------------- 免费在线 ----------------

def _google_translate(word, sl, tl):
    url = (
        "https://translate.googleapis.com/translate_a/single"
        "?client=gtx&sl=%s&tl=%s&dt=t&q=%s"
        % (sl, tl, urllib.parse.quote(word))
    )
    r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
    r.raise_for_status()
    data = r.json()
    segs = data[0] if data and isinstance(data[0], list) else []
    text = "".join(seg[0] for seg in segs if seg and seg[0])
    return text.strip()


def _dictapi(word):
    url = "https://api.dictionaryapi.dev/api/v2/entries/en/" + urllib.parse.quote(word)
    r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    entry = data[0]
    phonetic = entry.get("phonetic") or ""
    if not phonetic:
        for ph in entry.get("phonetics", []):
            if ph.get("text"):
                phonetic = ph["text"]
                break
    defs = []
    for m in entry.get("meanings", []):
        pos = m.get("partOfSpeech", "")
        for d in m.get("definitions", [])[:3]:
            ex = (d.get("example") or "").strip()
            defs.append({
                "pos": pos,
                "def": (d.get("definition") or "").strip(),
                "example": ex,
            })
    return {"phonetic": phonetic, "definitions": defs}


def _lookup_free(word, from_lang):
    if from_lang == "zh":
        # 中 -> 英
        translation = _google_translate(word, "zh-CN", "en")
        return {
            "word": word, "phonetic": "", "translation": translation,
            "definitions": [], "source": "free", "from_lang": "zh",
        }

    # 英 -> 中：并发获取译文与词典释义
    translation = ""
    dict_info = {"phonetic": "", "definitions": []}
    errors = []

    def do_gtx():
        nonlocal translation
        translation = _google_translate(word, "en", "zh-CN")

    def do_dict():
        nonlocal dict_info
        info = _dictapi(word)
        if info:
            dict_info = info

    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(do_gtx), ex.submit(do_dict)]
        for f in futs:
            try:
                f.result(timeout=TIMEOUT + 1)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

    # 若译文缺失但词典有定义，退而求其次取第一条定义作说明
    if not translation and dict_info["definitions"]:
        translation = dict_info["definitions"][0]["def"]

    if not translation and not dict_info["definitions"]:
        return None

    return {
        "word": word,
        "phonetic": dict_info["phonetic"],
        "translation": translation,
        "definitions": dict_info["definitions"],
        "source": "free",
        "from_lang": "en",
    }


# ---------------- 官方 API ----------------

def _lookup_official(word, from_lang):
    oc = cfg.get()["official"]
    provider = oc.get("provider", "none")
    sl = "zh-CHS" if from_lang == "zh" else "EN"
    tl = "EN" if from_lang == "zh" else "zh-CHS"
    try:
        if provider == "youdao":
            return _youdao(word, sl, tl, oc)
        if provider == "baidu":
            return _baidu(word, from_lang, oc)
    except Exception:
        return None
    return None


def _youdao(word, sl, tl, oc):
    appkey = oc.get("youdao_appkey", "")
    secret = oc.get("youdao_secret", "")
    if not appkey or not secret:
        return None
    salt = str(random.randint(1, 65536))
    sign_src = appkey + word + salt + secret
    sign = hashlib.md5(sign_src.encode("utf-8")).hexdigest()
    r = requests.post(
        "https://openapi.youdao.com/api",
        data={
            "q": word, "from": sl, "to": tl,
            "appKey": appkey, "salt": salt, "sign": sign,
        },
        timeout=TIMEOUT,
    )
    data = r.json()
    if data.get("errorCode") != "0":
        return None
    translation = "；".join(data.get("translation", []))
    return {
        "word": word, "phonetic": "", "translation": translation,
        "definitions": [], "source": "official",
        "from_lang": "zh" if sl.startswith("zh") else "en",
    }


def _baidu(word, from_lang, oc):
    appid = oc.get("baidu_appid", "")
    secret = oc.get("baidu_secret", "")
    if not appid or not secret:
        return None
    salt = str(random.randint(32768, 65536))
    sl = "zh" if from_lang == "zh" else "en"
    tl = "en" if from_lang == "zh" else "zh"
    sign = hashlib.md5((appid + word + salt + secret).encode("utf-8")).hexdigest()
    r = requests.get(
        "https://api.fanyi.baidu.com/trans/vip/translate",
        params={"q": word, "from": sl, "to": tl,
                "appid": appid, "salt": salt, "sign": sign},
        timeout=TIMEOUT,
    )
    data = r.json()
    results = data.get("trans_result", [])
    translation = "；".join(x.get("dst", "") for x in results)
    return {
        "word": word, "phonetic": "", "translation": translation,
        "definitions": [], "source": "official",
        "from_lang": from_lang,
    }


# ---------------- 入口 ----------------

def lookup(word):
    """三级查找。返回结果 dict，失败时返回 None。"""
    word = _clean_word(word) if word else None
    if not word:
        return None

    from_lang = "zh" if is_cjk(word) else "en"

    # 1. 本地
    local = _lookup_local(word)
    if local:
        return local

    # 2. 免费在线
    try:
        free = _lookup_free(word, from_lang)
    except Exception:
        free = None
    if free:
        return free

    # 3. 官方 API
    official = _lookup_official(word, from_lang)
    if official:
        return official

    return None
