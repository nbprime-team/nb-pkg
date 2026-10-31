# AI 生成 / 辅助创作：DeepSeek V4.1 Flash（未人工审查）
"""U 盘模式下的计算器：探测、状态、部署。

计算器以 mass-storage 挂载时，盘根对应设备 C:\\，所以包要写到 <盘>/DATA/ 下。
所有写入都限制在 DATA/ 内，且只触碰索引里声明过的名字。
"""
import os
import shutil
import sys
import time

from . import artifacts, manifest

MARKER = "DATA"
STAGING = ".nb-pkg-staging"


def _dir_ci(root, name):
    try:
        for e in os.listdir(root):
            if e.lower() == name.lower():
                p = os.path.join(root, e)
                if os.path.isdir(p):
                    return p
    except OSError:
        pass
    return None


def roots():
    """枚举可能的挂载点。"""
    if os.name == "nt":
        for l in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            p = "%s:\\" % l
            if os.path.exists(p):
                yield p
    elif sys.platform == "darwin":
        if os.path.isdir("/Volumes"):
            for n in sorted(os.listdir("/Volumes")):
                yield os.path.join("/Volumes", n)
    else:
        user = os.environ.get("USER", "")
        for base in ("/media/%s" % user, "/run/media/%s" % user, "/mnt", "/media"):
            if not os.path.isdir(base):
                continue
            for n in sorted(os.listdir(base)):
                p = os.path.join(base, n)
                if not os.path.isdir(p):
                    continue
                yield p
                try:
                    for m in sorted(os.listdir(p)):
                        q = os.path.join(p, m)
                        if os.path.isdir(q):
                            yield q
                except OSError:
                    pass


def find(explicit=None):
    """返回 (盘根, DATA 目录) 或 None。"""
    if explicit:
        d = _dir_ci(explicit, MARKER)
        return (explicit, d) if d else None
    for r in roots():
        d = _dir_ci(r, MARKER)
        if d:
            return (r, d)
    return None


def status(device):
    """读设备上已装的包与入口。"""
    root, data = device
    sysdir = _dir_ci(data, "sys") or os.path.join(data, "sys")
    db = os.path.join(sysdir, "core.db")
    installed = {}
    if os.path.isfile(db):
        with open(db, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 4:
                    installed[(parts[0], parts[1])] = parts[2]
    entries = sorted(e for e in os.listdir(data) if e.lower().endswith(".hpappdir"))
    try:
        free = shutil.disk_usage(root).free
    except OSError:
        free = 0
    return {"installed": installed, "entries": entries, "free": free,
            "data": data, "root": root}


def plan(index, installed):
    """返回 (新增, 升级, 已是最新)。"""
    new, up, same = [], [], []
    for m in manifest.load_all(index):
        key = (m.name, m.version)
        if key in installed:
            same.append(m)
            continue
        older = [v for (n, v) in installed if n == m.name]
        (up if older else new).append(m)
    return new, up, same


def _copy_merge(src, dst):
    """把 src 合并进 dst（覆盖同名文件），不删除 dst 里其它内容。"""
    os.makedirs(dst, exist_ok=True)
    for n in os.listdir(src):
        s = os.path.join(src, n)
        d = os.path.join(dst, n)
        if os.path.isdir(s):
            _copy_merge(s, d)
        else:
            shutil.copy2(s, d)


def _rm(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def deploy(index, device, dry_run=False, keep_old=False,
           with_legacy=True, with_entries=True, flat=False, bundles=False):
    """构建到设备上的暂存目录，再合并进 DATA/。返回摘要 dict。"""
    st = status(device)
    data = st["data"]
    new, up, same = plan(index, st["installed"])
    summary = {"new": [m.name for m in new], "upgrade": [m.name for m in up],
               "same": [m.name for m in same], "installed": 0,
               "warnings": []}
    if dry_run:
        return summary

    staging = os.path.join(data, STAGING)
    _rm(staging)
    os.makedirs(staging)
    try:
        # 1) 生成核心区与入口
        if bundles:
            n = 0
            errs = []
            for m in manifest.load_all(index):
                if m.kind not in ("app", "tool", "pyapp"):
                    continue
                if not m.payload_path() and not m.get("payload_url"):
                    continue
                artifacts.bundle(m, os.path.join(staging, "bundles",
                                                 "%s.hpappdir" % m.name))
                n += 1
            summary["warnings"] += errs
            ent = os.path.join(staging, "bundles")
            if os.path.isdir(ent):
                for d in os.listdir(ent):
                    _copy_merge(os.path.join(ent, d), os.path.join(data, d))
            summary["installed"] = n
            return summary
        if flat:
            n = artifacts.sys_flat(index, os.path.join(staging, "sys"))
            errs = []
            # 扁平模式：先清掉旧的 bin/lib 目录，避免残留嵌套
            for kind in ("bin", "lib"):
                _rm(os.path.join(_dir_ci(data, "sys") or os.path.join(data, "sys"), kind))
        else:
            n, errs = artifacts.sys_tree(index, os.path.join(staging, "sys"))
        summary["warnings"] += errs
        if with_entries:
            for m in manifest.load_all(index):
                if m.kind in ("app", "tool", "pyapp"):
                    if not m.payload_path() and not m.get("payload_url"):
                        continue
                    artifacts.entry(m, os.path.join(
                        staging, "entries", "%s.hpappdir" % m.name), flat=flat)
        if with_legacy:
            artifacts.legacy_tree(index, os.path.join(staging, "pkg"))

        sysdir = _dir_ci(data, "sys") or os.path.join(data, "sys")
        os.makedirs(sysdir, exist_ok=True)

        # 2) 旧版本处理：先移除同名旧版本目录（可选保留）
        for m in manifest.load_all(index):
            for kind in ("bin", "lib"):
                base = os.path.join(sysdir, kind)
                if not os.path.isdir(base):
                    continue
                for d in os.listdir(base):
                    if d.startswith("%s-" % m.name) and d != "%s-%s" % (m.name, m.version):
                        old = os.path.join(base, d)
                        if keep_old:
                            shutil.move(old, old + ".old." + str(int(time.time())))
                        else:
                            _rm(old)

        # 3) 合并核心区、入口、兼容布局
        _copy_merge(os.path.join(staging, "sys"), sysdir)
        if with_entries:
            ent = os.path.join(staging, "entries")
            if os.path.isdir(ent):
                for d in os.listdir(ent):
                    _copy_merge(os.path.join(ent, d), os.path.join(data, d))
        if with_legacy:
            pkg = os.path.join(staging, "pkg")
            if os.path.isdir(pkg):
                _copy_merge(pkg, os.path.join(data, "pkg"))
        summary["installed"] = n
    finally:
        _rm(staging)
    return summary
