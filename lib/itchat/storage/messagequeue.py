import logging
try:
    import Queue as queue # Python 2 的 Queue 模块，命名为 queue
except ImportError:
    import queue # 如果是 Python 3，则直接导入 queue 模块

from .templates import AttributeDict # 从当前包导入 AttributeDict 类
# 初始化日志记录器，指定名称为 'itchat'
logger = logging.getLogger('itchat')

# 定义一个继承自 queue.Queue 的自定义队列类
class Queue(queue.Queue):
    def put(self, message): # 重写 put 方法，将传入的消息封装为 Message 对象后存入队列
        queue.Queue.put(self, Message(message))  # 调用父类的 put 方法，将封装后的消息存入队列

# 定义 Message 类，继承自 AttributeDict
class Message(AttributeDict):
    # 定义下载方法，用于下载文件
    def download(self, fileName):
        # 如果 text 属性是可调用的函数或方法，则调用它并传入文件名
        if hasattr(self.text, '__call__'):
            return self.text(fileName)
        else:  # 如果 text 不是可调用对象，返回空字节串
            return b''
    # 重写 __getitem__ 方法，支持特定的过期属性访问提醒
    def __getitem__(self, value):
        if value in ('isAdmin', 'isAt'): # 检查是否访问过期的属性
            v = value[0].upper() + value[1:] # ''[1:] == '' # 将属性名称首字母大写（例如 'isAdmin' 转换为 'IsAdmin'）
            logger.debug('%s is expired in 1.3.0, use %s instead.' % (value, v))  # 记录提醒日志
            value = v # 将访问的属性名替换为首字母大写的版本
        return super(Message, self).__getitem__(value) # 调用父类的 __getitem__ 获取属性值
    # 重写 __str__ 方法，返回字典的字符串表示形式
    def __str__(self):
        return '{%s}' % ', '.join(
            ['%s: %s' % (repr(k),repr(v)) for k,v in self.items()]) # 将字典中的键值对格式化为字符串
    # 重写 __repr__ 方法，返回对象的正式字符串表示形式
    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__.split('.')[-1],
            self.__str__()) # 显示类名（去掉包名）和字典内容的字符串表示
