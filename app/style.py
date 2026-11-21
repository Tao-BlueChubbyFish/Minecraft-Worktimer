"""对话框内原生控件的 QSS（用配色方案动态生成，保持 MC 观感）。"""
from __future__ import annotations


def _col(pal: dict, key: str) -> str:
    v = pal[key]
    return v[0] if isinstance(v, list) else v


def menu_qss(pal: dict, font_px: int, family: str) -> str:
    return f"""
QMenu {{
    background-color: #262626;
    border: 2px solid #101010;
    padding: 4px;
    font-family: "{family}";
    font-size: {font_px}px;
    color: #e9e9e9;
}}
QMenu::item {{
    padding: 7px 26px 7px 14px;
    border: 1px solid transparent;
}}
QMenu::item:selected {{
    background-color: {_col(pal, 'accent')};
    border: 1px solid #101010;
    color: #ffffff;
}}
QMenu::item:disabled {{
    color: #7c7c7c;
}}
QMenu::separator {{
    height: 2px;
    background: #101010;
    margin: 5px 8px;
}}
"""


def dialog_qss(pal: dict, font_px: int, family: str) -> str:
    bevel_light = _col(pal, "bevel_light")
    bevel_dark = _col(pal, "bevel_dark")
    text = _col(pal, "text")
    accent = _col(pal, "accent")
    return f"""
QTimeEdit {{
    background-color: #141414;
    color: #f0f0f0;
    border: 2px solid {bevel_dark};
    border-top-color: #000000;
    border-left-color: #000000;
    padding: 2px 6px;
    font-family: "{family}";
    font-size: {font_px}px;
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QPushButton {{
    background-color: {_col(pal, 'panel')};
    color: {text};
    border: 2px solid {bevel_light};
    border-right-color: {bevel_dark};
    border-bottom-color: {bevel_dark};
    padding: 3px 10px;
    font-family: "{family}";
    font-size: {font_px}px;
}}
QPushButton:hover {{
    background-color: {_col(pal, 'panel_shade')};
}}
QPushButton:pressed {{
    border: 2px solid {bevel_dark};
    border-right-color: {bevel_light};
    border-bottom-color: {bevel_light};
}}
QPushButton#primary {{
    background-color: {accent};
    color: #ffffff;
    border: 2px solid #8bbf62;
    border-right-color: #2f4a1c;
    border-bottom-color: #2f4a1c;
}}
QPushButton#primary:hover {{
    background-color: #5c8f38;
}}
QPushButton#primary:pressed {{
    border: 2px solid #2f4a1c;
    border-right-color: #8bbf62;
    border-bottom-color: #8bbf62;
}}
QToolTip {{
    background-color: #262626;
    color: #e9e9e9;
    border: 2px solid #101010;
    font-family: "{family}";
}}
"""
