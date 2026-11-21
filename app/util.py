"""路径 / 文件读写工具。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """配置文件所在目录：打包后是 exe 所在目录，开发时是项目根目录。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """只读资源目录（字体等）。onefile 模式下位于临时解包目录。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return app_dir() / "config.json"


def data_path() -> Path:
    return app_dir() / "data.json"


def fonts_dir() -> Path:
    return resource_dir() / "assets" / "fonts"


def read_json(path: Path) -> dict:
    """读取 json；文件损坏时备份并返回空 dict。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        try:
            bad = path.with_suffix(path.suffix + ".broken")
            path.replace(bad)
        except Exception:
            pass
        return {}


def write_json(path: Path, data: dict) -> None:
    """原子写入，避免半截文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.stem, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def deep_merge(base: dict, override: dict) -> dict:
    """把 override 合并进 base 的副本（递归字典合并）。"""
    out: dict[str, Any] = {}
    for k, v in base.items():
        if isinstance(v, dict):
            out[k] = deep_merge(v, override.get(k, {}) if isinstance(override.get(k), dict) else {})
        else:
            out[k] = v
    for k, v in override.items():
        if k not in out:
            out[k] = v
        elif isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def clamp(value, low, high):
    return low if value < low else high if value > high else value
