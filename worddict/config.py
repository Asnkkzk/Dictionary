# -*- coding: utf-8 -*-
"""配置管理：读写 %APPDATA%/WordDict/config.json，带默认值合并。"""
import os
import json
import threading

APP_NAME = "随取词典"
APP_ID = "WordDict"

_lock = threading.Lock()

DEFAULTS = {
    "official": {
        # provider: none | youdao | baidu
        "provider": "none",
        "youdao_appkey": "",
        "youdao_secret": "",
        "baidu_appid": "",
        "baidu_secret": "",
    },
    "popup": {
        "enabled": True,
        "drag_min_distance": 15,  # 拖动多远算“选中”（过小会误判普通点击）
        "copy_delay_ms": 120,     # 松开鼠标后等待多久再 Ctrl+C
        "max_phrase_len": 60,     # 超过该长度视为非单词，不弹窗
    },
    "daily_word": {
        "enabled": True,
        "hour": 9,                # 每日推送小时（0-23）
    },
    "history_limit": 200,
    "autostart": False,
}


def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_ID)
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def config_path():
    return os.path.join(data_dir(), "config.json")


def db_path():
    return os.path.join(data_dir(), "dict.db")


def _deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            out[k] = _deep_merge(base[k], v)
        else:
            out[k] = v
    return out


def load():
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = _deep_merge(cfg, data)
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg):
    with _lock:
        try:
            with open(config_path(), "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except OSError:
            pass


_config = None


def get():
    global _config
    if _config is None:
        _config = load()
    return _config


def reload():
    global _config
    _config = load()
    return _config


def set_value(path, value):
    """path 形如 'official.provider' 或 'popup.enabled'。"""
    global _config
    cfg = get()
    keys = path.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value
    save(cfg)
    return cfg
