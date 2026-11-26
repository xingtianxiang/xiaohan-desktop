from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from desktop_platform import default_data_path, screen_bounds, MacInstanceLock
from keyboard_activity import KeyboardActivity
from mac_activity import counter_delta


class PlatformTests(unittest.TestCase):
    def test_mac_save_is_outside_signed_bundle(self):
        with patch('sys.platform','darwin'),patch.object(sys,'frozen',True,create=True),patch('sys.executable','/Applications/小汉.app/Contents/MacOS/小汉'):
            self.assertEqual(default_data_path(),Path.home()/'Library/Application Support/XiaohanDesktop/pet.json')

    def test_windows_source_and_bundle_save_locations(self):
        with patch('sys.platform','win32'),patch.object(sys,'frozen',False,create=True):
            self.assertEqual(default_data_path(),Path(__file__).resolve().parents[1]/'data/pet.json')
        exe=Path(tempfile.gettempdir())/'pet-release'/'小汉.exe'
        with patch('sys.platform','win32'),patch.object(sys,'frozen',True,create=True),patch('sys.executable',str(exe)):
            self.assertEqual(default_data_path(),exe.resolve().parent/'data/pet.json')

    @unittest.skipUnless(sys.platform=='win32','Windows monitor API')
    def test_bounds_follow_monitor_under_point(self):
        import ctypes
        metrics=ctypes.windll.user32.GetSystemMetrics
        primary=(0,0,metrics(0),metrics(1))
        self.assertEqual(screen_bounds(None,metrics(0)//2,metrics(1)//2),primary)
        # Points outside every monitor snap to the nearest one instead of the primary screen size.
        far_left,far_top=metrics(76)-5000,metrics(77)-5000
        left,top,right,bottom=screen_bounds(None,far_left,far_top)
        self.assertLessEqual(metrics(76),left);self.assertLessEqual(metrics(77),top)
        self.assertLess(left,right);self.assertLess(top,bottom)

    def test_counter_baseline_reset_and_wrap(self):
        self.assertEqual(counter_delta(400,400),0)
        self.assertEqual(counter_delta(400,405),5)
        self.assertEqual(counter_delta(400,0),0)
        self.assertEqual(counter_delta(0xfffffffe,1),3)

    def test_batched_counts_drive_same_rate_as_events(self):
        batched=KeyboardActivity();events=KeyboardActivity()
        batched.record_activity(10,5)
        for _ in range(5):events.record_activity(10)
        self.assertEqual(batched.count,events.count)
        self.assertAlmostEqual(batched.speed(10.1),events.speed(10.1))

    @unittest.skipUnless(sys.platform=='darwin','requires macOS flock')
    def test_second_instance_rejected_until_release(self):
        with tempfile.TemporaryDirectory() as folder:
            first=MacInstanceLock(Path(folder)/'pet.lock');second=MacInstanceLock(first.path)
            try:
                self.assertTrue(first.acquire());self.assertFalse(second.acquire())
                first.close();self.assertTrue(second.acquire())
            finally:first.close();second.close()
