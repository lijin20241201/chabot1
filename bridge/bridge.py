from bot.bot_factory import create_bot
from bridge.context import Context
from bridge.reply import Reply
from common import const
from common.log import logger
from common.singleton import singleton
from config import conf
from translate.factory import create_translator
from voice.factory import create_voice

@singleton # 单例模式装饰器，确保该类的实例在整个程序中只有一个
class Bridge(object):
    def __init__(self):
        # 初始化 bot 类型字典，包含各种服务的默认值
        self.btype = {
            "chat": const.CHATGPT,
            "voice_to_text": conf().get("voice_to_text", "openai"),
            "text_to_voice": conf().get("text_to_voice", "google"),
            "translate": conf().get("translate", "baidu"),
        }
        # 根据配置文件中的 `bot_type` 设置聊天模型类型
        bot_type = conf().get("bot_type")
        if bot_type:
            self.btype["chat"] = bot_type # 如果配置有bot_type，则覆盖默认的chat模型
        else:
            # 如果没有bot_type，从配置中获取其他模型类型进行设置
            model_type = conf().get("model") or const.GPT35
            # 根据不同的模型类型设置对应的聊天模型
            if model_type in ["text-davinci-003"]:
                self.btype["chat"] = const.OPEN_AI
            if conf().get("use_azure_chatgpt", False):
                self.btype["chat"] = const.CHATGPTONAZURE
            if model_type in ["wenxin", "wenxin-4"]:
                self.btype["chat"] = const.BAIDU
            if model_type in ["xunfei"]:
                self.btype["chat"] = const.XUNFEI
            if model_type in [const.QWEN]:
                self.btype["chat"] = const.QWEN
            if model_type in [const.QWEN_TURBO, const.QWEN_PLUS, const.QWEN_MAX]:
                self.btype["chat"] = const.QWEN_DASHSCOPE
            if model_type and model_type.startswith("gemini"):
                self.btype["chat"] = const.GEMINI
            if model_type and model_type.startswith("glm"):
                self.btype["chat"] = const.ZHIPU_AI
            if model_type and model_type.startswith("claude-3"):
                self.btype["chat"] = const.CLAUDEAPI
            if model_type in ["claude"]:
                self.btype["chat"] = const.CLAUDEAI

            if model_type in [const.MOONSHOT, "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]:
                self.btype["chat"] = const.MOONSHOT

            if model_type in ["abab6.5-chat"]:
                self.btype["chat"] = const.MiniMax
            # 如果配置了LinkAI，则相应的服务也使用LinkAI
            if conf().get("use_linkai") and conf().get("linkai_api_key"):
                self.btype["chat"] = const.LINKAI
                # 如果没有配置voice_to_text,或者配置的语音转文本是openai
                if not conf().get("voice_to_text") or conf().get("voice_to_text") in ["openai"]:
                    self.btype["voice_to_text"] = const.LINKAI
                if not conf().get("text_to_voice") or conf().get("text_to_voice") in ["openai", const.TTS_1, const.TTS_1_HD]:
                    self.btype["text_to_voice"] = const.LINKAI
        self.bots = {} # 存储已创建的 bot 实例
        self.chat_bots = {} # 存储已创建的聊天 bot 实例

    # 获取并返回指定类型的 bot 实例
    def get_bot(self, typename):
        if self.bots.get(typename) is None: # 如果还没有创建过该类型的 bot
            logger.info("create bot {} for {}".format(self.btype[typename], typename))
            if typename == "text_to_voice":
                self.bots[typename] = create_voice(self.btype[typename]) # 创建文本转语音 bot
            elif typename == "voice_to_text": 
                self.bots[typename] = create_voice(self.btype[typename]) # 创建语音转文本 bot
            elif typename == "chat":
                self.bots[typename] = create_bot(self.btype[typename]) # 创建聊天 bot
            elif typename == "translate":
                self.bots[typename] = create_translator(self.btype[typename]) # 创建翻译 bot
        return self.bots[typename]  # 返回已经创建的 bot 实例

    def get_bot_type(self, typename): # 获取指定类型的 bot 所使用的服务类型
        return self.btype[typename]

    def fetch_reply_content(self, query, context: Context) -> Reply: # 获取聊天机器人回复内容
        return self.get_bot("chat").reply(query, context)

    def fetch_voice_to_text(self, voiceFile) -> Reply: # 获取语音转文本的结果
        return self.get_bot("voice_to_text").voiceToText(voiceFile)

    def fetch_text_to_voice(self, text) -> Reply: # 获取文本转语音的结果
        return self.get_bot("text_to_voice").textToVoice(text)

    def fetch_translate(self, text, from_lang="", to_lang="en") -> Reply: # 获取翻译结果
        return self.get_bot("translate").translate(text, from_lang, to_lang)
    # 获取指定类型的聊天机器人实例
    def find_chat_bot(self, bot_type: str):
        if self.chat_bots.get(bot_type) is None:
            self.chat_bots[bot_type] = create_bot(bot_type)
        return self.chat_bots.get(bot_type)
    # 重新初始化
    def reset_bot(self):
        self.__init__() # 通过重新调用构造函数来重置整个对象
