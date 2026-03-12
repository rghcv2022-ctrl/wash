# zht C 盘深度清理大师

一个基于 Python 标准库实现的 Windows 磁盘清理工具，提供：

- 命令行清理入口：`wash.py`
- 图形界面入口：`sdu.py`
- 统一核心逻辑包：`zht_cleaner/`

项目当前只面向 Windows 使用，部分功能需要管理员权限。

## 项目结构

```text
wash/
├─ zht_cleaner/        # 核心包
│  ├─ config.py        # 配置、清理分类、系统工具定义
│  ├─ core.py          # 共享业务逻辑
│  ├─ cli.py           # 命令行程序
│  └─ gui.py           # Tkinter 图形界面
├─ wash.py             # CLI 兼容入口
├─ sdu.py              # GUI 兼容入口
├─ sdu.spec            # PyInstaller 打包配置
└─ pyproject.toml      # 项目元数据
```

## 功能概览

- 一键清理系统临时文件、Windows 更新缓存、浏览器缓存、崩溃转储
- 清理开发者缓存，例如 Pip、Conda、VS Code、Gradle
- 扫描系统盘大文件，并在 GUI 中直接删除选中文件
- 调用 Windows 原生命令执行系统级清理：
  - `DISM`
  - `powercfg`
  - `cleanmgr`
  - `compact.exe`

## 运行方式

### 1. 图形界面

```powershell
python sdu.py
```

### 2. 命令行

默认执行全量清理：

```powershell
python wash.py
```

列出可用分类和系统工具：

```powershell
python wash.py list
```

仅清理指定分类：

```powershell
python wash.py clean --category "系统临时文件" --category "浏览器缓存"
```

扫描系统盘中大于 1024 MB 的文件：

```powershell
python wash.py scan --threshold 1024 --limit 20
```

调用系统工具：

```powershell
python wash.py tool dism
python wash.py tool cleanmgr
```

## 打包

使用 PyInstaller：

```powershell
pyinstaller sdu.spec
```

打包入口为 `sdu.py`，默认生成 GUI 程序。

## 开发说明

- 代码已按“配置 / 核心逻辑 / CLI / GUI”分层
- `wash.py` 与 `sdu.py` 只保留兼容入口，避免逻辑重复
- 项目依赖仅使用 Python 标准库

## 注意事项

- 请在 Windows 环境运行
- 系统级清理和系统工具建议使用管理员权限
- 删除大文件前请确认文件用途，避免误删重要数据
