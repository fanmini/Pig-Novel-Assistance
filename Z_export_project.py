import os
import shutil

def export_clean_project():
    # 1. 获取当前脚本所在的根目录路径
    # 假设 test.py 放在项目根目录下
    current_project_path = os.path.abspath(os.path.dirname(__file__))
    project_folder_name = os.path.basename(current_project_path)
    parent_path = os.path.dirname(current_project_path)

    # 2. 定义导出目录的名称（在同级目录下创建一个名为“原项目名_Clean_Export”的文件夹）
    export_folder_name = f"{project_folder_name}_Clean_Export"
    export_path = os.path.join(parent_path, export_folder_name)

    # 3. 如果导出目录已经存在，先将其彻底删除，确保每次都是最新的干净副本
    if os.path.exists(export_path):
        print(f"正在清理旧的导出副本: {export_path}")
        try:
            shutil.rmtree(export_path)
        except Exception as e:
            print(f"删除失败: {e}。请检查文件夹是否被占用。")
            return

    # 4. 定义需要忽略（不复制）的文件和文件夹名单
    # 包含了数据、日志、虚拟环境、缓存以及常见的 IDE 配置文件
    ignore_list = shutil.ignore_patterns(
        'data',           # 书籍、向量库数据
        'logs',           # 运行日志
        '.venv',          # Python 虚拟环境
        'venv',           # 常见的虚拟环境名
        '__pycache__',    # Python 编译缓存
        '.git',           # Git 仓库信息
        '.idea',          # PyCharm 配置
        '.vscode',        # VS Code 配置
        '*.pyc',          # 编译字节码文件
        'test.py'         # 导出脚本自身（可选，如果不希望副本里也有这个脚本）
    )

    # 5. 开始执行复制操作
    print(f"开始导出干净的项目代码...")
    print(f"源路径: {current_project_path}")
    print(f"目标路径: {export_path}")

    try:
        shutil.copytree(current_project_path, export_path, ignore=ignore_list)
        print("\n" + "="*30)
        print("✅ 导出成功！")
        print(f"项目副本已保存在: {export_path}")
        print("="*30)
    except Exception as e:
        print(f"❌ 导出过程中出现错误: {e}")

if __name__ == "__main__":
    export_clean_project()