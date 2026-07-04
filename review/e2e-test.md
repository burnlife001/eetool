# e2e-test.md — eetool 端到端测试清单

简单的手动测试流程，验证 eetool 各子系统基本可用。

---

## 前置条件

| 项目 | 说明 |
|------|------|
| Python 环境 | 已安装 `.venv` 且激活 |
| eetool 安装 | `pip install -e .` 完成 |
| 测试数据 | 准备示例文件（见各测试项） |
| 硬件（可选） | ATK-Logic、串口设备（仅测试对应功能时需要） |

---

## 测试流程

### Level 0 — 基础验证 (必测)

#### T0-1: 命令可用性
```bash
eetool --version
eetool --help
```
**预期**: 输出版本号 `0.1.0`，显示所有子命令列表。

---

#### T0-2: Doctor 诊断
```bash
eetool doctor
```
**预期**: 
- ✓ Python 版本 >= 3.10
- ✓ 11 个依赖包全部 OK
- ✓ 列出可用串口（可能为空）

**失败处理**: 若有依赖缺失，运行 `pip install -e .` 重新安装。

---

### Level 1 — 无硬件功能 (必测)

#### T1-1: Pin2json — LCSC Part ID 转 KiCad
```bash
# 准备: 选一个 LCSC Part ID (如 C2040)
eetool pin2json C2040 --output test_output.json
```
**预期**: 
- 生成 `test_output.json`
- JSON 包含 `symbol_name`, `pins` 数组
- 无错误输出

**失败标志**: 
- `JLC2KiCadLib failed` → 检查网络连接
- `ModuleNotFoundError` → 检查依赖安装

---

#### T1-2: Pin2json — KiCad Symbol 路径
```bash
# 准备: 一个 .kicad_sym 文件路径
eetool pin2json path/to/symbol.kicad_sym --output test_kicad.json
```
**预期**: 解析成功，生成 JSON。

---

#### T1-3: PDF Pin Extract — 搜索模式
```bash
# 准备: 一个 MCU 数据手册 PDF (如 STM32F103.pdf)
eetool pin extract-search your_datasheet.pdf
```
**预期**: 
- 输出找到的关键词位置
- 显示页码和匹配的表格标题

---

#### T1-4: PDF Pin Extract — 提取
```bash
# 假设搜索发现 Pin Assignment 在第 10 页
eetool pin extract your_datasheet.pdf --flavor lattice --package TSSOP20
```
**预期**: 
- 生成 `your_datasheet_pins.md`
- Markdown 包含 Pin Assignment 表格
- Markdown 包含 Multiplexing 表格（若有）

**跳过条件**: 若无合适 PDF，跳过此测试。

---

#### T1-5: Schmd-from-netlist — 单目标追踪
```bash
# 准备: 一个 Protel 格式 netlist 文件
eetool schmd-from-netlist your_netlist.txt U1.PA0
```
**预期**: 
- 输出 Markdown 格式的信号追踪路径
- 显示连接的元器件和引脚

**跳过条件**: 若无 netlist 文件，跳过。

---

#### T1-6: Keil — 生成构建脚本
```bash
# 准备: 一个 Keil 项目目录（含 .uvprojx）
cd path/to/keil_project
eetool keil gen-build
```
**预期**: 
- 生成 `__build.ps1`
- 脚本包含正确的 UV4 路径和项目名

**跳过条件**: 若无 Keil 项目，跳过。

---

### Level 2 — 需要硬件 (可选)

#### T2-1: Serial — 端口列举
```bash
eetool serial list
```
**预期**: 显示系统可用串口列表（或提示无可用端口）。

---

#### T2-2: Serial — 发送命令
```bash
# 准备: 连接一个串口设备到 COM7 (或你的端口)
eetool serial send --port COM7 --baudrate 115200 "AT\r\n"
```
**预期**: 
- 显示 `[INFO] Connected to COM7 @ 115200 baud`
- 显示设备响应（如 `OK`）

**跳过条件**: 无串口设备时跳过。

---

#### T2-3: Serial — 监听模式
```bash
eetool serial listen --port COM7 --baudrate 115200
```
**预期**: 
- 实时显示接收的数据
- Ctrl+C 退出

**跳过条件**: 无串口设备时跳过。

---

#### T2-4: Capture — Preflight 检查
```bash
# 准备: 安装 ATK-Logic GUI, 部署 Proxy DLL (见 install.ps1)
eetool capture preflight
```
**预期**: 
- 4 项检查全部 PASS:
  - ✓ GUI executable exists
  - ✓ Proxy DLL deployed
  - ✓ set.ini readable
  - ✓ TCP port available

**跳过条件**: 无 ATK-Logic 硬件时跳过。

---

#### T2-5: Capture — 采集测试
```bash
# 准备: ATK-Logic 连接信号源，GUI 已关闭
eetool capture start --ch 0,1 --duration 2s --output test_capture.atkdl
```
**预期**: 
- 显示 preflight 通过
- 显示采集进度 (0% → 100%)
- 生成 `test_capture.atkdl` 文件
- GUI 自动启动并保存

**失败标志**:
- `preflight failed` → 运行 T2-4 排查
- `卡在 1%` → 检查 GUI 是否被杀毒软件阻止

**跳过条件**: 无 ATK-Logic 硬件时跳过。

---

### Level 3 — 集成测试 (可选)

#### T3-1: Keil Setup — 完整项目初始化
```bash
cd path/to/keil_project
eetool keil setup --dry-run
```
**预期**: 
- 输出将要生成的文件列表
- 显示检测到的受限区域
- 不实际写入文件（`--dry-run`）

---

#### T3-2: Keil Setup — 实际部署
```bash
eetool keil setup
```
**预期**: 
- 生成 `.claude/CLAUDE.md`
- 生成 `.git/hooks/pre-commit`
- 生成 `.claude/settings.json`
- 显示部署成功消息

**验证**: 
```bash
cat .claude/CLAUDE.md  # 应包含受限区域表
```

---

## 测试结果记录

| 测试项 | 状态 | 备注 |
|--------|------|------|
| T0-1: 命令可用性 | ⬜ | |
| T0-2: Doctor 诊断 | ⬜ | |
| T1-1: Pin2json LCSC | ⬜ | |
| T1-2: Pin2json KiCad | ⬜ | |
| T1-3: PDF 搜索 | ⬜ | |
| T1-4: PDF 提取 | ⬜ | |
| T1-5: Netlist 追踪 | ⬜ | |
| T1-6: Keil 脚本生成 | ⬜ | |
| T2-1: Serial 列举 | ⬜ | |
| T2-2: Serial 发送 | ⬜ | 需硬件 |
| T2-3: Serial 监听 | ⬜ | 需硬件 |
| T2-4: Capture Preflight | ⬜ | 需硬件 |
| T2-5: Capture 采集 | ⬜ | 需硬件 |
| T3-1: Keil Setup 预览 | ⬜ | |
| T3-2: Keil Setup 部署 | ⬜ | |

**图例**: ⬜ 未测试 / ✅ 通过 / ❌ 失败 / ⏭️ 跳过

---

## 快速测试（最小集）

如果时间有限，只需执行以下 5 项核心测试：

```bash
# 1. 基础
eetool --version
eetool doctor

# 2. 无硬件功能验证（任选一个）
eetool pin2json C2040 --output test.json

# 3. 硬件功能验证（若有设备）
eetool serial list
eetool capture preflight  # 若有 ATK-Logic
```

**全部通过** = 基本功能正常。

---

## 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| `command not found: eetool` | 未安装或虚拟环境未激活 | `pip install -e .` 后重试 |
| Doctor 依赖检查失败 | 依赖包缺失 | `pip install -e .` 重新安装 |
| Pin2json 网络错误 | JLC API 连接失败 | 检查网络，重试 |
| Capture preflight 失败 | Proxy DLL 未部署 | 运行 `install.ps1` 或手动部署 |
| Serial 无端口 | 无串口设备连接 | 跳过 Serial 测试 |
| Keil 找不到 UV4 | 路径配置错误 | 检查 `_config.py` 或生成的脚本 |

---

## 测试完成标准

- **最低标准**: Level 0 + Level 1 全部通过
- **完整验证**: Level 0 + Level 1 + Level 2 (有硬件) 全部通过
- **上线标准**: Level 0~3 全部通过，无已知 P0/P1 bug

---

## 自动化建议（未来）

当前为手动测试，未来可考虑：
- Level 0~1 使用 `pytest` 自动化
- Level 2 使用 mock 对象模拟硬件
- CI/CD 集成 Level 0~1 测试

当前阶段：**手动执行即可，记录结果到上面的表格。**
