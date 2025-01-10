import logging

class LogSystem(object):
    handlerList = [] # 存储所有的处理器（handlers）
    showOnCmd = True # 是否在命令行显示日志
    loggingLevel = logging.INFO # 日志的默认级别，默认为INFO
    loggingFile = None # 日志文件的路径，默认为None
    def __init__(self):
        self.logger = logging.getLogger('itchat') # 创建一个名为 'itchat' 的日志记录器
        self.logger.addHandler(logging.NullHandler())  # 添加一个空的处理器，以防没有日志处理器时产生错误
        self.logger.setLevel(self.loggingLevel) # 设置日志的默认级别为 logging.INFO
        self.cmdHandler = logging.StreamHandler() # 创建一个流处理器，将日志输出到命令行
        self.fileHandler = None # 初始化文件处理器为空
        self.logger.addHandler(self.cmdHandler) # 将命令行流处理器添加到日志记录器中
    def set_logging(self, showOnCmd=True, loggingFile=None,
            loggingLevel=logging.INFO):
            '''
            设置日志的显示方式和级别
            参数：
            - showOnCmd: 是否在命令行显示日志，默认True
            - loggingFile: 日志文件的路径，默认None，表示不写入文件
            - loggingLevel: 设置日志的级别，默认为logging.INFO
            '''
        if showOnCmd != self.showOnCmd: # 如果是否显示在命令行的设置有变化
            if showOnCmd:
                self.logger.addHandler(self.cmdHandler) # 显示日志到命令行
            else:
                self.logger.removeHandler(self.cmdHandler)  # 不显示日志到命令行
            self.showOnCmd = showOnCmd  # 更新显示日志到命令行的设置
        # 如果日志文件路径有变化
        if loggingFile != self.loggingFile:
            if self.loggingFile is not None: # 如果之前有文件处理器，先移除它
                self.logger.removeHandler(self.fileHandler)  # 移除旧的文件处理器
                self.fileHandler.close() # 关闭旧的文件处理器
            if loggingFile is not None: # 如果提供了新的日志文件路径，添加新的文件处理器
                self.fileHandler = logging.FileHandler(loggingFile) # 创建一个新的文件处理器
                self.logger.addHandler(self.fileHandler) # 将新的文件处理器添加到日志记录器中
            self.loggingFile = loggingFile # 更新日志文件路径
        # 如果日志级别有变化
        if loggingLevel != self.loggingLevel:
            self.logger.setLevel(loggingLevel)  # 设置新的日志级别
            self.loggingLevel = loggingLevel # 更新日志级别
# 创建一个 LogSystem 实例
ls = LogSystem()
set_logging = ls.set_logging # 设置日志的配置方法
