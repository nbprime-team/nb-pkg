# AI 生成 / 辅助创作：DeepSeek V4.1 Flash（未人工审查）
"""从包清单生成三种产物：sys 核心区、薄入口、自包含 bundle。"""
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "templates", "loader_main.py")
SKIP = {"pkg.cfg", "src", "README.md", "hashes.txt", "__pycache__"}


def payload_names(m):
    for n in sorted(os.listdir(m.payload_root())):
        if n in SKIP:
            continue
        yield n


def copy_payload(m, dst):
    os.makedirs(dst, exist_ok=True)
    for n in payload_names(m):
        s = os.path.join(m.payload_root(), n)
        d = os.path.join(dst, n)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)


def _make_main(m, app_dir, elf):
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        text = f.read()
    esc = app_dir.replace("\\", "\\\\")
    esc_elf = elf.replace("\\", "\\\\")
    text = re.sub(r'APP_DIR\s*=\s*"[^"]*"',
                  lambda _: 'APP_DIR = "%s"' % esc, text, count=1)
    text = re.sub(r'APP_ELF\s*=\s*"[^"]*"',
                  lambda _: 'APP_ELF = "%s"' % esc_elf, text, count=1)
    return text.replace("[sh]", "[%s]" % m.name)


def payload_files(m):
    """递归列出载荷文件（相对包根），排除清单/源码/说明。"""
    out = []
    base = m.payload_root()
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ("src", "__pycache__")]
        rel_root = os.path.relpath(root, base)
        for f in sorted(files):
            if f in SKIP:
                continue
            rel = f if rel_root == "." else os.path.join(rel_root, f)
            out.append(rel.replace(os.sep, "/"))
    return sorted(out)


def _meta_names(m):
    return [n for n in payload_names(m)
            if n.endswith((".hpapp", ".hpappnote", ".hpappprgm", ".png"))]


def sys_tree(index, dest, device_sys="C:\\DATA\\sys", only=None):
    """把包安装进核心区；返回 (安装数, 错误列表)。"""
    from . import manifest
    errs, n = [], 0
    for m in manifest.load_all(index):
        if only and m.name not in only:
            continue
        e = manifest.validate(m)
        if e:
            errs += e
            continue
        kind = "lib" if m.kind == "lib" else "bin"
        target = os.path.join(dest, kind, "%s-%s" % (m.name, m.version))
        copy_payload(m, target)
        with open(os.path.join(dest, "core.db"), "a", encoding="utf-8") as f:
            f.write("%s %s %s %s\n" % (m.name, m.version, kind,
                                       "%s/%s-%s" % (kind, m.name, m.version)))
        n += 1
    return n, errs


def sys_flat(index, dest):
    r"""扁平核心区：sys/bin/<name>.elf、sys/lib/<name>.elf，不建版本子目录。

    规避固件对多层目录/带点目录名的不友好（DATA\sys\bin\hello-0.1\ 打不开）。
    """
    from . import manifest
    n = 0
    for m in manifest.load_all(index):
        if m.kind == "pyapp":
            continue
        rel = m.rel_entry()
        if not rel:
            continue
        src = os.path.join(m.payload_root(), rel.replace("/", os.sep))
        if not os.path.isfile(src):
            continue
        kind = "lib" if m.kind == "lib" else "bin"
        os.makedirs(dest, exist_ok=True)
        base = os.path.basename(rel)
        shutil.copy2(src, os.path.join(dest, base))
        with open(os.path.join(dest, "core.db"), "a", encoding="utf-8") as f:
            f.write("%s %s %s %s\n" % (m.name, m.version, kind, base))
        n += 1
    return n


def legacy_tree(index, dest):
    r"""兼容布局：C:\DATA\pkg\<name>-<ver>\（当前 sh 的扫描方式）。"""
    from . import manifest
    n = 0
    for m in manifest.load_all(index):
        copy_payload(m, os.path.join(dest, "%s-%s" % (m.name, m.version)))
        shutil.copy2(os.path.join(m.dir, "pkg.cfg"),
                     os.path.join(dest, "%s-%s" % (m.name, m.version), "pkg.cfg"))
        n += 1
    return n


def entry(m, dest, device_sys="C:\\DATA\\sys", flat=False):
    os.makedirs(dest, exist_ok=True)
    for n in _meta_names(m):
        s = os.path.join(m.payload_root(), n)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dest, n))
    if m.kind in ("app", "tool"):
        sub = "lib" if m.kind == "lib" else "bin"
        rel_elf = (m.rel_entry() or m.entry).replace("/", "\\")
        app_dir = device_sys if flat else \
            ("%s\\%s\\%s-%s" % (device_sys, sub, m.name, m.version))
        if flat:
            rel_elf = rel_elf.split("\\")[-1]
        with open(os.path.join(dest, "main.py"), "w", encoding="utf-8") as f:
            f.write(_make_main(m, app_dir, rel_elf))
    elif m.kind == "pyapp":
        copy_payload(m, dest)
    return dest


def bundle(m, dest, device_root="C:\\DATA"):
    copy_payload(m, dest)
    if m.kind in ("app", "tool"):
        base = os.path.basename(os.path.normpath(dest))
        with open(os.path.join(dest, "main.py"), "w", encoding="utf-8") as f:
            f.write(_make_main(m, "%s\\%s" % (device_root, base),
                               (m.rel_entry() or m.entry).replace("/", "\\")))
    return dest
