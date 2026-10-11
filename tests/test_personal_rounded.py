import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('rounded', Path(__file__).resolve().parents[1]/'patches/patch-personal-rounded.py')
rounded = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rounded)

class PersonalRoundedTests(unittest.TestCase):
    def test_layer_is_idempotent_and_keeps_controls(self):
        original = '\tconst CSS = `\n/* fullscreen controls */\n`;\nif (kdeSession && !kdeBlurReady) root.dataset.dshOpaqueSidebar = "";'
        result = rounded.transform_preload(original)
        self.assertEqual(result, rounded.transform_preload(result))
        self.assertIn('/* fullscreen controls */', result)
        self.assertIn('clip-path: inset(0 round 12px)', result)
        self.assertIn('[data-fullscreen] body { clip-path: none; }', result)
        self.assertIn('if (process.platform === "linux")', result)
    def test_unknown_payload_fails_without_changes(self):
        with self.assertRaises(ValueError): rounded.transform_preload('new unknown preload')
        with self.assertRaises(ValueError): rounded.transform_main('new unknown main')
    def test_native_blur_disabled_idempotently(self):
        result = rounded.transform_main('\tconst configureKdeBlur = (window) => {\nreturn request;\n};')
        self.assertIn('return Promise.resolve(false)', result)
        self.assertEqual(result, rounded.transform_main(result))
