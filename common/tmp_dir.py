import os # 导入os模块，用于文件和目录的操作
import pathlib # 导入pathlib模块，用于处理路径操作
import shutil  # 导入shutil，用于删除非空目录
from config import conf # 导入配置模块

# __del__ 是 Python 中的一个特殊方法，用于在对象被销毁时执行清理操作。
# 当对象没有引用时，垃圾回收会触发 __del__ 方法的调用。
# 你可以在子类中重写 __del__ 方法来执行清理操作，如果父类有 __del__ 方法，并且你希望调用父类的清理逻辑，才需要使用 super().__del__()。
# 在你当前的 TmpDir 类中，由于父类 object 没有 __del__ 实现，因此不需要调用 super().__del__()。
class TmpDir(object): # 定义一个临时目录的类
    # 该类表示一个临时目录，且当对象被销毁时，目录会被删除。
    tmpFilePath = pathlib.Path("./tmp/")
    
    def __init__(self):
        pathExists = os.path.exists(self.tmpFilePath) # 判断临时目录是否已存在
        if not pathExists: # 如果临时目录不存在
            os.makedirs(self.tmpFilePath) # 创建该目录

    def path(self):
        return str(self.tmpFilePath) + "/" # 返回临时目录的路径，路径以斜杠结尾
    # def __del__(self):
    #     """在对象销毁时删除临时目录及其内容"""
    #     if os.path.exists(self.tmpFilePath):  # 检查目录是否存在
    #         shutil.rmtree(self.tmpFilePath)  # 删除目录及其中的所有内容
    #         print(f"临时目录 {self.tmpFilePath} 已删除。")