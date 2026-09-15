from pathlib import Path

from PIL import Image

import branding


def test_logo_returns_requested_size():
    image = branding.logo(128)
    assert image.size == (128, 128)


def test_tray_icon_idle_and_recording_differ():
    idle = branding.tray_icon(False, 64)
    recording = branding.tray_icon(True, 64)
    assert idle.size == recording.size == (64, 64)
    assert list(idle.getdata()) != list(recording.getdata())


def test_tray_icon_recording_has_a_visible_white_ring():
    # The recording state must differ by shape, not just color, so it reads
    # even without color vision — check the very edge pixel is white, which
    # only happens when the ring is drawn (idle has background color there).
    recording = branding.tray_icon(True, 64)
    edge_pixel = recording.getpixel((32, 1))
    assert edge_pixel[:3] == (255, 255, 255)


def test_save_ico_creates_multi_resolution_file(tmp_path):
    ico_path = tmp_path / "icon.ico"
    branding.save_ico(str(ico_path), sizes=(16, 32))
    assert ico_path.exists()
    with Image.open(ico_path) as img:
        assert img.format == "ICO"
