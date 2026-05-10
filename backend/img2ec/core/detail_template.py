"""默认详情页模板：5 个 module 垂直拼接。

V1 用一份模板适配 3 个平台。V1.1+ 可加平台差异化。
"""
from __future__ import annotations

DEFAULT_TEMPLATE: dict = {
    "canvas_width": 750,
    "modules": [
        {"type": "hero",           "config": {"height": 750, "scale": 0.78, "bg_color": [248, 244, 238]}},
        {"type": "title_banner",   "config": {"height": 280, "title_size": 40, "subtitle_size": 22}},
        {"type": "selling_points", "config": {"height": 360, "max_points": 3, "accent_color": [191, 130, 60]}},
        {"type": "full_image",     "config": {}},
        {"type": "cta",            "config": {"height": 200, "text": "立即购买", "btn_color": [191, 130, 60]}},
    ],
}
