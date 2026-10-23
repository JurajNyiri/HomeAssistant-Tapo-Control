"""Storage layout checks runnable without Home Assistant installed."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

spec = importlib.util.spec_from_file_location(
    'media_storage', Path(__file__).parents[1] / 'custom_components/tapo_control/media_storage.py'
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class StorageLayoutTests(unittest.TestCase):
    def test_timezone_and_child_filename(self):
        # 2024-01-01 23:30 UTC falls on January 2 in Stockholm.
        name = 'hub-child-1704151800-1704151860.mp4'
        self.assertEqual(str(m.recording_path('/archive', 'videos', name, m.DATED,
                                            'Europe/Stockholm')),
                         '/archive/videos/2024/01/02/' + name)
        self.assertEqual(str(m.recording_path('/archive', 'videos', name, m.FLAT,
                                            'Europe/Stockholm')),
                         '/archive/videos/' + name)

    def test_round_trip_preserves_contents_and_partial_download(self):
        with TemporaryDirectory() as root:
            for folder, ext in [('videos', 'mp4'), ('thumbs', 'jpg')]:
                p = Path(root) / folder / f'1704151800-1704151860.{ext}'
                p.parent.mkdir()
                p.write_bytes(folder.encode())
            partial = Path(root) / 'videos/1704151800-1704151860.ts'
            partial.write_bytes(b'partial')
            self.assertEqual(m.migrate_layout(root, m.DATED, 'Europe/Stockholm'), 2)
            self.assertEqual(m.migrate_layout(root, m.DATED, 'Europe/Stockholm'), 0)
            self.assertTrue(partial.exists())
            self.assertEqual(m.migrate_layout(root, m.FLAT, 'Europe/Stockholm'), 2)
            for folder, ext in [('videos', 'mp4'), ('thumbs', 'jpg')]:
                self.assertEqual((Path(root) / folder / f'1704151800-1704151860.{ext}').read_bytes(), folder.encode())

    def test_collision_preflight_does_not_move_other_files(self):
        with TemporaryDirectory() as root:
            videos = Path(root) / 'videos'
            videos.mkdir()
            source = videos / '1704151800-1704151860.mp4'
            source.write_bytes(b'original')
            target = m.recording_path(root, 'videos', source.name, m.DATED, 'UTC')
            target.parent.mkdir(parents=True)
            target.write_bytes(b'conflict')
            with self.assertRaises(ValueError):
                m.migrate_layout(root, m.DATED, 'UTC')
            self.assertEqual(source.read_bytes(), b'original')
            self.assertEqual(target.read_bytes(), b'conflict')

    def test_interrupted_migration_can_resume(self):
        with TemporaryDirectory() as root:
            videos = Path(root) / 'videos'
            videos.mkdir()
            for start in [1704151800, 1704151900]:
                p = videos / f'{start}-{start+60}.mp4'
                p.write_bytes(b'video')
            source = next(videos.glob('*.mp4'))
            target = m.recording_path(root, 'videos', source.name, m.DATED, 'UTC')
            target.parent.mkdir(parents=True)
            source.rename(target)
            self.assertEqual(m.migrate_layout(root, m.DATED, 'UTC'), 1)
            self.assertEqual(len(m.recording_files(videos)), 2)


if __name__ == '__main__':
    unittest.main()
