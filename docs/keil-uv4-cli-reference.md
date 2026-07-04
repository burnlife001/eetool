以下是将 Keil µVision 命令行参数整理后的中文 Markdown 列表：

---

### **命令（Commands）**

| 参数 | 说明 | 示例 |
| :--- | :--- | :--- |
| `-b` | 构建项目的最后一个当前目标，构建完成后退出。若为多项目，则构建“项目 - 批量构建”对话框中定义的目标。 | `UV4 -b PROJECT1.uvprojx` |
| `-c` | 清理项目的所有目标。若为多项目，则清理在“项目 - 批量构建”中已选定的全部目标。 | `UV4 -c PROJECT1.uvprojx` |
| `-cr` | 清理所有项目目标，并重新编译（re-translate）最后一个当前目标，完成后退出。 | `UV4 -cr PROJECT1.uvprojx` |
| `-d` | 以调试模式启动 µVision。可与调试初始化文件配合使用，执行自动化测试流程。 | `UV4 -d PROJECT1.uvprojx` |
| `-f` | 将程序下载到 Flash，下载完成后退出。 | `UV4 -f PROJECT1.uvprojx -t"MCB2100 Board"` |
| `-r` | 重新编译最后一个当前项目目标，完成后退出。若为多项目，则按“项目 - 批量构建”定义重新编译。 | `UV4 -r PROJECT1.uvprojx -t"Simulator"` |

### **选项（Options）**

| 参数 | 说明 | 示例 |
| :--- | :--- | :--- |
| `-j0` | 隐藏 µVision 图形界面，并抑制消息输出。用于批处理测试。 | — |
| `-i <文件.xml>` | 使用符合 `project_import.xsd` 架构的 XML 文件创建新项目或更新现有项目。自动抑制 GUI。 | `UV4 MyProject.uvprojx –i MyImport.xml` |
| `-n <器件名>` | 使用指定的器件名称创建新项目。自动抑制 GUI。 | `UV4 MyProject.uvprojx –n Device1234` |
| `-t <目标名>` | 将指定目标设为当前目标。若未指定，则使用上次已知的目标。 | `UV4 -r PROJECT1.uvprojx -t"MCB2100 Board"` |
| `-o <输出文件>` | 指定输出日志文件。 | `UV4 -r PROJECT1.uvprojx -o"listmake.prn"` |
| `-q` | 重新构建多项目中的**选定目标**。需确保每个目标使用不同的对象输出文件夹。 | `UV4 -r "C:\MyProjects\ARM\Example-mpw.uvmpwx" -q` |
| `-z` | 重新构建项目或多项目中的**所有目标**。需确保每个目标使用不同的对象输出文件夹。 | `UV4 -b PROJECT1.uvproj -z` |
| `-x` | 启用 DDE 模式，并返回**完整命令输出**。仅可与 `-d` 命令配合使用。 | — |
| `-y` | 启用 DDE 模式，并**仅返回命令确认**。仅可与 `-d` 命令配合使用。 | — |

### **构建返回码（ERRORLEVEL）**

| 代码 | 说明 |
| :--- | :--- |
| `0` | 无错误或警告 |
| `1` | 仅有警告 |
| `2` | 存在错误 |
| `3` | 存在致命错误 |
| `11` | 无法以写入模式打开项目文件 |
| `12` | 数据库中未找到指定名称的器件 |
| `13` | 写入项目文件时出错 |
| `15` | 读取导入 XML 文件时出错 |

### **基本语法格式**

```
UV4 [command] [projectfile] [options]
```

- **command**：上表中的命令参数，若省略则进入交互式构建模式。
- **projectfile**：项目文件（`.uvproj` / `.uvprojx`）或多项目文件（`.uvmpw` / `.uvmpwx`），若省略则打开上次使用的项目。
- **options**：附加参数，用于指定目标名称、输出文件等。
