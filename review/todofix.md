# todofix.md — eetool 完整修复计划

基于 `diff1.md` 的完整差异分析及第二轮评估补充。

---

## 优先级分类

- **P0 — 阻塞性 bug**：用户操作导致错误或数据损坏
- **P1 — 功能回退**：原始技能有的功能在新 CLI 中不可用
- **P2 — 文档补全**：SKILL.md / install.ps1 缺少关键信息
- **P3 — 代码质量**：无用代码、边界情况

---

## P0 — 阻塞性 Bug

### P0-1: do_sync 不传 --duration 时误改 setTime

**文件**: `src/eetool/capture/atk_cli.py` cmd_capture (~L556-579)

**复现**:
```bash
eetool capture start --ch 0,1,2,3
# 输出: [sync] differences: {'setTime_ms': 3000}  ← set.ini 被改写
# 输出: Post-restart preflight failed              ← GUI 重启后失败
```

**根因**: 传 `--ch` 触发 `do_sync=True`，`sync_set_ini(..., duration_s=3.0)` 把默认值写入 set.ini，覆盖了 GUI 的 setTime (如 50000ms)。

**修复方案**:

1. 在 cmd_capture 中增加 `explicit_duration` 判断：
```python
explicit_duration = args.duration != "3s"
```

2. `do_sync` 中用 `explicit_duration` 替代 `args.duration != "3s"`：
```python
do_sync = (
    args.sync
    or explicit_ch
    or explicit_hz
    or explicit_threshold
    or explicit_duration
) and not pf_sync_done
```

3. `sync_set_ini` 调用时只有显式传了才传 duration_s：
```python
sync_result = sync_set_ini(
    channels=ch_list_for_sync,
    set_hz=args.sample_rate_hz,
    threshold=args.threshold,
    duration_s=duration_s if explicit_duration else None,
)
```

4. 在 `lib_config_sync.py` 的 `sync_set_ini` 中，只在 `duration_s is not None` 时才写入 setTime：
```python
if duration_s is not None:
    desired['settingData']['setTime'] = int(duration_s * 1000)
```

**预期效果**: 不传 `--duration` 时 set.ini.setTime 不被修改，与原版行为一致；传 `--duration 5s` 时写 setTime。

---

### P0-2: do_sync 非默认 --duration 触发 GUI 重启

**文件**: 同上

**复现**:
```bash
eetool capture start --duration 10s
# 即使不加 --sync，也会写入 set.ini + 可能重启 GUI
```

**说明**: P0-1 修复会同时解决这个问题。用户显式传 `--duration 10s` 时：
- 改 set.ini.setTime（这是合理的新功能）
- 重启 GUI（只在 set.ini 真的变更时）
- 默认值不触发同步（P0-1 修复）

---

### P0-3: Proxy DLL 基础设施完全缺失

**问题**: 新项目**完全没有** `proxy_dll/` 目录及其所有内容。

**影响**: 
- ATK-Logic 采集自动化的核心组件缺失
- Proxy DLL 用于拦截 GUI 的 Qt5Network 调用，实现 CLI 与 GUI 的通信
- 没有 proxy DLL，用户无法完成首次部署

**原始内容** (`C:/Users/yg/.claude/skills/__myskills/electro_bak/atk-logic-capture/proxy_dll/`):
```
proxy_dll/
├── proxy_main.c              # 23,610 bytes - C source
├── Qt5Network_proxy.def      # 202,772 bytes - DEF file with all Qt5Network exports
├── build.ps1                 # 2,159 bytes - MSVC build script
├── README.md                 # Build & deploy instructions
└── outdll/
    ├── Qt5Network.dll        # Pre-built proxy DLL (~307 KB)
    ├── .gitignore
    └── (其他构建产物 .lib, .exp, .obj)
```

**修复**: 
```bash
# 从原始项目复制整个目录
cp -r "C:/Users/yg/.claude/skills/__myskills/electro_bak/atk-logic-capture/proxy_dll" \
      "E:/__work/BaseTools/eetool/"
```

验证以下文件存在：
- `proxy_dll/proxy_main.c`
- `proxy_dll/Qt5Network_proxy.def`
- `proxy_dll/build.ps1`
- `proxy_dll/README.md`
- `proxy_dll/outdll/Qt5Network.dll` (预构建版本)
- `proxy_dll/outdll/.gitignore`

**优先级**: **P0 致命** — 这是 ATK-Logic 集成的核心依赖，缺失导致功能完全不可用。

---

## P1 — 功能回退

### P1-1: Serial 恢复配置持久化

**文件**: `src/eetool/commands/serial.py`

**问题**: 原始 `serial_monitor.py` 通过 `serial_monitor.ini` 持久化 port/baud/bytesize/parity/stopbits/hex/timeout。新版完全丢失。

**修复**:
1. 在 `send_command()` 和 `listen_port()` 结束后保存当前配置
2. 下次启动时自动恢复（函数开头读取 INI 作为默认值）
3. INI 路径：`~/.local/share/eetool/serial.ini`（用 `platformdirs` 或 `os.path.expanduser`）

示例配置结构：
```ini
[serial]
port = COM7
baudrate = 115200
bytesize = 8
parity = N
stopbits = 1
timeout = 1.0
hex_mode = false
```

---

### P1-2: Serial 恢复 bytesize/parity/stopbits 配置

**文件**: `commands/serial.py` `add_subparser()` + `_open_serial()`

**问题**: 硬编码 8N1，原始支持 5-8 数据位、N/E/O/M/S 校验、1-2 停止位。

**修复**:
1. 在 `serial listen` 和 `serial send` 子命令中增加参数：
   - `--bytesize` (choices=[5, 6, 7, 8], default=8)
   - `--parity` (choices=['N', 'E', 'O', 'M', 'S'], default='N')
   - `--stopbits` (choices=[1, 1.5, 2], default=1)

2. 修改 `_open_serial()` 接受这些参数：
```python
def _open_serial(port: str, baudrate: int, bytesize: int, parity: str, 
                 stopbits: float, timeout: float) -> serial.Serial:
    return serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        timeout=timeout,
    )
```

3. 恢复连接提示信息的帧格式显示：
```python
print(f"[INFO] Connected to {port} @ {baudrate} baud ({bytesize}{parity}{stopbits})")
```

---

### P1-3: Pin2json 恢复错误 stderr

**文件**: `src/eetool/commands/pin2json.py` `_generate_symbol()`

**问题**: `CalledProcessError` 未被包装为 `RuntimeError`，stderr 丢失。

**修复**:
```python
try:
    subprocess.run(
        [exe, ...], 
        check=True, 
        capture_output=True, 
        text=True
    )
except subprocess.CalledProcessError as e:
    raise RuntimeError(
        f"JLC2KiCadLib failed to generate symbol for {part_id}:\n{e.stderr.strip()}"
    ) from e
```

---

### P1-4: Install.ps1 补全 ATK-Logic 部署步骤

**文件**: `install.ps1`

**问题**: 缺少 ATK-Logic GUI 检测、proxy DLL 部署、config 路径更新、uiautomation 安装、preflight 验证。

**修复**: 在现有 Python 包安装流程后增加新 section：

#### 1. ATK-Logic GUI 检测
搜索标准路径列表（参考原始 install.ps1 第 50-70 行）：
```powershell
$StandardPaths = @(
    'D:\Programs\ATK-Logic\ATK-Logic.exe',
    'C:\Program Files\ATK-Logic\ATK-Logic.exe',
    'C:\Program Files (x86)\ATK-Logic\ATK-Logic.exe',
    # ... 其他路径
)
```

#### 2. Proxy DLL 部署 (P2-6 细节)
```powershell
# 2.1 检查原始 Qt5Network.dll 状态
$GuiDir = Split-Path $GuiExe
$OriginalDll = Join-Path $GuiDir 'Qt5Network.dll'
$BackupDll = Join-Path $GuiDir 'Qt5Network_real.dll'
$ProxyDll = Join-Path $PSScriptRoot 'proxy_dll\outdll\Qt5Network.dll'

# 2.2 判断是否已部署过 proxy
$IsProxy = (Get-Item $OriginalDll).Length -lt 400KB

# 2.3 备份原始 DLL (只在首次部署时)
if (-not $IsProxy -and -not (Test-Path $BackupDll)) {
    Copy-Item $OriginalDll $BackupDll -Force
    Write-Host "[Install] Backed up Qt5Network.dll -> Qt5Network_real.dll"
}

# 2.4 检查 GUI 进程
$GuiProcess = Get-Process -Name 'ATK-Logic' -ErrorAction SilentlyContinue
if ($GuiProcess) {
    Write-Warning "ATK-Logic GUI is running. Please close it and re-run install.ps1"
    exit 1
}

# 2.5 部署 proxy DLL
Copy-Item $ProxyDll $OriginalDll -Force
Write-Host "[Install] Deployed proxy Qt5Network.dll"

# 2.6 验证部署
$DeployedSize = (Get-Item $OriginalDll).Length
if ($DeployedSize -lt 200KB -or $DeployedSize -gt 400KB) {
    Write-Warning "Proxy DLL size unexpected: $($DeployedSize / 1KB) KB"
}
```

#### 3. _config.py 路径更新
检测 GUI_DIR 是否需要更新（读取 `src/eetool/capture/_config.py`，替换路径变量）。

#### 4. uiautomation 安装
```powershell
& $VenvPython -m pip install uiautomation
```

#### 5. Preflight 验证
```powershell
& $VenvPython -m eetool.capture.atk_preflight --fix --json
```

参考原始: `C:/Users/yg/.claude/skills/__myskills/electro_bak/atk-logic-capture/install.ps1`

---

### P1-5: ATK-Logic README.md 缺失

**问题**: 原始项目有详细的 `atk-logic-capture/README.md`（113 行），包含:
- 快速开始命令示例
- 前置条件列表（Windows 版本、Python 版本、硬件要求）
- `install.ps1` 做了什么（7 步详细说明）
- 目录布局图
- 手动部署步骤（5 步）
- License 信息

**修复**: 
选项 1: 复制到 `docs/capture-deployment.md`
```bash
cp "C:/Users/yg/.claude/skills/__myskills/electro_bak/atk-logic-capture/README.md" \
   "E:/__work/BaseTools/eetool/docs/capture-deployment.md"
```

选项 2: 在顶层 `README.md` 中增加 "ATK-Logic Capture Setup" 章节

**优先级**: P1 — 用户首次部署时的参考文档。

---

### P1-6: Proxy DLL README.md 缺失

**问题**: 原始 `proxy_dll/README.md` 包含构建和部署说明。

**修复**: 随 P0-3 修复自动包含（复制整个 `proxy_dll/` 目录时保留 README.md）。

---

### P1-7: Keil UV4 CLI 参考文档缺失

**问题**: 原始 `keil-batch-gen/uv4-cli.md` 包含完整的 Keil µVision 命令行参数表（中文，52 行）。

**修复**: 
```bash
cp "C:/Users/yg/.claude/skills/__myskills/electro_bak/keil-batch-gen/uv4-cli.md" \
   "E:/__work/BaseTools/eetool/docs/keil-uv4-cli-reference.md"
```

或在 SKILL.md 的 Keil 章节中增加内联表格。

---

## P2 — 文档补全 (SKILL.md)

所有文档补充到根目录 `SKILL.md` 中。

### P2-1: atk-logic-capture SKILL.md 补全

**优先级顺序**:
1. **采集工作流**（agent 行为规则）
   - 默认采集不确认（除非改 set.ini 或 duration > 10s）
   - preflight 自动检测（4 项检查）
   - save flow（Ctrl+S 自动化）
   - isCtrlSPressed 变量作用

2. **采集参数表**
   | 参数 | 说明 | 默认值 | 示例 |
   |------|------|--------|------|
   | `--ch` | 通道列表 | 无 | `--ch 0,1,2,3` |
   | `--duration` | 采集时长 | 3s | `--duration 5s` |
   | `--sample-rate-hz` | 采样率 | 无（使用 set.ini） | `--sample-rate-hz 24000000` |
   | `--threshold` | 电压阈值 | 无 | `--threshold 1.5` |
   | `--sync` | 强制同步 set.ini | false | `--sync` |
   | `--rle` | 启用 RLE 压缩 | false | `--rle` |
   | `--output` | 输出路径 | 自动生成 | `--output out.atkdl` |

3. **TCP API 参考**（8 命令 JSON 格式）
   - `start_capture` / `stop_capture`
   - `get_progress` / `is_capturing`
   - `export` / `decode`
   - `get_info` / `ping`

4. **8 项已知问题及修复**
   - GUI 卡在 1% → graceful close
   - 临时标记清理
   - 内存标记恢复
   - set.ini 权限问题
   - ... (其他 4 项)

5. **采集失败恢复**（1% 卡死 graceful close）

6. **路径配置**（config.ini / set.ini / _config.py）

7. **ATK-Logic 快捷键**（F1/F2/Ctrl+S）

8. **PWM 分析输出说明**

9. **脚本清单**（12 文件 + 依赖图）

---

### P2-2: pdf-pin-extract SKILL.md 补全

1. **完整依赖列表 + 安装命令**
```bash
pip install camelot-py numpy pandas opencv-python-headless pypdfium2 pillow playa-pdf
```

2. **import camelot 失败修复过程**
   - 可编辑安装恢复（`pip install -e .`）
   - 权限问题排查

3. **3 阶段工作流**
   - 搜索（`--search` 关键词定位）
   - 提取（`extract` 解析表格）
   - 清洗（`clean_cell_*` 函数链）

4. **关键词搜索表**（中英文 × 表类型）
   | 表类型 | 中文关键词 | 英文关键词 |
   |--------|-----------|-----------|
   | Pin Assignment | 引脚分配, 引脚定义 | Pin Assignment, Pin Definition |
   | Multiplexing | 复用功能, 多路复用 | Alternate Functions, Multiplexing |

5. **数据清洗 artifacts 处理表**

6. **验证检查表及 exit codes**
   - Port 列完整性（exit 1）
   - MUX 列完整性（exit 2）
   - 交叉验证（exit 3）
   - 制品检查（exit 4）
   - 统计检查（exit 5）

7. **JSON 输出 schema**

8. **供应商说明**（MM32/STM32/GD32/AT32）

9. **Troubleshooting 表**（6 条目）

---

### P2-3: schmd-from-netlist SKILL.md 补全

1. **6 级命名优先级规则**（完整）
   - Level 1: Net Label
   - Level 2: Pin Name (source component)
   - Level 3: Signal Hint (JSON alias)
   - Level 4: Default Signal Name
   - Level 5: Net ID
   - Level 6: Fallback (NC)

2. **前置用户警告信息**
   - SCH-PCB 同步要求
   - NC 脚标注规范
   - 禁止多个 net label 连接同一 net

3. **Netlist 格式约定 + 示例**
   - Protel/DXP bracket 格式
   - 示例片段

4. **Source alias hint 规则**
   - `__shared_docs/<signal>.json` 匹配算法

5. **限制说明**（3 项）

---

### P2-4: keil-init SKILL.md 补全

1. **`eetool keil setup` 8 步管线逐步说明**
   - Step 1: 解析 `.uvprojx` (Device, Compiler, OutputName)
   - Step 2: 检测 vendor HAL 目录
   - Step 3: 检测 RTOS 目录
   - Step 4: 生成 `CLAUDE.md`
   - Step 5: 生成 pre-commit hook
   - Step 6: 写入 `settings.json`
   - Step 7: 安装 hook 到 `.git/hooks/`
   - Step 8: 验证（`--dry-run` 支持）

2. **受限区域 A/B 分类框架 + glob 模式**
   | 类型 | 说明 | Glob 示例 |
   |------|------|----------|
   | A 类 | 完全禁止修改 | `Device/**`, `Drivers/CMSIS/**` |
   | B 类 | 谨慎修改（需 review） | `Drivers/STM32F1xx_HAL_Driver/**` |

3. **生成文件的模板内容**
   - `CLAUDE.md` 模板（受限区域表 + 架构图 + 功能模块）
   - `pre-commit` hook 脚本
   - `settings.json` 模板（hook 配置 + permissions）

---

### P2-5: 其他 SKILL.md 小补全

1. **serial**: Troubleshooting 表（4 条目）
   - 端口占用
   - 权限问题
   - 波特率不匹配
   - 超时设置

2. **pin2json**: 
   - 输入识别规则（JLC Part ID vs KiCad symbol path）
   - JSON schema
   - JLC2KiCadLib 依赖

3. **keil-batch-gen**: 
   - Scatter file 删除警告
   - Build result 检测方法（扫描 `*.axf` 文件）

---

### P2-6: Install.ps1 Proxy DLL 部署逻辑细节

**说明**: 这部分已在 P1-4 中详细展开，无需单独章节。

---

### P2-7: Binary Dependencies 技术说明

在 SKILL.md 的 "ATK-Logic Capture" 章节中增加 "Binary Dependencies" 小节：

**内容**:
- `_bootstrap.py` 的作用：将 `lib/bin/` 加入 Windows DLL 搜索路径
- Python 3.8+ 的 DLL 加载策略变更（需要显式 `os.add_dll_directory()`）
- 为何需要 `libsigrokdecode-4.dll` 及其 11 个依赖 DLL
- DLL 依赖链示意图：
  ```
  lib_decoder.py
    → libsigrokdecode-4.dll
      → libglib-2.0-0.dll
        → libiconv-2.dll
        → libintl-8.dll
        → libpcre2-8-0.dll
      → libffi-8.dll
      → libirmp-0.dll
    → libstdc++-6.dll
    → libgcc_s_seh-1.dll
    → libwinpthread-1.dll
    → zlib1.dll
  ```
- 为何不能用 pip 安装：libsigrokdecode 无官方 Windows wheels

---

## P3 — 代码质量

### P3-1: 移除无用 import

**文件**: `src/eetool/capture/lib/lib_config_sync.py`

```python
# 移除这行（从未使用）
from .._config import get_gui_dir
```

---

### P3-2: sync_set_ini 参数顺序

**文件**: 同上

`duration_s` 插在中间打破 convention。当前所有调用者都用 keyword args，暂时无实际影响。如果将来重构，考虑移到 `set_ini_path` 之后。

**建议**: 暂不修改（破坏性变更风险 > 收益）。

---

### P3-3: 验证 decoders/ 目录完整性

**验证方法**:
```bash
diff -r \
  "C:/Users/yg/.claude/skills/__myskills/electro_bak/atk-logic-capture/scripts/runtime/decoders" \
  "E:/__work/BaseTools/eetool/src/eetool/capture/runtime/decoders"
```

**预期**: 应完全一致（仅 import 路径调整）。若有差异，需要同步。

---

### P3-4: .gitignore 文件保留

**说明**: 随 P0-3 修复自动完成（复制 `proxy_dll/` 目录时保留 `outdll/.gitignore`）。

---

## 执行计划

| 阶段 | 任务 | 估计工作量 | 状态 |
|------|------|-----------|------|
| **Session 2** | **P0-3**: 复制 `proxy_dll/` 到根目录 | 文件复制 | 🔴 最高优先级 |
| **Session 2** | P0-1, P0-2 (capture do_sync fix) | 20 行代码 | 🟡 代码修复 |
| **Session 2** | P3-1 (移除无用 import) | 1 行代码 | 🟢 快速修复 |
| **Session 3** | P1-1, P1-2 (serial 配置恢复) | ~80 行代码 | 🟡 功能恢复 |
| **Session 3** | P1-3 (pin2json stderr) | 5 行代码 | 🟢 快速修复 |
| **Session 4** | P1-4 (install.ps1 ATK 部署 + Proxy DLL 逻辑) | ~120 行 PS | 🟡 脚本开发 |
| **Session 4** | P1-5, P1-6, P1-7 (README 文档复制/整合) | 文档迁移 | 🟢 文档整理 |
| **Session 5** | P2-1 + P2-7 (atk-capture SKILL.md + Binary Deps) | 文档（长） | 🔵 文档编写 |
| **Session 6** | P2-2 (pdf-pin-extract SKILL.md) | 文档 | 🔵 文档编写 |
| **Session 7** | P2-3, P2-4 (schmd + keil-init SKILL.md) | 文档 | 🔵 文档编写 |
| **Session 8** | P2-5 (其他小补全) | 文档 | 🔵 文档编写 |
| **Session 8** | P3-3 (验证 decoders 一致性) | diff 命令 | 🟢 验证任务 |
| **Session 9** | 最终集成测试 + Proxy DLL 部署验证 | 测试 | 🔵 测试验证 |

**关键里程碑**: 
1. Session 2 完成 → P0 bug 全部修复，capture 基本可用
2. Session 4 完成 → 完整部署流程可用（install.ps1 + proxy DLL）
3. Session 8 完成 → 功能对齐完成，开始最终测试

---

## 总结

| 类别 | 总数 | 已修复 | 待修复 |
|------|------|--------|--------|
| P0 | 3 | 0 | 3 |
| P1 | 7 | 0 | 7 |
| P2 | 7 | 0 | 7 |
| P3 | 4 | 0 | 4 |
| **合计** | **21** | **0** | **21** |

**最严重遗漏**: 
- P0-3 (Proxy DLL) — 整个 C 源码/构建系统缺失
- P0-1/P0-2 (do_sync bug) — 用户每次使用都会触发

**评估方法改进建议**: 
使用 codebase-memory MCP 对比代码逻辑的同时，应结合 `find` + `diff` 对比目录结构，逐一检查非代码文件（README, 构建脚本, 配置文件, 二进制依赖）。
