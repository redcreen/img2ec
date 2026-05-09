from img2ec.core.bg_detect import is_white_background


def test_white_bg_detected(fixtures_dir):
    assert is_white_background(fixtures_dir / "white_bg.jpg") is True


def test_photo_bg_not_detected(fixtures_dir):
    assert is_white_background(fixtures_dir / "photo_bg.jpg") is False
