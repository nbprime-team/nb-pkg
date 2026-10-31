# AI 生成 / 辅助创作：DeepSeek V4.1 Flash（未人工审查）
import os
import tempfile
import unittest

from nb_pkg import artifacts, manifest


def make_pkg(root, name, kind="app", entry="hello.elf", extra=""):
    d = os.path.join(root, "packages", "%s-%s" % (name, "0.1"))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "pkg.cfg"), "w", encoding="utf-8") as f:
        f.write("name = %s\nversion = 0.1\nkind = %s\nentry = %s\n%s"
                % (name, kind, entry, extra))
    if entry and entry != ".":
        with open(os.path.join(d, entry), "wb") as f:
            f.write(b"\x7fELF" + b"\0" * 12)
    return d


class TestManifest(unittest.TestCase):
    def test_valid(self):
        with tempfile.TemporaryDirectory() as t:
            make_pkg(t, "hello")
            m = manifest.load_all(t)[0]
            self.assertEqual(manifest.validate(m), [])
            self.assertEqual(m.kind, "app")

    def test_bad_fields(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_pkg(t, "Hello", kind="app", entry="")
            m = manifest.load(os.path.join(d, "pkg.cfg"))
            self.assertTrue(any("name" in e for e in manifest.validate(m)))
            self.assertTrue(any("entry" in e for e in manifest.validate(m)))
        with tempfile.TemporaryDirectory() as t:
            d = make_pkg(t, "hello", kind="weird")
            m = manifest.load(os.path.join(d, "pkg.cfg"))
            self.assertTrue(any("kind" in e for e in manifest.validate(m)))

    def test_payload_url_ok(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_pkg(t, "lua", kind="lib", entry="", extra="payload_url = https://x\n")
            os.rename(os.path.join(d, "pkg.cfg"), os.path.join(d, "pkg.cfg.tmp"))
            with open(os.path.join(d, "pkg.cfg.tmp"), "a", encoding="utf-8") as f:
                f.write("lib = lua.elf\n")
            os.rename(os.path.join(d, "pkg.cfg.tmp"), os.path.join(d, "pkg.cfg"))
            m = manifest.load(os.path.join(d, "pkg.cfg"))
            self.assertEqual(manifest.validate(m), [])


class TestArtifacts(unittest.TestCase):
    def test_sys_tree(self):
        with tempfile.TemporaryDirectory() as t:
            make_pkg(t, "hello")
            n, errs = artifacts.sys_tree(t, os.path.join(t, "out"))
            self.assertEqual((n, errs), (1, []))
            self.assertTrue(os.path.isfile(
                os.path.join(t, "out", "bin", "hello-0.1", "hello.elf")))
            with open(os.path.join(t, "out", "core.db"), encoding="utf-8") as f:
                self.assertIn("hello 0.1 bin bin/hello-0.1", f.read())

    def test_entry_targets_sys(self):
        with tempfile.TemporaryDirectory() as t:
            make_pkg(t, "hello")
            m = manifest.load_all(t)[0]
            artifacts.entry(m, os.path.join(t, "e.hpappdir"))
            src = open(os.path.join(t, "e.hpappdir", "main.py"), encoding="utf-8").read()
            self.assertIn('APP_DIR = "C:\\\\DATA\\\\sys\\\\bin\\\\hello-0.1"', src)
            self.assertIn('APP_ELF = "hello.elf"', src)

    def test_bundle_contains_payload(self):
        with tempfile.TemporaryDirectory() as t:
            make_pkg(t, "hello")
            m = manifest.load_all(t)[0]
            out = os.path.join(t, "hello.hpappdir")
            artifacts.bundle(m, out)
            self.assertTrue(os.path.isfile(os.path.join(out, "hello.elf")))
            self.assertTrue(os.path.isfile(os.path.join(out, "main.py")))


if __name__ == "__main__":
    unittest.main()
