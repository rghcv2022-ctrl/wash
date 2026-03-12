from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .config import (
    CLEANUP_CATEGORY_MAP,
    SENSITIVE_SCAN_SEGMENTS,
    SYSTEM_TOOL_MAP,
    CleanupCategory,
)

Logger = Callable[[str], None]


@dataclass(frozen=True)
class CleanupSummary:
    total_bytes_freed: int
    processed_paths: int
    selected_categories: tuple[str, ...]


@dataclass(frozen=True)
class LargeFileEntry:
    path: Path
    size_bytes: int


def _log(logger: Logger | None, message: str) -> None:
    if logger is not None:
        logger(message)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def restart_as_admin() -> None:
    if getattr(sys, "frozen", False):
        executable = sys.executable
        parameters = subprocess.list2cmdline(sys.argv[1:])
    else:
        executable = sys.executable
        parameters = subprocess.list2cmdline(sys.argv)

    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, parameters, None, 1)
    if int(result) <= 32:
        raise RuntimeError("无法以管理员身份重新启动程序。")


def format_bytes(size: int) -> str:
    size_float = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if size_float < 1024 or unit == "PB":
            return f"{size_float:.2f} {unit}"
        size_float /= 1024
    return f"{size_float:.2f} PB"


def get_cleanup_categories(names: Iterable[str] | None = None) -> tuple[CleanupCategory, ...]:
    if names is None:
        return tuple(CLEANUP_CATEGORY_MAP.values())

    selected: list[CleanupCategory] = []
    unknown: list[str] = []

    for name in names:
        category = CLEANUP_CATEGORY_MAP.get(name)
        if category is None:
            unknown.append(name)
        else:
            selected.append(category)

    if unknown:
        available = "、".join(CLEANUP_CATEGORY_MAP)
        raise ValueError(f"未知清理分类: {', '.join(unknown)}。可选值: {available}")

    return tuple(selected)


def clean_directory(path: Path) -> int:
    if not path.exists():
        return 0

    if path.is_file():
        try:
            size = path.stat().st_size
            path.unlink()
            return size
        except OSError:
            return 0

    freed_bytes = 0
    for current_root, dirnames, filenames in os.walk(path, topdown=False):
        root_path = Path(current_root)

        for filename in filenames:
            file_path = root_path / filename
            try:
                if file_path.is_symlink():
                    file_path.unlink()
                    continue

                freed_bytes += file_path.stat().st_size
                file_path.unlink()
            except OSError:
                continue

        for dirname in dirnames:
            dir_path = root_path / dirname
            try:
                dir_path.rmdir()
            except OSError:
                continue

    return freed_bytes


def clean_developer_caches(logger: Logger | None = None) -> None:
    commands: list[tuple[list[str], str]] = []

    if shutil.which("conda"):
        commands.append((["conda", "clean", "--all", "-y"], "Conda 缓存已清理"))

    if shutil.which("pip"):
        commands.append((["pip", "cache", "purge"], "Pip 缓存已清理"))

    if not commands:
        _log(logger, "未检测到 Conda 或 Pip，可跳过命令行缓存清理。")
        return

    _log(logger, "正在执行开发者缓存命令...")
    for command, success_message in commands:
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _log(logger, f"  - {success_message}")
        except (OSError, subprocess.SubprocessError):
            _log(logger, f"  - 命令执行失败: {' '.join(command)}")


def _set_windows_update_services(start: bool, logger: Logger | None = None) -> None:
    action = "start" if start else "stop"
    verb = "重启" if start else "停止"
    _log(logger, f"正在{verb} Windows Update 服务...")

    for service in ("wuauserv", "bits"):
        try:
            subprocess.run(
                ["net", action, service],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            _log(logger, f"  - 无法执行 net {action} {service}")


def clean_selected_categories(
    categories: Sequence[CleanupCategory],
    logger: Logger | None = None,
) -> CleanupSummary:
    selected = tuple(categories)
    if not selected:
        return CleanupSummary(total_bytes_freed=0, processed_paths=0, selected_categories=())

    total_freed = 0
    processed_paths = 0
    requires_windows_update = any(item.needs_windows_update_service for item in selected)

    if requires_windows_update:
        _set_windows_update_services(start=False, logger=logger)

    try:
        for category in selected:
            _log(logger, f"正在处理: {category.name}")
            category_total = 0

            for path in category.paths:
                if not path.exists():
                    _log(logger, f"  - 跳过不存在路径: {path}")
                    continue

                freed = clean_directory(path)
                total_freed += freed
                category_total += freed
                processed_paths += 1
                _log(logger, f"  - 已清理 {path}，释放约 {format_bytes(freed)}")

            if category.includes_dev_tool_cleanup:
                clean_developer_caches(logger=logger)

            _log(logger, f"完成分类: {category.name}，累计释放约 {format_bytes(category_total)}")
    finally:
        if requires_windows_update:
            _set_windows_update_services(start=True, logger=logger)

    return CleanupSummary(
        total_bytes_freed=total_freed,
        processed_paths=processed_paths,
        selected_categories=tuple(category.name for category in selected),
    )


def _should_skip_scan_path(path: Path) -> bool:
    normalized = str(path).lower()
    return any(segment in normalized for segment in SENSITIVE_SCAN_SEGMENTS)


def scan_large_files(
    root: Path,
    threshold_mb: int,
    logger: Logger | None = None,
) -> list[LargeFileEntry]:
    if threshold_mb <= 0:
        raise ValueError("扫描阈值必须大于 0。")

    _log(logger, f">>> 正在扫描 {root} 中大于 {threshold_mb} MB 的文件，请耐心等待...")
    threshold_bytes = threshold_mb * 1024 * 1024
    results: list[LargeFileEntry] = []

    for current_root, dirnames, filenames in os.walk(root):
        root_path = Path(current_root)
        dirnames[:] = [dirname for dirname in dirnames if not _should_skip_scan_path(root_path / dirname)]

        for filename in filenames:
            file_path = root_path / filename
            try:
                if file_path.is_symlink():
                    continue

                size_bytes = file_path.stat().st_size
            except OSError:
                continue

            if size_bytes >= threshold_bytes:
                results.append(LargeFileEntry(path=file_path, size_bytes=size_bytes))

    results.sort(key=lambda item: item.size_bytes, reverse=True)
    _log(logger, f"扫描完成，找到 {len(results)} 个大文件。")
    return results


def delete_file(path: Path) -> None:
    path.unlink()


def run_system_tool(tool_key: str, logger: Logger | None = None) -> None:
    tool = SYSTEM_TOOL_MAP[tool_key]
    _log(logger, tool.description)

    if tool.detached:
        subprocess.Popen(tool.command)
        return

    subprocess.run(tool.command, check=True)
