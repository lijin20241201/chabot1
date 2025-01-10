import time # 导入time模块，用于获取当前时间戳

from elevenlabs.client import ElevenLabs # 从elevenlabs库中导入ElevenLabs类
from elevenlabs import save # 从elevenlabs库中导入save函数，用于保存生成的音频文件
from bridge.reply import Reply, ReplyType # 从bridge模块中导入Reply类和ReplyType枚举，用于构建回复对象
from common.log import logger
from common.tmp_dir import TmpDir
from voice.voice import Voice # 从voice.voice模块中导入Voice类，作为基类
from config import conf

XI_API_KEY = conf().get("xi_api_key") # 从配置文件中获取API密钥
client = ElevenLabs(api_key=XI_API_KEY) # 使用API密钥初始化ElevenLabs客户端
name = conf().get("xi_voice_id") # 从配置文件中获取语音ID

class ElevenLabsVoice(Voice):  # 创建一个继承自Voice类的ElevenLabsVoice类

    def __init__(self):
        pass  # 初始化方法，这里没有做任何操作

    def voiceToText(self, voice_file): # 定义将语音转文本的方法，但当前未实现
        pass

    def textToVoice(self, text):  # 定义将文本转语音的方法
        audio = client.generate( # 使用ElevenLabs客户端生成语音
            text=text, # 传入的文本
            voice=name, # 使用配置中的语音ID
            model='eleven_multilingual_v2'  # 使用特定的语音模型
        )
        # 生成音频文件的名称，包含当前时间戳和文本的哈希值（确保文件名唯一）
        fileName = TmpDir().path() + "reply-" + str(int(time.time())) + "-" + str(hash(text) & 0x7FFFFFFF) + ".mp3"
        save(audio, fileName) # 保存生成的音频文件到临时目录
        # 记录日志，显示传入的文本和生成语音文件的文件名
        logger.info("[ElevenLabs] textToVoice text={} voice file name={}".format(text, fileName))
        return Reply(ReplyType.VOICE, fileName) # 返回一个包含音频文件路径的Reply对象，类型为VOICE