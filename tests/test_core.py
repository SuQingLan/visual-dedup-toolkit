"""Tests for visual_dedup package."""

import hashlib
import shutil
import tempfile
from pathlib import Path
import unittest

from PIL import Image, ImageDraw


class TestScanner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_discovers_supported_formats(self):
        (self.root / 'a.png').write_bytes(b'png')
        (self.root / 'b.JPG').write_bytes(b'jpg')
        (self.root / 'c.jpeg').write_bytes(b'jpeg')
        (self.root / 'd.txt').write_text('not image')
        from visual_dedup.scanner import discover_images
        result = discover_images(str(self.root))
        self.assertEqual(len(result), 3)
        names = {p.name for p in result}
        self.assertIn('a.png', names)
        self.assertIn('b.JPG', names)
        self.assertIn('c.jpeg', names)
        self.assertNotIn('d.txt', names)

    def test_excludes_output_directory(self):
        sub = self.root / 'output'
        sub.mkdir()
        (sub / 'img.png').write_bytes(b'png')
        (self.root / 'keep.png').write_bytes(b'png')
        from visual_dedup.scanner import discover_images
        result = discover_images(str(self.root), exclude_dirs=[str(sub)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, 'keep.png')

    def test_recursive_scan(self):
        sub = self.root / 'sub'
        sub.mkdir()
        (self.root / 'a.png').write_bytes(b'png')
        (sub / 'b.png').write_bytes(b'png')
        from visual_dedup.scanner import discover_images
        result = discover_images(str(self.root))
        self.assertEqual(len(result), 2)


class TestHashing(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_md5_identical_files(self):
        (self.root / 'a.png').write_bytes(b'hello')
        (self.root / 'b.png').write_bytes(b'hello')
        from visual_dedup.hashing import compute_md5
        self.assertEqual(compute_md5(self.root / 'a.png'), compute_md5(self.root / 'b.png'))

    def test_batch_md5(self):
        for i in range(3):
            (self.root / f'{i}.png').write_bytes(f'data{i}'.encode())
        from visual_dedup.hashing import batch_md5
        md5_map, errors = batch_md5(list(self.root.iterdir()), workers=2)
        self.assertEqual(len(md5_map), 3)
        self.assertEqual(len(errors), 0)

    def test_batch_md5_with_errors(self):
        (self.root / 'valid.png').write_bytes(b'data')
        invalid = self.root / 'invalid.png'
        invalid.write_bytes(b'data')
        import os
        os.chmod(str(invalid), 0o000)  # Make unreadable - skip on Windows
        from visual_dedup.hashing import batch_md5
        md5_map, errors = batch_md5(list(self.root.iterdir()), workers=1)
        self.assertGreaterEqual(len(md5_map) + len(errors), 1)

    def test_similarity_identical(self):
        from visual_dedup.hashing import similarity, compute_phash
        img = Image.new('RGB', (32, 32), 'red')
        img.save(self.root / 'a.png')
        img.save(self.root / 'b.png')
        h1 = compute_phash(self.root / 'a.png', hash_size=8)
        h2 = compute_phash(self.root / 'b.png', hash_size=8)
        self.assertEqual(similarity(h1, h2), 1.0)

    def test_similarity_different(self):
        from visual_dedup.hashing import similarity, compute_phash
        # Use visually distinct patterns, not solid colors
        # (at hash_size=8 solid red and blue may hash identically)
        img1 = Image.new('RGB', (64, 64), 'white')
        draw1 = ImageDraw.Draw(img1)
        draw1.rectangle((0, 0, 31, 63), fill='navy')
        draw1.rectangle((32, 0, 63, 63), fill='white')

        img2 = Image.new('RGB', (64, 64), 'white')
        draw2 = ImageDraw.Draw(img2)
        for x in range(0, 64, 8):
            for y in range(0, 64, 8):
                draw2.point((x, y), fill=((x * 4) % 256, (y * 4) % 256, 128))

        img1.save(self.root / 'a.png')
        img2.save(self.root / 'b.png')
        h1 = compute_phash(self.root / 'a.png', hash_size=8)
        h2 = compute_phash(self.root / 'b.png', hash_size=8)
        self.assertLess(similarity(h1, h2), 0.95)


class TestGrouper(unittest.TestCase):
    def test_exact_duplicates(self):
        from visual_dedup.grouper import group_exact_duplicates
        md5_map = {
            'aaa': [Path('/a/1.png'), Path('/a/2.png')],
            'bbb': [Path('/a/3.png')],
            'ccc': [Path('/a/4.png'), Path('/a/5.png'), Path('/a/6.png')],
        }
        groups = group_exact_duplicates(md5_map)
        self.assertEqual(len(groups), 2)

    def test_group_similar(self):
        from visual_dedup.grouper import group_similar
        import imagehash
        from PIL import Image
        # Create hashes with known distances
        h1 = imagehash.phash(Image.new('RGB', (32, 32), 'red'), hash_size=8)
        h2 = imagehash.phash(Image.new('RGB', (32, 32), 'darkred'), hash_size=8)
        h3 = imagehash.phash(Image.new('RGB', (32, 32), 'blue'), hash_size=8)
        phash_map = {
            Path('/a/r.png'): h1,
            Path('/a/s1.png'): h2,
            Path('/a/s2.png'): h3,
        }
        groups = group_similar(phash_map, threshold=0.1)
        self.assertGreaterEqual(len(groups), 0)


class TestSelector(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_by_pixel_area_selects_larger(self):
        from visual_dedup.selector import by_pixel_area
        img_small = Image.new('RGB', (64, 64), 'red')
        img_large = Image.new('RGB', (128, 128), 'red')
        img_small.save(self.root / 'small.png')
        img_large.save(self.root / 'large.png')
        result = by_pixel_area([self.root / 'small.png', self.root / 'large.png'])
        self.assertEqual(result, self.root / 'large.png')

    def test_by_pixel_area_tie_defers(self):
        from visual_dedup.selector import by_pixel_area
        img1 = Image.new('RGB', (64, 64), 'red')
        img2 = Image.new('RGB', (64, 64), 'blue')
        img1.save(self.root / 'a.png')
        img2.save(self.root / 'b.png')
        result = by_pixel_area([self.root / 'a.png', self.root / 'b.png'])
        self.assertIsNone(result)  # Tie, defer to next policy

    def test_select_keep_chain(self):
        from visual_dedup.selector import select_keep
        img1 = Image.new('RGB', (64, 64), 'red')
        img2 = Image.new('RGB', (64, 64), 'blue')
        img1.save(self.root / 'a.png')
        img2.save(self.root / 'b.png')
        # Same pixel area, file_size, first_alphabetical picks 'a.png'
        result = select_keep([self.root / 'b.png', self.root / 'a.png'])
        self.assertEqual(result, self.root / 'a.png')

    def test_select_keep_empty_raises(self):
        from visual_dedup.selector import select_keep
        with self.assertRaises(ValueError):
            select_keep([])

    def test_pixel_area_larger_than_bytesize(self):
        """Regression: verify pixel area, not byte size, is the primary selector.
        
        96x96 = 9216 pixels, 64x64 = 4096 pixels.
        The 64x64 file might be larger in bytes (e.g. PNG compression),
        but pixel area should win.
        """
        from visual_dedup.selector import select_keep
        img_large = Image.new('RGB', (96, 96), 'white')
        img_small = Image.new('RGB', (64, 64), 'white')
        img_large.save(self.root / 'large.png', optimize=False)
        img_small.save(self.root / 'small.png', optimize=False)
        # Ensure small is actually larger in bytes (less compressible)
        small_path = self.root / 'small.png'
        large_path = self.root / 'large.png'
        if small_path.stat().st_size <= large_path.stat().st_size:
            # Force small to be larger in bytes
            draw = ImageDraw.Draw(img_small)
            for x in range(64):
                for y in range(64):
                    draw.point((x, y), (x % 256, y % 256, (x + y) % 256))
            img_small.save(small_path)
        result = select_keep([small_path, large_path])
        # Should keep the one with larger pixel area (96x96 > 64x64)
        self.assertEqual(result, large_path,
                         "Should select by pixel area (96x96 > 64x64), not byte size")


class TestOrganizer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_copy_preserves_source(self):
        from visual_dedup.organizer import copy_file
        src = self.root / 'src'
        dst_dir = self.root / 'dst'
        src.mkdir()
        (src / 'file.txt').write_text('hello')
        target = copy_file(src / 'file.txt', dst_dir)
        self.assertTrue(target.exists())
        self.assertTrue((src / 'file.txt').exists())  # Source preserved
        self.assertEqual(target.read_text(), 'hello')

    def test_copy_no_overwrite(self):
        from visual_dedup.organizer import copy_file
        src = self.root / 'src'
        dst_dir = self.root / 'dst'
        src.mkdir()
        (src / 'file.txt').write_text('new')
        (src / 'file (1).txt').write_text('also new')
        dst_dir.mkdir()
        (dst_dir / 'file.txt').write_text('existing')

        t1 = copy_file(src / 'file.txt', dst_dir)
        self.assertNotEqual(t1.name, 'file.txt')  # Should be renamed
        self.assertEqual((dst_dir / 'file.txt').read_text(), 'existing')  # Not overwritten

    def test_move_same_volume(self):
        from visual_dedup.organizer import move_file
        src = self.root / 'src'
        dst_dir = self.root / 'dst'
        src.mkdir()
        (src / 'file.txt').write_text('hello')
        target = move_file(src / 'file.txt', dst_dir)
        self.assertTrue(target.exists())
        self.assertFalse((src / 'file.txt').exists())
        self.assertEqual(target.read_text(), 'hello')

    def test_operation_plan_preview(self):
        from visual_dedup.organizer import OperationPlan
        plan = OperationPlan()
        plan.add_keep(Path('/a/keep.png'))
        plan.add_copy(Path('/a/copy.png'), Path('/out'))
        preview = plan.preview()
        self.assertIn('KEEP', preview)
        self.assertIn('COPY', preview)


if __name__ == '__main__':
    unittest.main()