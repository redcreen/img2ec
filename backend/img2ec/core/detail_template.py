"""默认详情页模板：5 个 module 垂直拼接。

V1 用一份模板适配 3 个平台。V1.1+ 可加平台差异化。
"""
from __future__ import annotations

DEFAULT_TEMPLATE: dict = {
    "canvas_width": 750,
    # CTA 按钮已移除（用户反馈：电商详情页平台已有自带购买按钮，多余）
    # 顺序：商品 hero → 标题 banner → 3 卖点 → 全幅长图
    "modules": [
        {"type": "hero",           "config": {"height": 750, "scale": 0.78, "bg_color": [248, 244, 238]}},
        {"type": "title_banner",   "config": {"height": 280, "title_size": 40, "subtitle_size": 22}},
        {"type": "selling_points", "config": {"height": 360, "max_points": 3, "accent_color": [191, 130, 60]}},
        {"type": "full_image",     "config": {}},
    ],
}
