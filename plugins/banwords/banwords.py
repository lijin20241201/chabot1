# encoding:utf-8

import json
import os

import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *

from .lib.WordsSearch import WordsSearch


@plugins.register(
    name="Banwords", # 插件名称
    desire_priority=100, # 插件优先级，越高越优先执行
    hidden=True, # 插件是否隐藏
    desc="判断消息中是否有敏感词、决定是否回复。",  # 插件描述
    version="1.0", # 插件版本
    author="lanvent", # 插件作者
)
class Banwords(Plugin):
    def __init__(self):
        super().__init__() # 调用父类构造函数初始化插件
        try:
            conf = super().load_config()  # 从配置文件加载配置信息
            curdir = os.path.dirname(__file__) # 获取当前文件的目录路径
            if not conf:
                # 如果配置文件不存在，则写入默认配置
                config_path = os.path.join(curdir, "config.json")
                if not os.path.exists(config_path):
                    conf = {"action": "ignore"}  # 设置默认的行为为忽略敏感词
                    with open(config_path, "w") as f:
                        json.dump(conf, f, indent=4)  # 将默认配置写入文件
            # 初始化敏感词搜索对象
            self.searchr = WordsSearch()
            self.action = conf["action"] # 配置文件中定义的动作（如：ignore或replace）
            banwords_path = os.path.join(curdir, "banwords.txt") # 敏感词文件路径
            with open(banwords_path, "r", encoding="utf-8") as f: # 读取文件,写入列表
                words = []
                for line in f:
                    word = line.strip()
                    if word:
                        words.append(word)
            self.searchr.SetKeywords(words)  # 设置敏感词
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context # 注册处理回复事件处理器
            if conf.get("reply_filter", True): # 如果启用回复过滤
                self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply # 注册装饰回复事件处理器
                self.reply_action = conf.get("reply_action", "ignore")  # 配置回复中的敏感词处理方式
            logger.info("[Banwords] inited")
        except Exception as e:
            logger.warn("[Banwords] init failed, ignore or see https://github.com/zhayujie/chatgpt-on-wechat/tree/master/plugins/banwords .")
            raise e

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [ # 如果消息类型不是文本或图片创建,不处理
            ContextType.TEXT,
            ContextType.IMAGE_CREATE,
        ]:
            return

        content = e_context["context"].content # 获取消息内容
        logger.debug("[Banwords] on_handle_context. content: %s" % content)
        if self.action == "ignore": # 如果处理行为是忽略
            f = self.searchr.FindFirst(content)  # 查找敏感词
            if f: # 如果找到,原始代码是不做处理，静默,啥也不做，不回复
                logger.info("[Banwords] %s in message" % f["Keyword"])
                # reply = Reply(ReplyType.INFO, "您的消息中包含敏感词，已被忽略。")
                e_context.action = EventAction.BREAK_PASS # 设置事件行为为BREAK_PASS(结束所有事件处理)
                return 
        elif self.action == "replace": # 如果处理行为是替换
            if self.searchr.ContainsAny(content): # 找到消息中所有敏感词
                # 返回替换了文本消息中敏感词的回复，比如替换成***之类的占位符
                reply = Reply(ReplyType.INFO, "发言中包含敏感词，请重试: \n" + self.searchr.Replace(content))
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS  # 设置事件行为为BREAK_PASS(结束所有事件处理)
                return

    def on_decorate_reply(self, e_context: EventContext):
        if e_context["reply"].type not in [ReplyType.TEXT]: # 如果回复类型不是文本类型,直接不处理
            return
        reply = e_context["reply"] # 获取回复
        content = reply.content # 获取回复的内容
        if self.reply_action == "ignore": # 如果设置的reply_action为忽略
            f = self.searchr.FindFirst(content) # 查找敏感词
            if f: # 如果找到
                logger.info("[Banwords] %s in reply" % f["Keyword"]) 
                e_context["reply"] = None # 设置回复为None,就是啥也不做，静默处理
                e_context.action = EventAction.BREAK_PASS # 设置结束所有事件处理逻辑
                return
        elif self.reply_action == "replace": # 如果是替换的话
            if self.searchr.ContainsAny(content):
                # 设置回复为替换了敏感词后的回复
                reply = Reply(ReplyType.INFO, "已替换回复中的敏感词: \n" + self.searchr.Replace(content))
                e_context["reply"] = reply
                e_context.action = EventAction.CONTINUE # 事件传播行为设置为继续,如果有其他插件监听这个事件,会继续处理
                return

    def get_help_text(self, **kwargs):
        return "过滤消息中的敏感词。"
