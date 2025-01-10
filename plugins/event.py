# encoding:utf-8

from enum import Enum


class Event(Enum):
    ON_RECEIVE_MESSAGE = 1  # 收到消息事件
    """
    e_context = {  "channel": 消息channel, "context" : 本次消息的context}
    """

    ON_HANDLE_CONTEXT = 2  # 处理回复事件
    """
    e_context = {  "channel": 消息channel, "context" : 本次消息的context, "reply" : 目前的回复，初始为空  }
    """

    ON_DECORATE_REPLY = 3  # 装饰回复事件
    """
    e_context = {  "channel": 消息channel, "context" : 本次消息的context, "reply" : 目前的回复 }
    """

    ON_SEND_REPLY = 4  # 发送回复事件
    """
    e_context = {  "channel": 消息channel, "context" : 本次消息的context, "reply" : 目前的回复 }
    """

    # AFTER_SEND_REPLY = 5    # 发送回复后

# 事件传播行为
class EventAction(Enum):
    CONTINUE = 1  # 事件未结束，继续交给下个插件处理，如果没有下个插件，则交付给默认的事件处理逻辑
    BREAK = 2  # 事件结束，不再给下个插件处理，交付给默认的事件处理逻辑
    BREAK_PASS = 3  # 事件结束，不再给下个插件处理，不交付给默认的事件处理逻辑

# 事件上下文封装类
class EventContext:
    def __init__(self, event, econtext=dict()): # 初始化事件上下文
        self.event = event # 事件本身
        self.econtext = econtext # 事件相关的上下文数据，默认为空字典
        self.action = EventAction.CONTINUE # 设置默认的事件传播行为
    # 获取上下文中的某个值
    def __getitem__(self, key):
        return self.econtext[key]
     # 设置上下文中的某个值
    def __setitem__(self, key, value):
        self.econtext[key] = value
    # 删除上下文中的某个值
    def __delitem__(self, key):
        del self.econtext[key]
    def is_pass(self): 
        return self.action == EventAction.BREAK_PASS
    def is_break(self):
        return self.action == EventAction.BREAK or self.action == EventAction.BREAK_PASS
