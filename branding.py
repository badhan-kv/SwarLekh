"""SwarLekh's logo/icon, generated programmatically (no external image
assets to manage) — a soundwave badge, since "Swar" (voice/tone) turning into
"Lekh" (written text) is exactly what this app does."""

from PIL import Image, ImageDraw

IDLE_COLOR = (43, 42, 110)  # deep indigo
RECORDING_COLOR = (196, 30, 30)  # red
BAR_COLOR = (255, 255, 255)  # white

_BAR_HEIGHT_RATIOS = [0.32, 0.55, 0.85, 0.55, 0.32]


def _soundwave_badge(size: int, background: tuple, bar_color: tuple = BAR_COLOR, ring: bool = False) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if ring:
        # Recording state: a visible white ring changes the icon's silhouette,
        # not just its color — stays distinguishable even without color vision.
        draw.ellipse((0, 0, size - 1, size - 1), fill=(255, 255, 255))
        inset = size * 0.12
        draw.ellipse((inset, inset, size - 1 - inset, size - 1 - inset), fill=background)
        content_size = size - 2 * inset
    else:
        draw.ellipse((0, 0, size - 1, size - 1), fill=background)
        content_size = size

    bar_count = len(_BAR_HEIGHT_RATIOS)
    bar_width = content_size * 0.09
    gap = content_size * 0.055
    total_width = bar_count * bar_width + (bar_count - 1) * gap
    start_x = (size - total_width) / 2
    center_y = size / 2

    for i, ratio in enumerate(_BAR_HEIGHT_RATIOS):
        half_height = content_size * ratio * 0.5
        x0 = start_x + i * (bar_width + gap)
        x1 = x0 + bar_width
        y0 = center_y - half_height
        y1 = center_y + half_height
        draw.rounded_rectangle((x0, y0, x1, y1), radius=bar_width / 2, fill=bar_color)

    return image


def logo(size: int = 256) -> Image.Image:
    """The full brand mark: white soundwave bars on an indigo circle."""
    return _soundwave_badge(size, IDLE_COLOR)


def tray_icon(recording: bool, size: int = 64) -> Image.Image:
    """Small tray-icon variant: solid indigo circle when idle; red circle
    with a white ring while recording — two independent signals (color AND
    shape) so the state is clear even at a glance or without color vision."""
    if recording:
        return _soundwave_badge(size, RECORDING_COLOR, ring=True)
    return _soundwave_badge(size, IDLE_COLOR)


def save_ico(path: str, sizes=(16, 32, 48, 256)) -> None:
    """Save a multi-resolution .ico of the idle logo, for shortcuts/taskbar."""
    base = logo(max(sizes))
    base.save(path, format="ICO", sizes=[(s, s) for s in sizes])
