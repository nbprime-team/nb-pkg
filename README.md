# nb-pkg —— HP Prime 包管理器（PC 端）

> ⚠️ AI 生成 / 辅助创作：DeepSeek V4.1 Flash（未人工审查）

校验 `nb-package-index` 里的包，并把它们生成计算器可用的三种形态：

| 形态 | 产物 | 用途 |
|---|---|---|
| `sys` | `sys/<bin|lib>/<name>-<ver>/` + `core.db` | 共享核心区（省 Flash、统一版本） |
| `entry` | 薄 `.hpappdir`（只含 main.py + 元数据/图标） | 用户应用入口，载荷留在 sys |
| `bundle` | 自包含 `.hpappdir`（含载荷） | 直接拷给别人，或作为 release 资产 |
| `install` | 上述 sys + 全部入口，一次生成 | 装机 |

## 用法

```bash
git clone https://github.com/nbprime-team/nb-pkg.git
cd nb-pkg

python3 -m nb_pkg verify  ../nb-package-index          # 校验清单/哈希/载荷
python3 -m nb_pkg list    ../nb-package-index
python3 -m nb_pkg install ../nb-package-index out      # out/sys + out/entries/
python3 -m nb_pkg bundle  ../nb-package-index hello out/hello.hpappdir
python3 -m nb_pkg fetch   ../nb-package-index tcc out  # 取 payload_url
python3 -m nb_pkg hash    ../nb-package-index --write  # 生成 hashes.txt（发布前）
```

生成的路径默认是设备视角（`C:\DATA\sys`、`C:\DATA\<name>.hpappdir`），
用 `--device-sys` / `--device-root` 可改。

## 设备部署（U 盘模式）

计算器以 U 盘模式连接后，盘根对应设备 `C:\`，包写入 `<盘>/DATA/`：

```bash
python3 -m nb_pkg device                        # 列出检测到的计算器盘
python3 -m nb_pkg status ../nb-package-index    # 对比设备与索引（新增/升级/已最新）
python3 -m nb_pkg deploy ../nb-package-index    # 安装/升级（--dry-run 只看计划）
```

- 自动探测 Windows 盘符、macOS `/Volumes`、Linux `/media|/run/media|/mnt`，以 `DATA/` 目录识别；
- 先构建到 `DATA/.nb-pkg-staging`，再合并进 `sys/`、入口、`pkg/`，完成后清理；
- 只触碰索引里声明过的名字；`--keep-old` 保留旧版本目录，`--no-legacy` 不写兼容 `pkg/`；
- 入口里的设备路径固定为 `C:\DATA\...`，与盘符无关。

## 校验规则（`verify`）

- 必填：`name`（小写/数字/-）、`version`（MAJ.MIN）、`kind`（app/tool/lib/pyapp）；
- `app/tool` 需要 `entry`，`lib` 需要 `lib`，且必须是**相对包根**的路径；
- `app/tool/lib` 要么有本地载荷，要么有 `payload_url`；
- 可选 `hashes.txt`（`sha256  path` 格式）：存在则逐文件校验；
- 同一 `name+version` 不允许重复。

## 与仓库划分的关系

- 本仓库只放**工具**（校验/生成/取载荷），不放应用；
- 应用与清单在 `nb-package-index`；
- 平台 API、SDK、编译器包装在 `toolchain`；
- 大型应用源码在各自仓库，索引里只留清单与载荷指针。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

CI 见 `.github/workflows/ci.yml`：跑单测，并 clone `nb-package-index` 做一次 `verify`。
