# AGENTS.md — 接手前必读

给接手的智能体/开发者。**先跑通验证，再改代码。**

> 本文件不假设项目位置，也不假设文件夹名叫什么。下文「项目根」= 本文件所在目录
> （含 `app/` 与 `main.py` 的那一层）。同级目录一律用「可能存在的兄弟目录」描述。

## 0. 三条命令先跑一遍

在项目根执行：

```bash
python tools/_selftest.py                      # 必须 ALL OK
python tools/baseline_shots.py "$TEMP/shots"   # 31 张状态底片，可用任意临时目录
python tools/compare_shots.py "<底片目录>" "$TEMP/shots"
```

`<底片目录>` = 兄弟目录 `备份/对照图-当前版本`。该目录不存在时跳过第三条，
改为人工看 2~3 张图。有底片时必须「全部 31 张完全一致」，不一致先查环境再动手。

## 1. 这是什么

Windows 桌面无边框置顶像素风工时挂件（PySide6 全自绘）。典型部署是同级几个文件夹：

| 兄弟目录（可能不存在） | 作用 | 改动须知 |
| --- | --- | --- |
| 源码目录（本目录） | 唯一要改的地方 | 改完要重新打包，否则 exe 落后 |
| `exe启动版/` 或任意 exe 目录 | 打包产物 + 用户 `config.json` / `data.json` | 只放构建结果，不改代码 |
| `打包工程/` | `build.spec` + 一键打包脚本 | `SRC` 硬编码兄弟目录名，改名必须同步 |
| `备份/` | 改造前原件、各版本底片、历史归档 | 只读参考，不要删 |

版本号在 `app/__init__.py` 的 `__version__` / `__version_label__`，
同时体现在窗口标题、托盘提示、右键菜单、exe 文件名。

## 2. 环境与打包

- Windows 10/11，Python 3.13，PySide6 6.12
- 运行：双击 `启动.bat`（`启动.bat` 用 `%~dp0` 定位，移动目录不影响）
- 打包（有 `打包工程/build.spec` 时）：
  ```bash
  python -m PyInstaller --noconfirm --clean \
    --distpath "../打包工程/dist" --workpath "../打包工程/build" \
    "../打包工程/build.spec"
  ```
  没有 spec 时：`python -m PyInstaller --noconfirm --onefile --windowed --name MCWorkTimer main.py`
  不要直接双击 `一键打包exe.bat`（末尾 `pause` 会挂住自动化）
- 单实例锁在 `%TEMP%\mc-worktimer.lock`，全局唯一，两个形态不能同时开
- 两个形态的 `data.json`（加班台账）**不共享**

## 3. 目录职责（改东西先看这张表）

```
app/
├─ widget.py     窗口本体（构造/尺寸档/位置/显示）
├─ ui/           consts(档位) clock(计时状态) content(文字) paint(绘制) interact(鼠标菜单)
├─ render/       palette(配色) common(画笔/材质) chrome(边框件) sky(天空)
│                meadow(花海/草皮卷/道具/整条进度条) weather(天气) overlay(木牌/烟花)
├─ theme.py      转发出口，老的 theme.xxx 仍有效
├─ engine.py     工时规则（纯逻辑，不依赖 Qt，可直接跑测试）
├─ weather.py    今天什么天（按日期播种）
├─ quotes.py     全部文案
├─ life.py       鸟群时刻表
└─ pixel_font.py 5×7 点阵数字 + 像素中文
```

加东西去哪：新道具→`render/meadow.py`；新天气→`weather.py`+`render/weather.py`；
新文案→`quotes.py`；新菜单项→`ui/interact.py`；新计时规则→`engine.py`。

## 4. 改完必须做的验收

1. `python tools/_selftest.py` → ALL OK
2. 视觉改动：重拍底片 + 逐像素比对；或按新画面更新底片目录
3. **交互改动：逐个点开每个弹窗、每个菜单项**（像素比对证明不了交互没坏）
4. 打包后启动 exe 跑 6~8 秒，确认不崩溃

## 5. 五条铁律（违反会让画面崩掉）

1. **1 单位 = 2px**，全部按整数单位布局，最后整体整数倍放大（`FastTransformation`）。
2. **这个尺寸只认四种信息**：大形状、重复成片、颜色跳变、文字。单点粒子（萤火虫）、
   小生物（蜜蜂/蝴蝶）、按原版比例画的动物——全部试过，全部失败。鸟群靠"队形重复"、
   花海靠"重复成片"才成立。
3. **不做整体提亮/闪白**，会被当成闪屏。庆祝只用烟花+彩纸叠加。
4. **所有随机必须按日期播种**（`day.toordinal()`），同一天刷新画面完全固定。
5. **不新增图片资源**：材质用确定性噪声程序化生成，`assets/fonts` 只放可选字体。

## 6. 已知坑（都踩过）

1. **函数体内的相对导入**：`app/ui/*` 里写 `from .dialogs import X` 会指向不存在的
   `app.ui.dialogs`，Qt 吞掉异常 → 表现成"点了没反应"。必须 `from ..dialogs`。
   搬文件后务必 `grep -rn "^\s\+from \." app/`。
2. **离屏模式没有字体**：`QT_QPA_PLATFORM=offscreen` 下 `QFontDatabase.families()` 返回 0，
   中文变空心方框。截图要用正常平台模式、只构造不 `show()`。
3. **闪烁类装饰要看时间**：木牌箭头、问候语用 `perf_counter()`；截图前要把**所有**
   `app.*` 模块里的 `_time` 都换成冻结对象，否则出现"只差一颗箭头"的假警报。
4. **同名嵌套函数**：`render/meadow.py` 与 `render/sky.py` 里各有一个 `put()`，
   按名字做 AST 比对会误报。
5. **`build.spec` 路径耦合**：`SRC = join(SPEC_DIR, "..", "Python版")`，改文件夹名不改正
   会"找不到项目目录"。
6. **进度条分层顺序**：`draw_meadow_bar` = 天空 → 未开垦泥地 → 已开垦草地/花海 → 道具 →
   午休旗 → 草皮卷 → 鸟群 → 天气。插入新元素要挑对层，压错层会挡花色或挡文字。

## 7. 不要做

- 不加音效、不加闪光/整体提亮
- 不做番茄钟/待办/喝水提醒（越界，会让它变成"要维护的工具"）
- 不加社交、排行榜
- 不做 3D、粒子光效、动图资源（破坏像素语言 + 撑大 exe）
- 不在 exe 目录里改代码

## 8. 待办 / 可继续的方向

- 天气还差「雾」「雪」（结构已就绪：`weather.py` 加一档 + `render/weather.py` 加一个画法）
- 连击（连续准点下班长金花）、当日小结面板（数据都在 `store.py`）
- 季节主题（春樱/秋黄/冬雪）
- 打包体积优化：`onedir` 替代 `onefile`，排除未用 Qt 模块
