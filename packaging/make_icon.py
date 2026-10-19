"""Draws the Dune Market icon (packaging/dune-market.ico): a dark tile with a gold border, a sun and dunes."""

from pathlib import Path

from PIL import Image, ImageDraw

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

    draw.ellipse([300, 92, 420, 212], fill=GOLD)  # the sun
    draw.polygon([(24, 400), (150, 270), (260, 340), (380, 250), (488, 400), (488, 440), (24, 440)], fill=(188, 150, 80))  # far dune
    draw.polygon([(24, 440), (110, 340), (240, 410), (360, 330), (488, 430), (488, 488), (24, 488)], fill=DEEP_GOLD)  # near dune
    draw.line([(40, 392), (150, 292), (258, 362), (380, 272), (470, 380)], fill=GOLD, width=6)  # ridge light

    # a small bar chart on the near dune: it is a price tool
    for i, height in enumerate((46, 78, 62, 104)):
        x = 150 + i * 56
        draw.rounded_rectangle([x, 470 - height, x + 34, 470], radius=6, fill=DARKER)
    return image


if __name__ == "__main__":
    out = Path(__file__).with_name("dune-market.ico")
    draw().save(out, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    draw().resize((256, 256), Image.LANCZOS).save(out.with_suffix(".png"))
    print(f"wrote {out}")
