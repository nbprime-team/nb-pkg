# AI 生成 / 辅助创作：DeepSeek V4.1 Flash（未人工审查）
"""pkg.cfg 的解析与校验。"""
import os
import re

KINDS = ("app", "tool", "lib", "pyapp", "upsilon")
ABIS = ("shell", "hpconfig", "plua", "upsilon")
VER_RE = re.compile(r"^\d+\.\d+$")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class Manifest:
    def __init__(self, path, data):
        self.path = path
        self.dir = os.path.dirname(path)
        self.data = data

    def get(self, key, default=""):
        return self.data.get(key, default)

    @property
    def name(self):
        return self.get("name")

    @property
    def version(self):
        return self.get("version")

    @property
    def kind(self):
        return self.get("kind", "app")

    @property
    def entry(self):
        return self.get("entry")

    @property
    def lib(self):
        return self.get("lib")

    @property
    def payload_dir(self):
        return self.get("payload")

    def payload_root(self):
        if self.payload_dir:
            return os.path.join(self.dir, self.payload_dir.replace("\\", "/"))
        return self.dir

    def rel_entry(self):
        rel = self.lib if self.kind == "lib" else self.entry
        if not rel:
            return None
        rel = rel.replace("\\", "/")
        pre = (self.payload_dir or "").replace("\\", "/").strip("/")
        if pre and rel.startswith(pre + "/"):
            rel = rel[len(pre) + 1:]
        return rel

    def payload_path(self):
        """入口/库文件的本地路径；payload_url 包返回 None。"""
        rel = self.rel_entry()
        if not rel or rel == ".":
            return None
        p = os.path.join(self.payload_root(), rel)
        return p if os.path.isfile(p) else None


def load(path):
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return Manifest(path, data)


def load_all(index_dir):
    out = []
    pkg_root = os.path.join(index_dir, "packages")
    if not os.path.isdir(pkg_root):
        return out
    for name in sorted(os.listdir(pkg_root)):
        cfg = os.path.join(pkg_root, name, "pkg.cfg")
        if os.path.isfile(cfg):
            out.append(load(cfg))
    return out


def validate(m, require_payload=True):
    """返回错误列表（空 = 通过）。"""
    e = []
    if not m.name:
        e.append("%s: 缺 name" % m.path)
    elif not NAME_RE.match(m.name):
        e.append("%s: name 非法（小写字母/数字/-）" % m.path)
    if not m.version:
        e.append("%s: 缺 version" % m.path)
    elif not VER_RE.match(m.version):
        e.append("%s: version 必须是 MAJ.MIN" % m.path)
    if m.kind not in KINDS:
        e.append("%s: kind 必须是 %s" % (m.path, "/".join(KINDS)))
    abi = m.get("abi")
    if abi and abi not in ABIS:
        e.append("%s: abi 必须是 %s" % (m.path, "/".join(ABIS)))

    if m.kind in ("app", "tool", "lib"):
        rel = m.lib if m.kind == "lib" else m.entry
        if not rel:
            e.append("%s: kind=%s 需要 %s" % (m.path, m.kind,
                                              "lib" if m.kind == "lib" else "entry"))
        elif os.path.isabs(rel) or rel.startswith(("\\", "/")):
            e.append("%s: 路径必须是相对包根的" % m.path)
    if m.kind == "pyapp" and m.entry and m.entry not in (".",) and not m.entry.endswith(".py"):
        e.append("%s: pyapp 的 entry 应为 .py 或 '.'" % m.path)

    if require_payload and m.kind in ("app", "tool", "lib"):
        if not m.payload_path() and not m.get("payload_url"):
            e.append("%s: 载荷缺失且没有 payload_url" % m.path)
    return e


def hashes(path_dir):
    """读取可选的 hashes.txt（sha256sum 格式）。返回 (dict, errors)。"""
    f = os.path.join(path_dir, "hashes.txt")
    out, err = {}, []
    if not os.path.isfile(f):
        return out, err
    with open(f, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) != 2 or len(parts[0]) != 64:
                err.append("%s:%d: 哈希格式错误" % (f, i))
                continue
            out[parts[1].lstrip("*")] = parts[0]
    return out, err
