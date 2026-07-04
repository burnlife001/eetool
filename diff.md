# diff.md — ee-toolkit vs electro_bak 差异报告

调研日期: 2026-07-04

## 调研范围

- **Project A (原始)**: `C:/Users/yg/.claude/skills/__myskills/electro_bak/`
- **Project B (新)**: `E:/__work/BaseTools/ee-toolkit/src/ee_toolkit/`
- **方法**: codebase-memory MCP 逐文件对比代码 + Read tool 对比文档

---

## 1. Capture 子系统 (atk-logic-capture)

### 1.1 Bug: do_sync 把 setTime 改写成默认值

**文件**: `capture/atk_cli.py` cmd_capture (~L556)

**问题**:
- 用户传 `--ch 0,1,2,3` 不传 `--duration` → `do_sync` 触发（因为 `explicit_ch=True`）
- 进入 sync 路径后 `duration_s=3.0`（默认值 3s）被无条件传入 `sync_set_ini(..., duration_s=duration_s)`
- 若 set.ini 里的 `setTime` 是 50000ms，diff 检测到 `setTime_ms: 3000 ≠ 50000`，改写了 set.ini
- 导致 GUI 重启进而 post-restart preflight 失败

**原始行为**: `sync_set_ini` 根本没有 `duration_s` 参数，set.ini.setTime 从来不被 CLI 修改

详见 commit `939ad34`（fix(capture): push --duration into set.ini settingData.setTime）

### 1.2 Bug: do_sync 触发条件引入 `args.duration != "3s"`

**文件**: `capture/atk_cli.py` cmd_capture (~L569)

**问题**: 任何非默认 `--duration` 即使不加 `--sync`，也会触发完整的 set.ini 同步 + GUI 重启流程。原始版本 duration 只通过 TCP 协议发送给 GUI，不碰 set.ini。

### 1.3 潜在风险: sync_set_ini 签名 positional arg 移位

**文件**: `capture/lib/lib_config_sync.py` (~L266)

**问题**: `duration_s` 插在 `threshold` 和 `set_ini_path` 之间。若有代码用 positional args 调用 `sync_set_ini`，第4个参数会从 `set_ini_path` 变成 `duration_s`。当前所有调用者都用 keyword args，但这是隐患。

### 1.4 无用 import

**文件**: `capture/lib/lib_config_sync.py`

`from .._config import get_gui_dir` 导入了但从未使用。

### 1.5 其他文件: 无功能差异

以下文件逻辑与原版完全一致（仅 import 路径从绝对改为相对）:
- `lib/lib_reader.py` (CaptureReader, AtkdlReader, BinReader, EdgeEvent)
- `lib/lib_proto.py` (UartDecoder, I2CDecoder, SpiDecoder)
- `lib/lib_decoder.py` (DecoderBridge, ctypes 结构体)
- `capture/atk_preflight.py` (所有检查逻辑，preflight 未使用 duration_s 参数)
- `capture/uia_save.py` (UIA Save As 自动化)
- `_config.py` (路径配置，SCRIPTS_DIR 改为绝对路径指向新项目)
- `_bootstrap.py` (DLL 路径注入)
- `config.ini` (DATA_DIR / GUI_DIR 一致)
- `analyze/atk_classify.py`, `analyze/atk_pwm.py` (分析工具)

---

## 2. Serial 子系统

### 2.1 回归: INI 配置持久化被移除

**原始**: `serial_monitor.py` 读写 `serial_monitor.ini`，保存 port/baud/bytesize/parity/stopbits/hex/timeout。
**新**: 无任何配置持久化。用户偏好丢失。

### 2.2 回归: 串口参数硬编码为 8N1

**文件**: `commands/serial.py` `_open_serial()`

**原始**: 支持 `--bytesize` (5-8), `--parity` (N/E/O/M/S), `--stopbits` (1-2)。
**新**: 硬编码 `serial.EIGHTBITS`, `serial.PARITY_NONE`, `serial.STOPBITS_ONE`，无 CLI 参数可配。

### 2.3 次要: 连接信息简化

**原始**: `[INFO] Connected to {port} @ {baud} baud ({bytesize}{parity}{stopbits})`
**新**: `[INFO] Connected to {port} @ {baudrate} baud` — 丢失帧格式显示。

### 2.4 改善: ProcessLock 跨进程安全

`serial.py` 新增 `ProcessLock(f"serial-{port}")` 包装 `send_command()` 和 `listen_port()`。原始无锁。

---

## 3. Keil 子系统

### 3.1 重大改善: 8 步手动流程 → 自动化

**原始 keil-init**: 人工阅读 SKILL.md 中的 8 步指南，手动执行每一步。
**新 `ee keil setup`**: `setup_project()` 自动完成全部步骤：
- 解析 `.uvprojx` XML 提取 Device/pCCUsed/OutputName
- 检测 vendor HAL 目录 (`Device/`, `Drivers/`, `Library/`, `Middleware/`)
- 检测 RTOS 目录 (FreeRTOS, RT-Thread, QP, CMSIS)
- 生成 `.claude/CLAUDE.md`（含受限区域表 + 编译/烧录命令）
- 生成 pre-commit hook（自动构建受限区域 regex）
- 写入 `.claude/settings.json`（hook 配置 + permissions）
- 安装 hook 到 `.git/hooks/pre-commit`
- 支持 `--dry-run` 预览
- 支持 `--framework FreeRTOS` 声明额外受限区域

### 3.2 改善: 按需生成单个模板

**新**: `gen-build`, `gen-flash`, `gen-build-flash` 子命令可按需生成单个 `.ps1`。
**原始**: 三个模板总是同时生成。

### 3.3 一致: PowerShell 模板内容

`__build.ps1`, `__download.ps1`, `__build_and_download.ps1` 三个模板与原始内容**完全一致**（仅占位符 `{{UV4_PATH}}`, `{{PROJECT_NAME}}`, `{{OUTPUT_NAME}}` 相同）。

### 3.4 次要: UV4.png 引用移除

原始 SKILL.md 关联 UV4 图标，新版本未处理（不影响功能）。

---

## 4. Pin2json 子系统

### 4.1 回归: 错误信息丢失 stderr

**文件**: `commands/pin2json.py` `_generate_symbol()`

**原始**: 
```python
try:
    subprocess.run(..., check=True)
except subprocess.CalledProcessError as e:
    raise RuntimeError(f"JLC2KiCadLib failed...\n{e.stderr}") from e
```

**新**: `subprocess.run(check=True)` 无内层 try/except，外层 `except Exception` 捕获后只拿到 `CalledProcessError` 对象字符串表示，**不包含 stderr**。

### 4.2 CLI 参数变更

**原始**: 输出文件是位置参数 `python pin2json.py input [output.json]`
**新**: 输出用 `--output`/`-o` 标志 `ee pin2json input --output out.json`

### 4.3 改善: KiCad 解析器提取为独立模块

`parse_kicad_sym()` 移到 `core/kicad_parser.py`，增加类型提示、预编译正则、`_pin_sort_key()` helper、`_ANGLE_TO_DIRECTION` 常量表。`parse_symbol()` 为新规范名，`parse_kicad_sym()` 为兼容别名。

---

## 5. PDF Pin Extract 子系统

### 5.1 一致: 所有逻辑完全保留

提取逻辑（`search_pages`, `detect_ports`, `detect_mux_cols`, `extract_pin_assignment`, `extract_multiplexing`, `build_json`, `write_package_markdown`, 所有 `clean_cell_*`）**逐行一致**。

验证逻辑（`check_file`, `check_pin_table`, `check_mux_tables`, `check_cross_validation`, `check_artifacts`, `check_stats`）**逐行一致**。

### 5.2 CLI 参数变更

**原始**: 两个独立脚本
- `python extract_tables.py DS.pdf [--search] [--flavor lattice] [--package TSSOP20]`
- `python verify_output.py file.md [--ports ...] [--mux-cols ...]`

**新**: 统一子命令
- `ee pin extract DS.pdf [--flavor lattice] [--package TSSOP20]`
- `ee pin extract-search DS.pdf`
- `ee pin extract-verify file.md [--ports ...] [--mux-cols ...]`

---

## 6. Schmd-from-Netlist 子系统

### 6.1 一致: 所有逻辑完全保留

信号映射逻辑和拓扑推断逻辑全部保留，中文字符串输出全部保留，`maxhop=4` 默认值一致。

### 6.2 改善: 代码组织

- `parse_netlist()` 提取到 `core/netlist_parser.py`（预编译正则，type hints，`Path.read_text()`）
- `_resolve_netlist()`, `_load_context()`, `_pick_target()` 消除两个脚本间的重复代码
- `sys.path.insert(0, ...)` 改为正规 package import

---

## 7. CLI 入口 + Doctor

### 7.1 新功能: 统一入口

`cli.py` 提供 `ee` 命令，按子命令派发 `ee serial`, `ee pin2json`, `ee pin`, `ee schmd-from-netlist`, `ee keil`, `ee capture`, `ee doctor`。

### 7.2 新功能: doctor 诊断

`ee doctor` 检查 Python 版本，验证 11 个依赖项安装，列举可用串口。无原始对应功能。

### 7.3 新功能: 版本跟踪

`ee --version` → `0.1.0`

### 7.4 Capture 包装层

`commands/capture.py` 提供子命令验证 + `ProcessLock`，通过 `subprocess.call()` 委派给底层 `atk_cli`/`atk_preflight`/`atk_classify`/`atk_pwm`。

---

## 8. Hardware Diff

### 8.1 完全保留

Root `SKILL.md` 中的 Hardware Diff SOP 段落为原始 `hardware-diff-by-codes/SKILL.md` 的逐字复制，Step 0-8、全部表格、9条关键规则均完整。

### 8.2 无 CLI 实现

原始也是纯 SOP（无代码），新版本同样无 CLI，符合设计意图。

---

## 9. 文档 (SKILL.md)

### 9.1 atk-logic-capture SKILL.md — 严重缺失

原始 SKILL.md 的以下内容在合并后的 SKILL.md 中**全部缺失**:

| 缺失内容 | 重要性 |
|----------|--------|
| 完整采集工作流（agent 行为、preflight 自动检测、save flow、isCtrlSPressed） | 严重 |
| 采集失败恢复过程（卡在 1%、graceful close、临时/内存标记清理） | 严重 |
| 采集参数表（--ch, --duration, --sample-rate-hz, --threshold, --sync, --rle, --output） | 高 |
| 路径配置说明（config.ini / _config.py / getter 函数） | 高 |
| ATK-Logic 官方快捷键参考（F1/F2/Ctrl+S） | 中 |
| TCP API 参考（8 个命令的 JSON request/response 格式） | 高 |
| Config 参考（set.ini 位置、config.ini 用途、快捷方式、崩溃恢复标记） | 高 |
| 8 项已知问题及解决方案 | 严重 |
| 12 文件脚本清单及依赖图 | 中 |
| PWM 分析输出说明 | 中 |

### 9.2 pdf-pin-extract SKILL.md — 严重缺失

| 缺失内容 | 重要性 |
|----------|--------|
| 完整依赖列表（camelot-py, numpy, pandas, opencv-python-headless, pypdfium2, pillow, playa-pdf） | 严重 |
| 可编辑安装恢复过程（import camelot 失败但 pip list 有的修复） | 高 |
| 3 阶段工作流（搜索→提取→清洗） | 高 |
| 关键词搜索表（中英文关键词 × 表类型） | 高 |
| 数据清洗代码和制品处理表 | 高 |
| 验证检查表及 exit codes | 高 |
| 自动检测覆盖场景表 | 高 |
| JSON 输出 schema | 高 |
| 供应商特定说明（MM32/STM32/GD32/AT32） | 高 |
| Troubleshooting 表（6 条目） | 高 |

### 9.3 schmd-from-netlist SKILL.md — 高严重缺失

| 缺失内容 | 重要性 |
|----------|--------|
| 前置用户警告信息（SCH-PCB 同步、NC 脚标注、禁止多个 net label 连接） | 高 |
| Netlist 格式约定（Protel/DXP bracket 格式 + 示例） | 高 |
| 6 级命名优先级规则 | 严重 |
| Source alias hint 规则 | 高 |
| JSON 依赖原理说明 | 中 |
| __shared_docs 匹配算法 | 中 |
| 源码自动扫描说明 | 中 |
| 限制说明（3 项） | 高 |

### 9.4 keil-init SKILL.md — 高严重缺失

| 缺失内容 | 重要性 |
|----------|--------|
| 完整 8 步过程的逐步说明 | 严重 |
| 受限区域 A/B 分类框架 + glob 模式 | 严重 |
| CLAUDE.md 完整模板（受限区域表 + 架构图 + 功能模块 + 关键定义 + 内存说明） | 严重 |
| Pre-commit hook 完整脚本 + RESTRICTED regex 构建指南 | 严重 |
| Settings.json 模板（hook 配置 + permissions） | 高 |
| 测试验证过程（受限区域阻塞测试 + 允许区域通过测试） | 中 |

### 9.5 其他 SKILL.md 缺失

| 子系统 | 缺失内容 | 重要性 |
|--------|----------|--------|
| serial | Troubleshooting 表（4 条目） | 低 |
| pin2json | 输入识别规则、JSON schema、JLC2KiCadLib 依赖 | 中 |
| keil-batch-gen | Scatter file 删除警告、build result 检测方法 | 中 |

### 9.6 Hardware diff — 完整保留

无缺失。

---

## 10. Install 脚本

### 10.1 install.ps1 — 功能不足

| 功能 | 原始 atk-logic-capture/install.ps1 | 新 install.ps1 |
|------|-----------------------------------|----------------|
| 虚拟环境创建 | 无 | 有（.venv + pip install -e） |
| ee.exe symlink | 无 | 有 |
| PATH 添加 | 无 | 有 |
| Skill junction | 无 | 有 |
| ATK-Logic GUI 检测 | 有（8+ 标准路径） | **缺失** |
| Proxy DLL 部署 | 有（backup + install） | **缺失** |
| _config.py 路径更新 | 有 | **缺失** |
| uiautomation 安装 | 有 | **缺失** |
| Preflight 验证 | 有 | **缺失** |

新 install.ps1 安装 Python 包本身没有问题，但缺少 ATK-Logic 硬件相关的部署步骤。

---

## 11. 总体评估

### 代码层面

| 子系统 | 状态 | 问题数 |
|--------|------|--------|
| Capture (atk_cli.py) | **有bug** | 2 |
| Capture (其他模块) | 一致 | 0 |
| Capture (lib_config_sync) | 小问题 | 2 |
| Serial | 功能退化 | 2 |
| Keil | 改善 | 0 |
| Pin2json | 小退化 | 1 |
| PDF Pin Extract | 一致 | 0 |
| Schmd from Netlist | 改善 | 0 |
| CLI Entry + Doctor | 新功能 | 0 |
| Hardware Diff | N/A (纯文档) | 0 |

### 文档层面

| 子系统 | 状态 |
|--------|------|
| atk-logic-capture SKILL.md | 严重缺失 |
| pdf-pin-extract SKILL.md | 严重缺失 |
| schmd-from-netlist SKILL.md | 严重缺失 |
| keil-init SKILL.md | 严重缺失 |
| serial SKILL.md | 轻度缺失 |
| pin2json SKILL.md | 轻度缺失 |
| keil-batch-gen SKILL.md | 轻度缺失 |
| hardware-diff SKILL.md | **完整保留** |
| install.ps1 | 缺失 ATK 部署步骤 |
