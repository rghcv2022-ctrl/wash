from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .config import (
    APP_NAME,
    APP_VERSION,
    CLEANUP_CATEGORIES,
    DEFAULT_LARGE_FILE_THRESHOLD_MB,
    DEFAULT_SCAN_ROOT,
    SYSTEM_TOOLS,
)
from .core import clean_selected_categories, format_bytes, get_cleanup_categories, is_admin, run_system_tool, scan_large_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} 命令行工具")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")

    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="列出清理分类和系统工具")
    list_parser.set_defaults(command="list")

    clean_parser = subparsers.add_parser("clean", help="执行清理流程")
    clean_parser.add_argument(
        "--category",
        action="append",
        choices=[category.name for category in CLEANUP_CATEGORIES],
        help="仅清理指定分类，可重复传入",
    )
    clean_parser.add_argument(
        "--open-cleanmgr",
        action="store_true",
        help="清理完成后打开 Windows 磁盘清理器",
    )

    scan_parser = subparsers.add_parser("scan", help="扫描系统盘大文件")
    scan_parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_LARGE_FILE_THRESHOLD_MB,
        help="阈值，单位 MB",
    )
    scan_parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_SCAN_ROOT,
        help="扫描根目录，默认系统盘",
    )
    scan_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="仅显示前 N 个结果",
    )

    tool_parser = subparsers.add_parser("tool", help="运行系统工具")
    tool_parser.add_argument("name", choices=[tool.key for tool in SYSTEM_TOOLS], help="系统工具名称")

    return parser


def _require_admin(command: str) -> bool:
    return command in {"clean", "tool"}


def _print_list() -> int:
    print("可用清理分类：")
    for category in CLEANUP_CATEGORIES:
        print(f"  - {category.name}")

    print("\n可用系统工具：")
    for tool in SYSTEM_TOOLS:
        print(f"  - {tool.key}: {tool.label}")
    return 0


def _run_clean(category_names: Sequence[str] | None, open_cleanmgr: bool) -> int:
    categories = get_cleanup_categories(category_names)
    summary = clean_selected_categories(categories, logger=print)
    print(
        f"\n清理完成：处理 {summary.processed_paths} 个路径，"
        f"累计释放约 {format_bytes(summary.total_bytes_freed)}。"
    )

    if open_cleanmgr:
        run_system_tool("cleanmgr", logger=print)

    return 0


def _run_scan(root: Path, threshold: int, limit: int) -> int:
    results = scan_large_files(root=root, threshold_mb=threshold, logger=print)
    if not results:
        print("没有找到符合条件的大文件。")
        return 0

    print()
    for item in results[:limit]:
        print(f"{format_bytes(item.size_bytes):>10}  {item.path}")

    if len(results) > limit:
        print(f"\n仅显示前 {limit} 条，共找到 {len(results)} 条。")

    return 0


def _run_tool(name: str) -> int:
    run_system_tool(name, logger=print)
    print("系统工具已执行。")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "clean"

    if _require_admin(command) and not is_admin():
        parser.error("该操作需要管理员权限，请使用管理员身份运行命令行。")

    if command == "list":
        return _print_list()
    if command == "clean":
        return _run_clean(category_names=args.category, open_cleanmgr=args.open_cleanmgr)
    if command == "scan":
        return _run_scan(root=args.root, threshold=args.threshold, limit=args.limit)
    if command == "tool":
        return _run_tool(args.name)

    parser.print_help()
    return 0
