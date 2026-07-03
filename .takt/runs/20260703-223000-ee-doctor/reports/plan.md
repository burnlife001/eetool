# Task Plan

## Original Request
新增 `ee doctor` 子命令：一个诊断子命令，检查 Python 版本、依赖、串口可用性，输出 pass/warn/fail 表格 + 修复建议。

## Analysis

### Objective
为 ee-toolkit 用户提供一个开箱即用的环境健康检查命令。当用户首次安装、迁移机器、或遇到"命令不工作"的问题时，运行 `ee doctor` 能快速定位问题（Python 版本过低、依赖缺失、串口权限不足等）并给出修复建议。

### Decomposed Requirements
| # | Requirement | Type | Notes |
|---|-------------|------|-------|
| 1 | CLI 注册 `ee doctor` 子命令 | Explicit | 需在 cli.py 注册新模块 |
| 2 | 检查 Python 版本 >= 3.10 | Explicit | 见 pyproject.toml `requires-python = ">=3.10"` |
| 3 | 检查运行时依赖（pyserial/pywin32/...） | Explicit | 对照 pyproject.toml dependencies |
| 4 | 列出可用串口 | Explicit | 使用 `serial.tools.list_ports` |
| 5 | 输出 pass/warn/fail 表格 | Explicit | 用 rich 或纯文本表格 |
| 6 | 每项失败时给修复建议 | Explicit | 例如 `pip install pyserial` |
| 7 | 退出码反映严重程度 | Implicit | 全部 pass → 0；任意 fail → 非 0 |

### Scope
- 新增文件:
  - `src/ee_toolkit/commands/doctor.py`（主命令实现）
  - `tests/test_doctor.py`（单元测试，mock 硬件）
- 修改文件:
  - `src/ee_toolkit/commands/__init__.py`（导出 `doctor` 模块）
  - `src/ee_toolkit/cli.py`（注册 subparser + 加入 dispatch dict）

### Approaches Considered
| Approach | Adopted? | Rationale |
|----------|----------|-----------|
| 单文件实现 | ✅ Yes | 命令逻辑简单（4 个 check），无需拆模块；保持与 `pin_extract.py` 一致 |
| 拆分为 `core/doctor/checks/*.py` | No | 过度拆分；200 行单文件足够 |
| 使用 Click 装饰器 | No | 项目统一使用 argparse（见 cli.py） |
| 使用 rich 输出彩色表格 | No | 增加第三方依赖；纯文本表格即可 |

### Implementation Approach
1. **新建 `src/ee_toolkit/commands/doctor.py`**：
   - `add_subparser(subparsers)`：注册 `ee doctor` 子命令
   - `_check_python() -> CheckResult`：检查 `sys.version_info`
   - `_check_dependencies() -> list[CheckResult]`：对照 pyproject.toml 动态读取（`importlib.metadata.version`）+ 静态 fallback（硬编码列表）
   - `_check_serial_ports() -> list[CheckResult]`：调用 `serial.tools.list_ports.comports()`
   - `run(parsed) -> int`：聚合结果，打印表格，返回 exit code
   - 复用 `src/ee_toolkit/commands/serial.py` 中已有的 `serial.tools` 导入模式
2. **修改 `src/ee_toolkit/commands/__init__.py`**：添加 `from . import doctor`
3. **修改 `src/ee_toolkit/cli.py`**：在 `build_parser()` 调用 `doctor.add_subparser`；在 `command_dispatch` 添加 `"doctor": doctor.run`
4. **新建 `tests/test_doctor.py`**：mock `serial.tools.list_ports`，覆盖每个 check 的 pass/warn/fail 分支

### Reachability and Launch Conditions
| Item | Content |
|------|---------|
| User entry point | `ee doctor`（无 subcommand） |
| Callers/wiring to update | `cli.py` 的 `build_parser` 和 `command_dispatch` |
| Launch conditions | 无认证/权限限制 |
| Remaining gaps | none |

## Implementation Guidelines

- **参考现有命令实现**：`src/ee_toolkit/commands/serial.py:1-30` 展示了 argparse subparser 注册 + `run(parsed)` 入口模式
- **依赖检查策略**：优先用 `importlib.metadata.version(name)` 动态检测；失败时降级到硬编码 fallback 列表（参考 pyproject.toml dependencies）
- **串口检查**：直接调用 `serial.tools.list_ports.comports()`，无需 try/except 包整个函数（失败也算 fail 信号）
- **输出格式**：`{STATUS:>7}  {name:30s}  {detail}` 每行一条，最后打印 summary
- **退出码**：0 = 全部 pass 或仅有 warn；1 = 任意 fail
- **行数控制**：单文件 ≤ 200 行

## Out of Scope
| Item | Reason for exclusion |
|------|---------------------|
| 自动修复（如 `pip install pyserial`） | 仅诊断，避免副作用；修复建议以文本形式给出 |
| 串口写权限深度检查（需要打开设备） | 风险高；仅列出可用端口 |
| 网络/USB 设备检查 | 超出"诊断基础环境"范围 |

## Open Questions
- 无（任务边界清晰）