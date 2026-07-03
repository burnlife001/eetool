# Coder Decisions

## Decision 1: 单文件 vs 模块拆分
**Chose:** 单文件 `doctor.py`

**Rationale:** 4 个 check 加 1 个聚合函数，总计 < 200 行，符合项目其他命令（`pin_extract.py` 等）的简洁风格。过早拆分会引入不必要的目录结构。

## Decision 2: 依赖列表来源
**Chose:** 硬编码在 doctor.py 中 + 注释说明来源

**Rationale:** `importlib.metadata` 在 editable install 下行为不稳定，且用户可能用 `pip install -e .` 或系统包安装。硬编码列表与 pyproject.toml 保持一致即可，注释里说明来源以备 review。

## Decision 3: 输出格式
**Chose:** 纯文本表格（无 rich）

**Rationale:** 不增加依赖；表格 3 列用对齐即可读；与现有命令的 `print` 风格一致。

## Decision 4: 退出码
**Chose:** 0 = 全 pass 或仅 warn；1 = 任意 fail

**Rationale:** 与 pytest 等工具的"软失败 vs 硬失败"语义对齐；CI 可用 `ee doctor` 作为前置 gate。

## Decision 5: 测试覆盖
**Chose:** mock `serial.tools.list_ports.comports`，覆盖每 check 的 pass/warn/fail 三分支

**Rationale:** 项目硬性约束（见 CLAUDE.md "Hardware-dependent commands must be mockable or skipped in CI"）。