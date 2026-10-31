# AI 生成 / 辅助创作：DeepSeek V4.1 Flash（未人工审查）
"""nb-pkg 命令行：校验、安装到核心区、生成入口/自包含包、取载荷。"""
import argparse
import hashlib
import os
import shutil
import sys
import urllib.request
import zipfile

from . import artifacts, manifest

DEV_SYS = "C:\\DATA\\sys"
DEV_ROOT = "C:\\DATA"


def _find(index, name):
    for m in manifest.load_all(index):
        if m.name == name:
            return m
    return None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_verify(args):
    errs, warns, seen = [], [], {}
    pkgs = manifest.load_all(args.index)
    if not pkgs:
        errs.append("没有找到 packages/*/pkg.cfg")
    for m in pkgs:
        errs += manifest.validate(m, require_payload=not args.allow_missing)
        key = (m.name, m.version)
        if key in seen:
            errs.append("%s: 重复的 name/version" % m.path)
        seen[key] = m.path
        hs, herr = manifest.hashes(m.dir)
        errs += herr
        for rel, want in hs.items():
            p = os.path.join(m.payload_root(), rel.replace("/", os.sep))
            if not os.path.isfile(p):
                errs.append("%s: hashes.txt 指到不存在的文件 %s" % (m.path, rel))
            elif _sha256(p) != want:
                errs.append("%s: 哈希不符 %s" % (m.path, rel))
        if m.get("payload_url") and not m.payload_path():
            warns.append("%s: 载荷在远端（payload_url）" % m.path)
    for w in warns:
        print("WARN ", w)
    for e in errs:
        print("ERROR", e)
    print("checked %d package(s): %d error(s), %d warning(s)"
          % (len(pkgs), len(errs), len(warns)))
    return 1 if errs else 0


def cmd_list(args):
    for m in manifest.load_all(args.index):
        print("%-18s %-5s %-6s %s" % (m.name, m.version, m.kind, m.get("provides")))
    return 0


def cmd_sys(args):
    n, errs = artifacts.sys_tree(args.index, args.dest, args.device_sys)
    for e in errs:
        print("ERROR", e)
    print("installed %d package(s) -> %s" % (n, args.dest))
    return 1 if errs else 0


def cmd_entry(args):
    m = _find(args.index, args.name)
    if not m:
        print("no such package:", args.name)
        return 2
    e = manifest.validate(m)
    if e:
        print("\n".join(e))
        return 1
    artifacts.entry(m, args.dest, args.device_sys)
    print("entry ->", args.dest)
    return 0


def cmd_bundle(args):
    m = _find(args.index, args.name)
    if not m:
        print("no such package:", args.name)
        return 2
    e = manifest.validate(m)
    if e:
        print("\n".join(e))
        return 1
    artifacts.bundle(m, args.dest, args.device_root)
    print("bundle ->", args.dest)
    return 0


def cmd_install(args):
    if args.layout == "legacy":
        n = artifacts.legacy_tree(args.index, os.path.join(args.dest, "pkg"))
        print("install(legacy): %d package(s) -> %s/pkg" % (n, args.dest))
        return 0
    n, errs = artifacts.sys_tree(args.index, os.path.join(args.dest, "sys"),
                                 args.device_sys)
    made = 0
    for m in manifest.load_all(args.index):
        if m.kind not in ("app", "tool"):
            continue
        d = os.path.join(args.dest, "entries", "%s.hpappdir" % m.name)
        artifacts.entry(m, d, args.device_sys)
        made += 1
    for e in errs:
        print("ERROR", e)
    print("install: %d package(s), %d entr(ies) -> %s" % (n, made, args.dest))
    return 1 if errs else 0


def cmd_hash(args):
    """为每个包生成/打印 hashes.txt（发布前跑一次，CI 会强制校验）。"""
    from . import artifacts
    made = 0
    for m in manifest.load_all(args.index):
        if not m.payload_path():
            continue
        lines = []
        for n in artifacts.payload_files(m):
            p = os.path.join(m.payload_root(), n.replace("/", os.sep))
            if os.path.isfile(p):
                lines.append("%s  %s" % (_sha256(p), n))
        if not lines:
            continue
        text = "\n".join(lines) + "\n"
        if args.write:
            with open(os.path.join(m.dir, "hashes.txt"), "w", encoding="utf-8") as f:
                f.write(text)
            made += 1
        else:
            print("# %s-%s" % (m.name, m.version))
            print(text, end="")
    if args.write:
        print("wrote hashes.txt for %d package(s)" % made)
    return 0


def cmd_fetch(args):
    m = _find(args.index, args.name)
    if not m or not m.get("payload_url"):
        print("no payload_url for", args.name)
        return 2
    os.makedirs(args.dest, exist_ok=True)
    target = os.path.join(args.dest, os.path.basename(m.get("payload_url")))
    print("fetch", m.get("payload_url"))
    urllib.request.urlretrieve(m.get("payload_url"), target)
    print("saved", target)
    if args.extract and zipfile.is_zipfile(target):
        with zipfile.ZipFile(target) as z:
            z.extractall(args.dest)
        print("extracted to", args.dest)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="nb-pkg", description="HP Prime 包管理器（PC 端）")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="校验索引里的所有包")
    v.add_argument("index")
    v.add_argument("--allow-missing", action="store_true",
                   help="允许载荷缺失（仅校验清单）")
    v.set_defaults(func=cmd_verify)

    l = sub.add_parser("list", help="列出包")
    l.add_argument("index")
    l.set_defaults(func=cmd_list)

    s = sub.add_parser("sys", help="把包安装进核心区（含 core.db）")
    s.add_argument("index")
    s.add_argument("dest")
    s.add_argument("--device-sys", default=DEV_SYS)
    s.set_defaults(func=cmd_sys)

    e = sub.add_parser("entry", help="生成薄 .hpappdir 入口")
    e.add_argument("index")
    e.add_argument("name")
    e.add_argument("dest")
    e.add_argument("--device-sys", default=DEV_SYS)
    e.set_defaults(func=cmd_entry)

    b = sub.add_parser("bundle", help="生成自包含 .hpappdir")
    b.add_argument("index")
    b.add_argument("name")
    b.add_argument("dest")
    b.add_argument("--device-root", default=DEV_ROOT)
    b.set_defaults(func=cmd_bundle)

    i = sub.add_parser("install", help="sys + 入口，一次生成")
    i.add_argument("index")
    i.add_argument("dest")
    i.add_argument("--device-sys", default=DEV_SYS)
    i.add_argument("--layout", choices=("sys", "legacy"), default="sys")
    i.set_defaults(func=cmd_install)

    h = sub.add_parser("hash", help="生成/打印 hashes.txt")
    h.add_argument("index")
    h.add_argument("--write", action="store_true")
    h.set_defaults(func=cmd_hash)

    f = sub.add_parser("fetch", help="下载 payload_url")
    f.add_argument("index")
    f.add_argument("name")
    f.add_argument("dest")
    f.add_argument("--extract", action="store_true")
    f.set_defaults(func=cmd_fetch)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
