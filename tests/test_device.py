# AI 生成 / 辅助创作：DeepSeek V4.1 Flash（未人工审查）
import os
import tempfile
import unittest

from nb_pkg import device, manifest


def make_index(root, version="0.1"):
    d = os.path.join(root, "packages", "hello-%s" % version)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "pkg.cfg"), "w", encoding="utf-8") as f:
        f.write("name = hello\nversion = %s\nkind = app\nentry = hello.elf\n" % version)
    with open(os.path.join(d, "hello.elf"), "wb") as f:
        f.write(b"\x7fELF" + b"\0" * 8)
    return root


class TestDevice(unittest.TestCase):
    def test_find_requires_data(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertIsNone(device.find(t))
            os.makedirs(os.path.join(t, "DATA"))
            self.assertEqual(device.find(t)[0], t)

    def test_dry_run_touches_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            idx = make_index(os.path.join(t, "idx"))
            dev = os.path.join(t, "dev")
            os.makedirs(os.path.join(dev, "DATA"))
            r = device.deploy(idx, device.find(dev), dry_run=True, all_=True)
            self.assertEqual(r["new"], ["hello"])
            self.assertEqual(os.listdir(os.path.join(dev, "DATA")), [])

    def test_deploy_and_status(self):
        with tempfile.TemporaryDirectory() as t:
            idx = make_index(os.path.join(t, "idx"))
            dev = os.path.join(t, "dev")
            os.makedirs(os.path.join(dev, "DATA"))
            device.deploy(idx, device.find(dev), all_=True)
            data = os.path.join(dev, "DATA")
            self.assertTrue(os.path.isfile(os.path.join(data, "sys", "core.db")))
            self.assertTrue(os.path.isfile(os.path.join(data, "hello.hpappdir", "main.py")))
            self.assertTrue(os.path.isdir(os.path.join(data, "pkg", "hello-0.1")))
            st = device.status(device.find(dev))
            self.assertIn(("hello", "0.1"), st["installed"])
            new, up, same = device.plan(idx, st["installed"])
            self.assertEqual([m.name for m in same], ["hello"])

    def test_upgrade_plan(self):
        with tempfile.TemporaryDirectory() as t:
            dev = os.path.join(t, "dev")
            os.makedirs(os.path.join(dev, "DATA"))
            idx1 = make_index(os.path.join(t, "v1"), "0.1")
            device.deploy(idx1, device.find(dev), all_=True)
            idx2 = make_index(os.path.join(t, "v2"), "0.2")
            st = device.status(device.find(dev))
            new, up, same = device.plan(idx2, st["installed"])
            self.assertEqual([m.name for m in up], ["hello"])


if __name__ == "__main__":
    unittest.main()
