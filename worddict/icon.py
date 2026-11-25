# -*- coding: utf-8 -*-
"""生成应用托盘图标 icon.ico（蓝色词典 + 放大镜）。"""
import os

from PIL import Image, ImageDraw


def build_icon(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 64.0

    # 圆角书本
    def box(x0, y0, x1, y1, r, fill):
        d.rounded_rectangle(
            [x0 * s, y0 * s, x1 * s, y1 * s], radius=r * s, fill=fill
        )

    # 书体
    box(10, 14, 54, 50, 7, (66, 133, 244, 255))
    # 书脊高光
    box(10, 14, 54, 24, 7, (53, 105, 200, 255))
    d.rectangle([10 * s, 22 * s, 54 * s, 24 * s], fill=(53, 105, 200, 255))
    # 中线
    d.line([32 * s, 14 * s, 32 * s, 50 * s], fill=(255, 255, 255, 255), width=int(2 * s))
    # 左侧文字行
    d.rectangle([16 * s, 30 * s, 28 * s, 32 * s], fill=(255, 255, 255, 230))
    d.rectangle([16 * s, 36 * s, 28 * s, 38 * s], fill=(255, 255, 255, 230))
    d.rectangle([16 * s, 42 * s, 24 * s, 44 * s], fill=(255, 255, 255, 200))
    # 右侧文字行
    d.rectangle([36 * s, 30 * s, 48 * s, 32 * s], fill=(255, 255, 255, 230))
    d.rectangle([36 * s, 36 * s, 48 * s, 38 * s], fill=(255, 255, 255, 230))
    d.rectangle([36 * s, 42 * s, 44 * s, 44 * s], fill=(255, 255, 255, 200))

    # 放大镜
    cx, cy, r = 40, 40, 13
    d.ellipse(
        [(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s],
        outline=(255, 255, 255, 255), width=int(4 * s),
    )
    d.line(
        [(cx + 9) * s, (cy + 9) * s, (cx + 19) * s, (cy + 19) * s],
        fill=(255, 255, 255, 255), width=int(4 * s),
    )

    return img


def ensure_icon(path):
    if os.path.exists(path):
        return path
    img = build_icon()
    img.save(path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    return path


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "assets", "icon.ico")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ensure_icon(out)
    print("icon written:", out)
