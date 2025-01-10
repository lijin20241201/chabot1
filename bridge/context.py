# encoding:utf-8
from enum import Enum
class ContextType(Enum): # 消息类型
    TEXT = 1  # 文本消息
    VOICE = 2  # 音频消息
    IMAGE = 3  # 图片消息
    FILE = 4  # 文件信息
    VIDEO = 5  # 视频信息
    SHARING = 6  # 分享信息
    IMAGE_CREATE = 10  # 创建图片命令
    ACCEPT_FRIEND = 19 # 同意好友请求
    JOIN_GROUP = 20  # 加入群聊
    PATPAT = 21  # 拍了拍
    FUNCTION = 22  # 函数调用
    EXIT_GROUP = 23 # 退出群

    def __str__(self):
        return self.name
# Context 类用于封装和存储一条消息的上下文信息，包括消息的类型、内容和附加的参数（以字典的形式存储）。
# 它提供了多种方法来访问和修改这些信息。
# Context 类可以被看作一个字典，或者更准确地说，模拟了字典的行为。它通过实现几个魔法方法（如 __contains__、__getitem__、
# __setitem__ 和 __delitem__），使得它在许多方面的行为与字典类似。这些方法使得 Context 类对象能够使用 in 操作符、索引操
# 作符（[]）、以及通过 get 方法来访问或修改存储在其中的值。
class Context:
    # 初始化方法
    # type：表示消息的类型，类型应该是 ContextType 枚举中的一种。默认为 None。
    # content：表示消息的内容，可以是任何类型（文本、音频、文件等），默认为 None。
    # kwargs：一个字典，用来存储其他附加的参数，默认为空字典 {}。
    def __init__(self, type: ContextType = None, content=None, kwargs=dict()):
        self.type = type
        self.content = content
        self.kwargs = kwargs
    # 使 Context 对象支持 in 操作符。检查给定的键是否存在于 Context 中，首先检查 type 和 content 属性，然后检查 kwargs 字典。
    # __contains__ 魔法方法可以让 Context 对象支持 in 操作符。因此，通过定义 __contains__ 方法，你可以实现诸如 "origin_ctype"
    # not in context 这样的语法。
    def __contains__(self, key):
        if key == "type":
            return self.type is not None
        elif key == "content":
            return self.content is not None
        else:
            return key in self.kwargs
    # 使 Context 对象支持 [] 操作符来获取属性值。如果键是 type 或 content，返回相应的属性值，否则从 kwargs 字典中获取值。
    def __getitem__(self, key):
        if key == "type":
            return self.type
        elif key == "content":
            return self.content
        else:
            return self.kwargs[key]
    # 提供另一种方式来获取属性的值，并允许设置默认值。如果键存在于 Context 中，返回其值，否则返回默认值。
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
    #  使 Context 对象支持 [] 操作符来设置属性值。如果键是 type 或 content，设置相应的属性值，否则将值存储在 kwargs 字典中。
    def __setitem__(self, key, value):
        if key == "type":
            self.type = value
        elif key == "content":
            self.content = value
        else:
            self.kwargs[key] = value
    # 使 Context 对象支持 [] 操作符来删除属性。如果键是 type 或 content，将相应的属性设置为 None，否则从 kwargs 字典中删除该键。
    def __delitem__(self, key):
        if key == "type":
            self.type = None
        elif key == "content":
            self.content = None
        else:
            del self.kwargs[key]
    # 定义 Context 对象的字符串表示形式，方便打印输出
    def __str__(self):
        return "Context(type={}, content={}, kwargs={})".format(self.type, self.content, self.kwargs)
