from PIL import Image

from img2ec.core.cutout import cutout_with_rembg


def test_cutout_returns_rgba_with_alpha(fixtures_dir, tmp_path):
    out_path = tmp_path / "front.png"
    cutout_with_rembg(fixtures_dir / "photo_bg.jpg", out_path)
    img = Image.open(out_path)
    assert img.mode == "RGBA"
    # 应该有透明像素（边缘被抠掉）
    alphas = {a for _, _, _, a in img.getdata() if hasattr(img, "mode")}
    # 简化：直接看角落像素是否透明
    corner_alpha = img.getpixel((0, 0))[3]
    assert corner_alpha == 0, f"expected transparent corner, got alpha={corner_alpha}"
