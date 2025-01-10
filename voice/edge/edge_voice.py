import time

import edge_tts
import asyncio

from bridge.reply import Reply, ReplyType
from common.log import logger
from common.tmp_dir import TmpDir
from voice.voice import Voice


class EdgeVoice(Voice):

    def __init__(self):
        '''
        初始化语音设置，可以选择不同的发音人
        # 普通话
        zh-CN-XiaoxiaoNeural
        zh-CN-XiaoyiNeural
        zh-CN-YunjianNeural
        zh-CN-YunxiNeural
        zh-CN-YunxiaNeural
        zh-CN-YunyangNeural
        # 地方口音
        zh-CN-liaoning-XiaobeiNeural
        zh-CN-shaanxi-XiaoniNeural
        # 粤语
        zh-HK-HiuGaaiNeural
        zh-HK-HiuMaanNeural
        zh-HK-WanLungNeural
        # 湾湾腔
        zh-TW-HsiaoChenNeural
        zh-TW-HsiaoYuNeural
        zh-TW-YunJheNeural
        '''
        self.voice = "zh-CN-YunjianNeural" # 默认使用普通话“云剑”语音

    def voiceToText(self, voice_file): # 此函数暂未实现，计划用于语音转文本
        pass

    async def gen_voice(self, text, fileName):
        communicate = edge_tts.Communicate(text, self.voice) # 使用 edge_tts 库生成语音并保存为文件
        await communicate.save(fileName)  # 异步保存语音文件

    def textToVoice(self, text):
        # 为了避免多线程中生成相同的文件名，使用当前时间戳和文本哈希值生成唯一的文件名
        # hash() 是 Python 内建的函数，它返回一个对象的哈希值。
        fileName = TmpDir().path() + "reply-" + str(int(time.time())) + "-" + str(hash(text) & 0x7FFFFFFF) + ".mp3"
        asyncio.run(self.gen_voice(text, fileName)) # 调用异步生成语音的方法
        # 记录日志，输出生成的语音文件路径
        logger.info("[EdgeTTS] textToVoice text={} voice file name={}".format(text, fileName))
        return Reply(ReplyType.VOICE, fileName) # 返回包含语音文件路径的回复对象