#####################################################################
#    xunfei voice service
#     Auth: njnuko
#     Email: njnuko@163.com
#
#    要使用本模块, 首先到 xfyun.cn 注册一个开发者账号,
#    之后创建一个新应用, 然后在应用管理的语音识别或者语音合同右边可以查看APPID API Key 和 Secret Key
#    然后在 config.json 中填入这三个值
#
#    配置说明：
# {
#  "APPID":"xxx71xxx",
#  "APIKey":"xxxx69058exxxxxx",  #讯飞xfyun.cn控制台语音合成或者听写界面的APIKey
#  "APISecret":"xxxx697f0xxxxxx",  #讯飞xfyun.cn控制台语音合成或者听写界面的APIKey
#  "BusinessArgsTTS":{"aue": "lame", "sfl": 1, "auf": "audio/L16;rate=16000", "vcn": "xiaoyan", "tte": "utf8"}, #语音合成的参数，具体可以参考xfyun.cn的文档
#  "BusinessArgsASR":{"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vad_eos":10000, "dwa": "wpgs"}  #语音听写的参数，具体可以参考xfyun.cn的文档
# }
#####################################################################

import json
import os
import time

from bridge.reply import Reply, ReplyType
from common.log import logger
from common.tmp_dir import TmpDir
from config import conf
from voice.voice import Voice # 导入Voice类，继承此类以实现具体的语音功能
from .xunfei_asr import xunfei_asr # 导入讯飞语音识别（ASR）功能
from .xunfei_tts import xunfei_tts  # 导入讯飞文本转语音（TTS）功能
from voice.audio_convert import any_to_mp3 # 导入音频转换工具（例如：wav转mp3）
import shutil # 导入shutil模块，用于文件操作
from pydub import AudioSegment # 导入pydub库，用于音频文件操作，转换格式等

# 定义XunfeiVoice类，继承Voice类，实现具体的语音识别和合成功能
class XunfeiVoice(Voice):
    def __init__(self):
        try:
            curdir = os.path.dirname(__file__) # 获取当前文件夹路径
            config_path = os.path.join(curdir, "config.json") # 拼接配置文件路径
            conf = None
            with open(config_path, "r") as fr: # 打开并加载配置文件
                conf = json.load(fr)
            print(conf)
            self.APPID = str(conf.get("APPID")) # 获取配置中的API信息
            self.APIKey = str(conf.get("APIKey"))
            self.APISecret = str(conf.get("APISecret"))
            self.BusinessArgsTTS = conf.get("BusinessArgsTTS")  # 获取TTS业务参数
            self.BusinessArgsASR= conf.get("BusinessArgsASR")  # 获取ASR业务参数

        except Exception as e: # 如果初始化失败，打印警告日志
            logger.warn("XunfeiVoice init failed: %s, ignore " % e)
    # 语音转文本的实现
    def voiceToText(self, voice_file):
        # 识别本地文件
        try:
            logger.debug("[Xunfei] voice file name={}".format(voice_file)) # 打印日志，显示接收到的语音文件
            #print("voice_file===========",voice_file)
            #print("voice_file_type===========",type(voice_file))
            #mp3_name, file_extension = os.path.splitext(voice_file)
            #mp3_file = mp3_name + ".mp3"
            #pcm_data=get_pcm_from_wav(voice_file)
            #mp3_name, file_extension = os.path.splitext(voice_file)
            #AudioSegment.from_wav(voice_file).export(mp3_file, format="mp3")
            #shutil.copy2(voice_file, 'tmp/test1.wav')
            #shutil.copy2(mp3_file, 'tmp/test1.mp3')
            #print("voice and mp3 file",voice_file,mp3_file)
            # 调用讯飞的语音识别功能，将语音文件转为文本
            text = xunfei_asr(self.APPID,self.APISecret,self.APIKey,self.BusinessArgsASR,voice_file)
            logger.info("讯飞语音识别到了: {}".format(text)) # 打印识别结果
            reply = Reply(ReplyType.TEXT, text) # 返回文本结果
        except Exception as e:
            # 如果识别失败，打印警告日志，并返回错误信息
            logger.warn("XunfeiVoice init failed: %s, ignore " % e)
            reply = Reply(ReplyType.ERROR, "讯飞语音识别出错了；{0}")
        return reply
    # 文本转语音的实现
    def textToVoice(self, text):
        try:
            # 生成一个唯一的文件名，避免多线程情况下文件名冲突
            fileName = TmpDir().path() + "reply-" + str(int(time.time())) + "-" + str(hash(text) & 0x7FFFFFFF) + ".mp3"
            # 调用讯飞的TTS功能，将文本转为语音文件
            return_file = xunfei_tts(self.APPID,self.APIKey,self.APISecret,self.BusinessArgsTTS,text,fileName)
            # 打印日志，显示生成的语音文件路径
            logger.info("[Xunfei] textToVoice text={} voice file name={}".format(text, fileName))
            reply = Reply(ReplyType.VOICE, fileName) # 返回语音文件的路径作为回复
        except Exception as e: # 如果生成语音失败，打印错误日志，并返回错误信息
            logger.error("[Xunfei] textToVoice error={}".format(fileName))
            reply = Reply(ReplyType.ERROR, "抱歉，讯飞语音合成失败")
        return reply
