"""应用图标生成器:assets/icon.png(1024 master)+ assets/icon.ico(16-256 多尺寸)。

设计:圆角方(半径 22%)垂直渐变 hsl(195 100% 55%) → hsl(210 90% 45%),
居中白色铃铛(顶钮/半球罩/梯形裙/圆角沿/钟舌),两侧各两道 70% 白声波弧,
左上 12% 白色内高光。与 frontend/public/favicon.svg、TitleBar 内联 SVG 同源。

依赖:pillow(仅生成时需要,不入 requirements.txt):.venv/bin/pip install pillow
用法:.venv/bin/python scripts/make_icon.py   (幂等,确定性输出,无随机因素)
"""
import colorsys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

S = 1024          # master 边长
K = 4             # 超采样倍数(4x 绘制后 LANCZOS 缩回,抗锯齿)
CORNER = 0.22     # 圆角比例
ARC_ALPHA = round(255 * 0.70)   # 声波弧 70% 白
HILITE_ALPHA = 0.12            # 左上内高光峰值 12%


def hsl(h: float, s: float, l: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hls_to_rgb(h / 360, l, s)
    return round(r * 255), round(g * 255), round(b * 255)


def vertical_gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    """1 像素宽的竖向渐变拉满画布(逐行插值,deterministic)。"""
    col = Image.new("RGB", (1, size))
    px = col.load()
    for y in range(size):
        t = y / (size - 1)
        px[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
    return col.resize((size, size))


def build_master() -> Image.Image:
    big = S * K
    # 1) 渐变底 + 圆角遮罩
    img = vertical_gradient(big, hsl(195, 1.0, 0.55), hsl(210, 0.9, 0.45)).convert("RGBA")
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, big - 1, big - 1], radius=round(big * CORNER), fill=255)
    img.putalpha(mask)

    ov = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # 2) 左上内高光(白 12%,径向渐弱)
    rad = ImageOps.invert(Image.radial_gradient("L")).resize((round(big * 1.5), round(big * 1.5)))
    hilite = Image.new("L", (big, big), 0)
    cx, cy = round(big * 0.30), round(big * 0.24)
    hilite.paste(rad, (cx - rad.width // 2, cy - rad.height // 2))
    glow = Image.new("RGBA", (big, big), (255, 255, 255, 255))
    glow.putalpha(hilite.point(lambda v: round(v * HILITE_ALPHA)))
    ov.alpha_composite(glow)
    d = ImageDraw.Draw(ov)

    def k(*vals: float) -> list[int]:
        return [round(v * K) for v in vals]

    # 3) 声波弧(两侧各两道,白 70%)
    acx, acy = 512 * K, 530 * K
    for r in (320, 400):
        bb = [acx - r * K, acy - r * K, acx + r * K, acy + r * K]
        d.arc(bb, start=-42, end=42, fill=(255, 255, 255, ARC_ALPHA), width=round(38 * K))
        d.arc(bb, start=138, end=222, fill=(255, 255, 255, ARC_ALPHA), width=round(38 * K))

    # 4) 铃铛本体(纯白,粗几何保证 16px 可辨)
    bell = (255, 255, 255, 255)
    d.ellipse(k(512 - 38, 240 - 38, 512 + 38, 240 + 38), fill=bell)            # 顶钮
    d.pieslice(k(344, 288, 680, 624), start=180, end=360, fill=bell)           # 半球罩
    d.polygon([tuple(k(x, y)) for x, y in [(344, 456), (680, 456), (722, 648), (302, 648)]], fill=bell)  # 外扩裙
    d.ellipse(k(512 - 58, 757 - 58, 512 + 58, 757 + 58), fill=bell)            # 钟舌(先画,被沿遮上缘)
    d.rounded_rectangle(k(272, 632, 752, 706), radius=round(37 * K), fill=bell)  # 圆角沿

    out = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    out.alpha_composite(img)
    out.alpha_composite(ov)
    return out.resize((S, S), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    master = build_master()
    master.save(OUT / "icon.png", optimize=True)
    master.save(OUT / "icon.ico",
                sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    for f in ("icon.png", "icon.ico"):
        p = OUT / f
        print(f"{p}  {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()
