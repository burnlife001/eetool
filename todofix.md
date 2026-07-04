# todofix.md — ee-toolkit 修复计划

基于 `diff.md` 的完整差异分析。

## 优先级分类

- **P0 — 阻塞性 bug**：用户操作导致错误或数据损坏
- **P1 — 功能回归**：原始技能有的功能在新 CLI 中不可用
- **P2 — 文档补全**：SKILL.md / install.ps1 缺少关键信息
- **P3 — 代码质量**：无用代码、边界情况

---

## P0 — 阻塞性 Bug

### P0-1: do_sync 不传 --duration 时误改 setTime

**文件**: `src/ee_toolkit/capture/atk_cli.py` cmd_capture (~L556-579)

**复现**:
```
ee capture start --ch 0,1,2,3
# 输出: [sync] differences: {'setTime_ms': 3000}  ← set.ini 被改写了
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

**预期效果**: 不传 `--duration` 时 set.ini.setTime 不被修改，与原版行为一致；传 `--duration 5s` 时写 setTime 解决 stale 问题。

### P0-2: do_sync 非默认 --duration 触发 GUI 重启

**文件**: 同上

**复现**:
```
ee capture start --duration 10s
# 即使不加 --sync，也会写入 set.ini + 可能重启 GUI
```

**修复**: 上述 P0-1 修复会同时解决这个问题 — `explicit_duration` 只标记用户"显式"传了 duration。GUI 重启只在 `do_sync=True` 且 set.ini 有 diff 时才发生。用户传 `--duration 10s` 期望行为：
- 改 set.ini.setTime（commit 939ad34 的意图 — 这是合理的新功能）
- 重启 GUI（只在 set.ini 真的变更时 — 这也合理）
- 区别是：只有用户显式传值才触发，默认值不触发（P0-1 修复）

**如果用户觉得 "改 duration 就重启 GUI 太慢"**，可以考虑只通过 TCP 传 duration_s 给 GUI 而不写 set.ini，但 commit 939ad34 的理由是 "GUI 用 setTime 作为采集定时器"，所以写 set.ini 是正确的。

---

## P1 — 功能回归

### P1-1: Serial 恢复配置持久化

**文件**: `src/ee_toolkit/commands/serial.py`

**问题**: 原始 `serial_monitor.py` 通过 `serial_monitor.ini` 持久化 port/baud/bytesize/parity/stopbits/hex/timeout。新版完全丢失。

**修复**:
1. 在 `send_command()` 和 `listen_port()` 结束后保存当前配置
2. 下次启动时自动恢复（函数开头读取 INI 作为默认值）
3. INI 路径：`~/.local/share/ee-toolkit/serial.ini`（用 `platformdirs` 或 `os.path.expanduser`）

### P1-2: Serial 恢复 bytesize/parity/stopbits 配置

**文件**: `commands/serial.py` `add_subparser()` + `_open_serial()`

**问题**: 硬编码 8N1，原始支持 5-8 数据位、N/E/O/M/S 校验、1-2 停止位。

**修复**:
1. 在 `serial listen` 和 `serial send` 子命令中增加 `--bytesize`, `--parity`, `--stopbits` 参数
2. 修改 `_open_serial()` 接受这些参数，传递为 `serial.BYTESIZES[x]`, `serial.PARITIES[y]`, `serial.STOPBITS[z]`
3. 修复连接提示信息恢复帧格式显示

### P1-3: Pin2json 恢复错误 stderr

**文件**: `src/ee_toolkit/commands/pin2json.py` `_generate_symbol()`

**问题**: `CalledProcessError` 未被包装为 `RuntimeError`，stderr 丢失。

**修复**:
```python
try:
    subprocess.run([exe, ...], check=True, capture_output=True, text=True)
except subprocess.CalledProcessError as e:
    raise RuntimeError(
        f"JLC2KiCadLib failed to generate symbol for {part_id}:\n{e.stderr.strip()}"
    ) from e
```

### P1-4: Install.ps1 补全 ATK-Logic 部署步骤

**文件**: `install.ps1`

**问题**: 缺少 ATK-Logic GUI 检测、proxy DLL 部署、config 路径更新、uiautomation 安装、preflight 验证。

**修复**: 在现有 Python 包安装流程后增加一个新 section：

1. **ATK-Logic GUI 检测**: 搜索标准路径列表，提示未找到时的手动步骤
2. **Proxy DLL 部署**: 备份原始 DLL → 安装代理 DLL
3. **_config.py 路径**: 检测 GUI_DIR 是否需要更新
4. **pip install uiautomation**: `./.venv/bin/pip install uiautomation`
5. **Preflight 验证**: `./.venv/bin/python -m ee_toolkit.capture.capture.atk_preflight --fix --json`

参考原始: `C:/Users/yg/.claude/skills/__myskills/electro_bak/atk-logic-capture/install.ps1`

---

## P2 — 文档补全 (SKILL.md)

所有文档补到根目录 `SKILL.md` 中。

### P2-1: atk-logic-capture SKILL.md 补全

**优先级顺序**:
1. 采集工作流（agent 行为规则: 默认采集不确认、preflight 自动检测、save flow、isCtrlSPressed）
2. 采集参数表
3. TCP API 参考（8 命令 JSON 格式）
4. 8 项已知问题及修复
5. 采集失败恢复（1% 卡死 graceful close）
6. 路径配置（config.ini / set.ini / _config.py）
7. ATK-Logic 快捷键
8. PWM 分析输出说明
9. 脚本清单

### P2-2: pdf-pin-extract SKILL.md 补全

1. 完整依赖列表 + 安装命令
2. import camelot 失败修复过程
3. 3 阶段工作流（搜索→提取→清洗）
4. 关键词搜索表（中英文 × 表类型）
5. 数据清洗 artifacts 处理表
6. 验证检查表及 exit codes
7. JSON 输出 schema
8. 供应商说明（MM32/STM32/GD32/AT32）
9. Troubleshooting 表

### P2-3: schmd-from-netlist SKILL.md 补全

1. 6 级命名优先级规则（完整）
2. 前置用户警告信息
3. Netlist 格式约定 + 示例
4. Source alias hint 规则
5. 限制说明

### P2-4: keil-init SKILL.md 补全

1. `ee keil setup` 8 步管线逐步说明
2. 受限区域 A/B 分类框架 + glob 模式
3. 生成文件的模板内容（CLAUDE.md, pre-commit, settings.json）

### P2-5: 其他 SKILL.md 小补全

1. **serial**: Troubleshooting 表
2. **pin2json**: 输入识别规则、JSON schema、JLC2KiCadLib 依赖
3. **keil-batch-gen**: Scatter file 警告

---

## P3 — 代码质量

### P3-1: 移除无用 import

**文件**: `src/ee_toolkit/capture/lib/lib_config_sync.py`

```python
from .._config import get_gui_dir  # ← 移除（从未使用）
```

### P3-2: sync_set_ini 参数顺序

**文件**: 同上

`duration_s` 插在中间打破 convention。当前所有调用者都用 keyword args，暂时无实际影响。如果将来重构，考虑移到 `set_ini_path` 之后。

---

## 执行计划

| 阶段 | 任务 | 估计工作量 |
|------|------|-----------|
| Session 2 | P0-1, P0-2 (capture do_sync fix) | 20 行代码 |
| Session 2 | P3-1 (移除无用 import) | 1 行代码 |
| Session 3 | P1-1, P1-2 (serial 配置恢复) | ~80 行代码 |
| Session 3 | P1-3 (pin2json stderr) | 5 行代码 |
| Session 4 | P1-4 (install.ps1 ATK 部署) | ~60 行 PS |
| Session 5 | P2-1 (atk-capture SKILL.md) | 文档（长） |
| Session 6 | P2-2 (pdf-pin-extract SKILL.md) | 文档 |
| Session 7 | P2-3 (schmd SKILL.md) | 文档 |
| Session 7 | P2-4 (keil-init SKILL.md) | 文档 |
| Session 8 | P2-5 (其他小补全) | 文档 |
| Session 8 | 最终集成测试 | 测试 |

**先修代码 bug (P0+P1)，再补文档 (P2+P3)。** 代码 bug 是用户每次使用都会碰到的，文档缺失是查阅时才需要的。
