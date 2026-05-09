import subprocess
import sys


def reveal_in_finder(path: str) -> None:
    """跨平台在文件管理器中显示该路径的父目录并选中。"""
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", path], check=False)
    elif sys.platform == "win32":
        subprocess.run(["explorer.exe", "/select,", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)
