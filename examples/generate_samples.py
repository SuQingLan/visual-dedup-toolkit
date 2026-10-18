"""Generate synthetic test images for visual-dedup-toolkit."""

from pathlib import Path

from PIL import Image, ImageDraw


def generate_test_images(output_dir: str) -> Path:
    """Generate a set of synthetic images with known duplication/similarity relationships.

    Creates:
    - original.png (96x96, navy rectangle) + duplicate.png (byte-identical copy)
    - resized_64.png (64x64, same visual content, smaller)
    - resized_128.png (128x128, same visual content, larger)
    - different.png (96x96, completely different content)
    - corrupt.jpg (invalid image data)
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    # Original image
    img = Image.new('RGB', (96, 96), 'white')
    draw = ImageDraw.Draw(img)
    draw.rectangle((8, 12, 53, 69), fill='navy')
    img.save(root / 'original.png')

    # Byte-identical duplicate
    img.save(root / 'duplicate.png')

    # Different resolutions, same visual content
    img_small = img.resize((64, 64))
    img_small.save(root / 'resized_64.png')

    img_large = img.resize((128, 128))
    img_large.save(root / 'resized_128.png')

    # Completely different image
    diff = Image.new('RGB', (96, 96), 'black')
    diff_draw = ImageDraw.Draw(diff)
    diff_draw.ellipse((10, 10, 86, 86), fill='red')
    diff.save(root / 'different.png')

    # Corrupt image
    (root / 'corrupt.jpg').write_bytes(b'this is not a valid image')

    # Non-image file (should be ignored)
    (root / 'notes.txt').write_text('not an image')

    print(f"Generated 7 files in: {root}")
    print("  original.png    - 96x96, navy rectangle")
    print("  duplicate.png   - byte-identical copy")
    print("  resized_64.png  - 64x64, same content (smaller)")
    print("  resized_128.png - 128x128, same content (larger)")
    print("  different.png   - 96x96, different content")
    print("  corrupt.jpg     - invalid image data")
    print("  notes.txt       - non-image (ignored)")
    return root


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "test_images"
    generate_test_images(out)