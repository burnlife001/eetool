# Coder Scope

## Task
新增 `ee doctor` 子命令（按 plan.md 执行）

## Files Modified
- `src/ee_toolkit/commands/doctor.py`（新增）
- `src/ee_toolkit/commands/__init__.py`（添加 export）
- `src/ee_toolkit/cli.py`（注册 subparser + dispatch）
- `tests/test_doctor.py`（新增）

## Change Type
- New feature (additive)
- No breaking changes
- Backward compatible: existing commands unaffected

## Lines Changed
- Added: ~150 lines (doctor.py) + ~50 lines (test) + 3 lines (cli.py) + 1 line (__init__.py)
- Removed: 0