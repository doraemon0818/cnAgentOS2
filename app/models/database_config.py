import json
import os

_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "database.json")

_defaults = {
    "type": "sqlite",
    "sqlite": {
        "path": os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "database", "app.db")
    },
    "mysql": {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "cnagentos",
        "charset": "utf8mb4"
    }
}


def _ensure_dir(path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def load():
    _ensure_dir(_config_path)
    if not os.path.exists(_config_path):
        save(_defaults)
        return dict(_defaults)
    with open(_config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    merged = dict(_defaults)
    merged.update(data)
    return merged


def save(cfg):
    _ensure_dir(_config_path)
    with open(_config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get():
    return load()
