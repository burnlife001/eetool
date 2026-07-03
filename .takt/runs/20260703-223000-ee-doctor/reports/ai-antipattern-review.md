# AI Antipattern Review — ee doctor

## Conclusion
**No AI-specific issues**

## Key Findings
- ✅ 无 god class（每个 check 是独立小函数）
- ✅ 无重复代码（每个 check 独立）
- ✅ 无过度泛化（没有"YAGNI"future-proofing）
- ✅ 无 magic numbers（`PYTHON_MIN = (3, 10)` 是常量）
- ✅ 无 TODO/FIXME 占位
- ✅ 无 swallow error（`except PackageNotFoundError` 给出 fix，generic `except Exception` 有 WARN + fix）
- ✅ 无 mock-in-prod
- ✅ 无猜测实现（每个 check 都有明确的判断逻辑）

## Evidence
- `src/ee_toolkit/commands/doctor.py:39-52` — `_check_python` 简洁无冗余
- `src/ee_toolkit/commands/doctor.py:55-78` — `_check_dependencies` 三个分支清晰
- `src/ee_toolkit/commands/doctor.py:81-110` — `_check_serial_ports` 接受注入，易测试

## Risks / Caveats
- 无

## Recommended Next Step
- 合并