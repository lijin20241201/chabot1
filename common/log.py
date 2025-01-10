import logging # 导入Python的日志模块
import sys # 导入系统模块，用于处理标准输出

# 重置日志配置
def _reset_logger(log):
    for handler in log.handlers: # 遍历现有的日志处理器
        handler.close() # 关闭日志处理器
        log.removeHandler(handler) # 从日志中移除处理器
        del handler # 删除处理器对象
    log.handlers.clear()  # 清空处理器列表
    log.propagate = False  # 禁止日志向父记录器传播
    # 设置控制台日志输出
    console_handle = logging.StreamHandler(sys.stdout) # 创建一个输出到标准输出的流处理器
    console_handle.setFormatter(
        logging.Formatter(
            "[%(levelname)s][%(asctime)s][%(filename)s:%(lineno)d] - %(message)s",  # 设置日志输出格式
            datefmt="%Y-%m-%d %H:%M:%S", # 设置时间格式
        )
    )
    # 设置文件日志输出
    file_handle = logging.FileHandler("run.log", encoding="utf-8") # 创建一个输出到文件的处理器，文件名为"run.log"
    file_handle.setFormatter(
        logging.Formatter(
            "[%(levelname)s][%(asctime)s][%(filename)s:%(lineno)d] - %(message)s", # 设置日志输出格式
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(file_handle) # 将文件处理器添加到日志
    log.addHandler(console_handle) # 将控制台处理器添加到日志


def _get_logger():
    # 获取日志记录器
    log = logging.getLogger("log") # 获取名为"log"的日志记录器
    _reset_logger(log) # 调用_reset_logger函数配置日志记录器
    log.setLevel(logging.INFO)  # 设置日志的最低级别为INFO
    return log # 返回配置好的日志记录器


logger = _get_logger()  # 获取配置好的日志记录器实例并赋值给logger
