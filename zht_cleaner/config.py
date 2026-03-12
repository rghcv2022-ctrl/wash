from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

APP_NAME: Final[str] = "zht C盘深度清理大师"
APP_VERSION: Final[str] = "2.1.0"
DEFAULT_LARGE_FILE_THRESHOLD_MB: Final[int] = 500
DEFAULT_SCAN_ROOT: Final[Path] = Path(f"{os.environ.get('SystemDrive', 'C:')}\\")
WINDOWS_ROOT: Final[Path] = Path(os.environ.get("SystemRoot", r"C:\Windows"))


def _collect_paths(*values: str | None) -> tuple[Path, ...]:
    return tuple(Path(value).expanduser() for value in values if value)


@dataclass(frozen=True)
class CleanupCategory:
    name: str
    paths: tuple[Path, ...] = ()
    includes_dev_tool_cleanup: bool = False
    needs_windows_update_service: bool = False


@dataclass(frozen=True)
class SystemTool:
    key: str
    label: str
    description: str
    command: tuple[str, ...]
    detached: bool = False


CLEANUP_CATEGORIES: Final[tuple[CleanupCategory, ...]] = (
    CleanupCategory(
        name="系统临时文件",
        paths=_collect_paths(
            os.environ.get("TEMP"),
            str(WINDOWS_ROOT / "Temp"),
            str(WINDOWS_ROOT / "Prefetch"),
            str(WINDOWS_ROOT / "System32" / "LogFiles"),
        ),
    ),
    CleanupCategory(
        name="Windows 更新缓存",
        paths=_collect_paths(str(WINDOWS_ROOT / "SoftwareDistribution" / "Download")),
        needs_windows_update_service=True,
    ),
    CleanupCategory(
        name="浏览器缓存",
        paths=_collect_paths(
            r"~\AppData\Local\Google\Chrome\User Data\Default\Cache",
            r"~\AppData\Local\Google\Chrome\User Data\Default\Code Cache",
            r"~\AppData\Local\Microsoft\Edge\User Data\Default\Cache",
            r"~\AppData\Local\Microsoft\Edge\User Data\Default\Code Cache",
        ),
    ),
    CleanupCategory(
        name="开发者垃圾 (Conda/Pip/Code/NPM)",
        paths=_collect_paths(
            r"~\AppData\Local\pip\cache",
            r"~\AppData\Local\npm-cache",
            r"~\AppData\Roaming\Code\CachedData",
            r"~\AppData\Roaming\Code\User\workspaceStorage",
            r"~\.gradle\caches",
        ),
        includes_dev_tool_cleanup=True,
    ),
    CleanupCategory(
        name="用户崩溃转储",
        paths=_collect_paths(r"~\AppData\Local\CrashDumps"),
    ),
)

CLEANUP_CATEGORY_MAP: Final[dict[str, CleanupCategory]] = {
    category.name: category for category in CLEANUP_CATEGORIES
}

SENSITIVE_SCAN_SEGMENTS: Final[tuple[str, ...]] = (
    r"windows\winsxs",
    r"windows\servicing",
    r"windows\system32",
)

SYSTEM_TOOLS: Final[tuple[SystemTool, ...]] = (
    SystemTool(
        key="dism",
        label="[推荐] 清理 WinSxS 组件 (DISM)",
        description="正在深度清理 WinSxS 组件存储...",
        command=("dism", "/online", "/cleanup-image", "/startcomponentcleanup"),
    ),
    SystemTool(
        key="hiber",
        label="关闭休眠 (释放 Hiberfil.sys)",
        description="正在关闭休眠功能...",
        command=("powercfg", "-h", "off"),
    ),
    SystemTool(
        key="cleanmgr",
        label="打开 Windows 磁盘清理器",
        description="正在启动 Windows 磁盘清理工具...",
        command=("cleanmgr", "/d", "C"),
        detached=True,
    ),
    SystemTool(
        key="compact",
        label="CompactOS 系统压缩 (省 2-4GB)",
        description="正在执行系统压缩...",
        command=("compact.exe", "/CompactOS:always"),
    ),
)

SYSTEM_TOOL_MAP: Final[dict[str, SystemTool]] = {tool.key: tool for tool in SYSTEM_TOOLS}
