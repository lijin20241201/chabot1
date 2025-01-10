import time # 导入time模块，用于处理时间相关功能
import pip  # 导入pip模块，用于安装Python包
from pip._internal import main as pipmain # 从pip内部导入main函数，用于安装包
from common.log import _reset_logger, logger # 从自定义日志模块导入日志重置函数和日志记录器

def install(package):
    # 安装指定的包
    pipmain(["install", package]) # 使用pip安装指定的包


def install_requirements(file):
    # 安装requirements.txt中的所有依赖包
    pipmain(["install", "-r", file, "--upgrade"])  # 使用pip安装依赖文件中的包并升级
    # 重置日志配置的目的是确保在安装依赖包后，日志系统能够适应新的环境或依赖，避免旧的日志配置影响新安装的功能或依赖包。
    _reset_logger(logger) # 安装完成后重置日志配置

def check_dulwich():
    # 检查并安装dulwich包
    needwait = False # 初始化标志变量，用于判断是否需要等待
    for i in range(2):  # 重试2次
        if needwait:  # 如果需要等待（上一次安装失败），则等待3秒钟
            # 通过等待 3 秒，程序可以在第一次安装失败后给网络或服务器一些恢复的时间，这样即使网络问题只是暂时的，也有可
            # 能解决，从而提高成功安装的概率，避免不必要的重复安装尝试。
            time.sleep(3)  # 暂停3秒
            needwait = False # 重置标志变量
        try:
            import dulwich  # 尝试导入dulwich包

            return # 如果导入成功，直接返回
        except ImportError:  # 如果导入失败，尝试安装dulwich
            try:
                install("dulwich") # 安装dulwich包
            except:
                needwait = True # 设置需要等待标志
    try:
        import dulwich # 再次尝试导入dulwich包
    except ImportError: # 如果仍然无法导入，抛出异常
        raise ImportError("Unable to import dulwich") # 抛出无法导入dulwich的错误
