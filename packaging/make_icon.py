"""Draws the Dune Market icon (packaging/dune-market.ico): a gold Solari coin on dunes, on a dark tile."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 512
GOLD, DEEP_GOLD, DARK, DARKER = (230, 201, 132), (150, 124, 70), (38, 31, 22), (21, 17, 12)


def draw() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    tile = Image.new("RGBA", (SIZE, SIZE), DARKER)
    gradient = ImageDraw.Draw(tile)
    for y in range(SIZE):  # vertical gradient, dark brown to near black
        t = y / SIZE
        gradient.line([(0, y), (SIZE, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(DARK, DARKER)) + (255,))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([8, 8, SIZE - 9, SIZE - 9], radius=92, fill=255)
    image.paste(tile, (0, 0), mask)

    draw.rounded_rectangle([8, 8, SIZE - 9, SIZE - 9], radius=92, outline=DEEP_GOLD, width=10)

    # dunes along the bottom
    draw.polygon([(24, 420), (140, 350), (260, 400), (380, 340), (488, 410), (488, 488), (24, 488)], fill=(110, 88, 48))
    draw.polygon([(24, 450), (120, 400), (250, 440), (370, 395), (488, 450), (488, 488), (24, 488)], fill=(78, 62, 34))

    # a big gold coin with the Solari "S" (the in-game currency)
    cx, cy, r = 256, 232, 168
    draw.ellipse([cx - r - 6, cy - r + 8, cx + r + 6, cy + r + 20], fill=(20, 16, 10, 200))  # soft shadow
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DEEP_GOLD)
    draw.ellipse([cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10], fill=GOLD)
    draw.ellipse([cx - r + 34, cy - r + 34, cx + r - 34, cy + r - 34], outline=DEEP_GOLD, width=9)
    draw.arc([cx - r + 18, cy - r + 18, cx + r - 18, cy + r - 18], start=200, end=290, fill=(255, 240, 200), width=8)  # shine
    font = None
    for name in ("segoeuib.ttf", "arialbd.ttf", "seguibl.ttf"):
        try:
            font = ImageFont.truetype(name, 190)
            break
        except OSError:
            continue
    letter = "S"
    if font:
        left, top, right, bottom = draw.textbbox((0, 0), letter, font=font)
        draw.text((cx - (right - left) / 2 - left, cy - (bottom - top) / 2 - top - 4), letter, font=font, fill=DARKER)
    # the vertical bar through the S, as on the Solari symbol
    draw.rounded_rectangle([cx - 7, cy - 118, cx + 7, cy + 118], radius=5, fill=DARKER)
    return image


if __name__ == "__main__":
    out = Path(__file__).with_name("dune-market.ico")
    draw().save(out, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    draw().resize((256, 256), Image.LANCZOS).save(out.with_suffix(".png"))
    print(f"wrote {out}")
