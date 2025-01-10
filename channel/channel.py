from bridge.bridge import Bridge
from bridge.context import Context
from bridge.reply import *
# 通道基类
class Channel(object):
    channel_type = "" # 通道类型，初始化为空字符串
    NOT_SUPPORT_REPLYTYPE = [ReplyType.VOICE, ReplyType.IMAGE] # 不支持的回复类型（语音和图片）
    def startup(self):
        raise NotImplementedError # 子类需要实现该方法，初始化通道时调用
    # 处理收到的文本消息,msg: 消息对象，包含接收到的文本
    def handle_text(self, msg):
        raise NotImplementedError
    # 统一的发送函数，每个Channel自行实现，根据回复的类型发送不同类型的消息
    def send(self, reply: Reply, context: Context):
        raise NotImplementedError
    # 构建回复内容，底层调用不同模型的聊天机器人回复文本消息
    def build_reply_content(self, query, context: Context = None) -> Reply:
        return Bridge().fetch_reply_content(query, context)
    # 将语音文件转为文本，底层调用语音转换成文本的不同的api
    def build_voice_to_text(self, voice_file) -> Reply:
        return Bridge().fetch_voice_to_text(voice_file)
    # 将文本转为语音
    def build_text_to_voice(self, text) -> Reply:
        return Bridge().fetch_text_to_voice(text)
