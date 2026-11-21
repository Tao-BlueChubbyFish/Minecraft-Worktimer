"""一键生成发布包。

做的事：
1. 从 app/__init__.py 读当前版本号
2. 把 dist 里刚打好的 exe 复制进 <父目录>/exe启动版/（运行版永远是最新的）
3. 把源码（排除个人数据、缓存、打包中间产物）复制到 <父目录>/打包工程/发布/vX.Y/源码/
4. 写一份「上传步骤.txt」，里面写清这次要传什么

exe 只留两处：exe启动版（你双击运行的）+ 打包工程/dist（打包产物）。
发布目录里**不再放 exe 副本**，免得三份一样的文件不知道用哪个。

为什么不直接传整个项目：`config.json` / `data.json` 里是你的上班时间和加班台账，
传到公开仓库等于公开作息。这个脚本只带源码。

用法：双击 打包工程/一键发版.bat，或 `python tools/make_release.py`
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]        # 源码根（含 app/ main.py 那一层）
BASE = ROOT.parent                                # 同级目录：exe启动版 / 打包工程 / 发布

# 复制源码时要跳过的东西
SKIP_DIR = {"__pycache__", ".git", ".workbuddy", "build", "dist", ".venv", "venv"}
SKIP_FILE = {"config.json", "data.json", "crash.log"}
SKIP_SUFFIX = {".pyc", ".pyo", ".log", ".spec"}

REPO = "https://github.com/Tao-BlueChubbyFish/Minecraft-Worktimer"


def read_version() -> tuple[str, str]:
    ns: dict = {}
    text = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    exec(compile(text, "__init__.py", "exec"), ns)          # 只读常量，安全
    return str(ns["__version__"]), str(ns["__version_label__"])


def copy_tree(src: Path, dst: Path) -> int:
    count = 0
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        if any(part in SKIP_DIR for part in rel.parts):
            continue
        if item.is_dir():
            continue
        if item.name in SKIP_FILE or item.suffix in SKIP_SUFFIX:
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        count += 1
    return count


def main() -> int:
    version, label = read_version()
    tag = label if label.startswith("v") else f"v{label}"

    out = BASE / "打包工程" / "发布" / tag
    if out.exists():
        shutil.rmtree(out)
    src_dir = out / "源码"
    src_dir.mkdir(parents=True)

    n = copy_tree(ROOT, src_dir)

    # .gitignore：防止以后有人在本地误提交个人数据
    (src_dir / ".gitignore").write_text(
        "config.json\ndata.json\ncrash.log\n*.log\n__pycache__/\n*.pyc\ndist/\nbuild/\n*.spec\n",
        encoding="utf-8")

    # exe：从 dist 复制进「exe启动版」，运行版跟着发版一起更新
    exe_name = f"MCWorkTimer_{tag}.exe"
    dist_exe = BASE / "打包工程" / "dist" / exe_name
    run_dir = BASE / "exe启动版"
    run_dir.mkdir(exist_ok=True)
    run_exe = run_dir / exe_name
    if dist_exe.exists():
        shutil.copy2(dist_exe, run_exe)
        for old in run_dir.glob("MCWorkTimer_*.exe"):
            if old.name != exe_name:
                old.unlink()                 # 老版本的 exe 挪走，免得双击错文件
        exe_note = f"{run_exe}（{run_exe.stat().st_size / 1048576:.1f} MB）"
    elif run_exe.exists():
        exe_note = f"{run_exe}（旧文件，dist 里没找到这次打包的产物）"
    else:
        exe_note = f"⚠ 没找到 {exe_name}，先跑一次打包"

    (out / "上传步骤.txt").write_text(f"""MC 工时牌 {tag} 发布包

一、源码（拖拽上传）
 1. 打开 {REPO}
 2. Add file → Upload files
 3. 打开本文件夹里的「源码」，Ctrl+A 全选里面的东西，拖进网页
    ★ 拖里面的内容，不要拖「源码」文件夹本身，否则会多套一层目录
 4. Commit changes

二、exe（Release 附件，不要放进仓库）
 1. Releases → Create a new release（已存在就 Edit）
 2. Tag: {tag}    标题: MC 工时牌 {tag}
 3. 附件（从这里取，发布目录里不再放 exe 副本）：{exe_note}
 4. Publish release

三、版本文件 latest.json（版本变了才改）
 {{
   "version": "{version}",
   "url": "{REPO}/releases/latest"
 }}

四、给自己的提醒
 · config.json / data.json 是个人数据，已经在「源码」里排除了
 · 程序里的「检查更新」读的就是 latest.json，改了版本号记得同步
""", encoding="utf-8")

    print(f"发布包已生成：{out}")
    print(f"  源码 {n} 个文件")
    print(f"  exe  {exe_note}")
    print(f"  版本 {version}（{tag}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
