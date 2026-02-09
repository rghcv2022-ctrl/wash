import os
import shutil
import ctypes
import sys
import subprocess
import platform

def is_admin():
    """检查是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_size(start_path):
    """计算文件夹大小 (用于统计清理量)"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # 跳过如果是链接文件
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except Exception:
        pass
    return total_size

def format_bytes(size):
    """格式化字节大小"""
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def clean_folder(folder_path, folder_name):
    """清理指定文件夹内容"""
    if not os.path.exists(folder_path):
        print(f"[-] {folder_name} 不存在，跳过...")
        return

    print(f"[*] 正在扫描 {folder_name} ({folder_path})...")
    
    # 清理前计算大小
    initial_size = get_size(folder_path)
    if initial_size == 0:
        print(f"   - {folder_name} 是空的，无需清理。")
        return

    print(f"   - 发现 {format_bytes(initial_size)} 垃圾文件，开始清理...")

    deleted_files = 0
    errors = 0

    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path) # 删除文件
                deleted_files += 1
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path) # 删除文件夹
                deleted_files += 1
        except Exception as e:
            # 文件通常被占用，这是正常的，跳过即可
            errors += 1
    
    print(f"   + 清理完成: 删除了 {deleted_files} 个项目 (跳过 {errors} 个占用文件)")

def clean_windows_update():
    """专门处理 Windows 更新缓存 (需要停止服务)"""
    update_path = os.path.join(os.environ['WINDIR'], 'SoftwareDistribution', 'Download')
    print(f"\n[*] 准备清理 Windows 更新缓存...")
    
    # 尝试停止服务
    print("   - 正在停止 Windows Update 服务...")
    subprocess.run(["net", "stop", "wuauserv"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["net", "stop", "bits"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    clean_folder(update_path, "Windows Update Cache")

    # 重启服务
    print("   - 正在重启 Windows Update 服务...")
    subprocess.run(["net", "start", "wuauserv"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["net", "start", "bits"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("==========================================")
    print("     zht C盘深度清理工具 v1.0")
    print("==========================================\n")

    if not is_admin():
        print("[!] 错误: 请以管理员身份运行此脚本！")
        print("    方法: 右键点击 CMD/PowerShell -> 以管理员身份运行 -> 输入 'python clean_c_drive.py'")
        input("\n按回车键退出...")
        sys.exit()

    # 1. 清理用户临时文件夹
    user_temp = os.environ.get('TEMP')
    clean_folder(user_temp, "用户临时文件 (Temp)")

    # 2. 清理系统临时文件夹
    system_temp = os.path.join(os.environ['WINDIR'], 'Temp')
    print()
    clean_folder(system_temp, "系统临时文件 (Windows/Temp)")

    # 3. 清理 Prefetch (预读取)
    prefetch = os.path.join(os.environ['WINDIR'], 'Prefetch')
    print()
    clean_folder(prefetch, "预读取文件 (Prefetch)")

    # 4. 清理 Windows 更新缓存 (高风险操作，已做安全处理)
    clean_windows_update()

    # 5. 调用系统自带磁盘清理 (可选)
    print("\n[*] 正在调用 Windows 磁盘清理工具 (cleanmgr)...")
    # /sagerun:1 需要预先配置，这里使用 /d c 简单调用或提示用户
    try:
        subprocess.Popen("cleanmgr /d c", shell=True)
        print("   + 磁盘清理窗口已打开，请手动勾选要删除的项目并点击确定。")
    except Exception as e:
        print(f"   - 调用失败: {e}")

    print("\n==========================================")
    print("           全部清理流程结束")
    print("==========================================")
    input("按回车键退出...")

if __name__ == "__main__":
    main()