import time # 导入时间模块，用于生成唯一的文件名

import speech_recognition  # 导入语音识别库，用于语音转文本
from gtts import gTTS # 导入 gTTS 库，用于文本转语音

from bridge.reply import Reply, ReplyType # 导入回复类和回复类型，用于构建响应
from common.log import logger  # 导入日志模块，用于日志记录
from common.tmp_dir import TmpDir # 导入临时目录管理工具，用于处理临时文件
from voice.voice import Voice # 导入父类 Voice，可能是其他语音服务的基类


class GoogleVoice(Voice): # 创建 GoogleVoice 类，继承自 Voice 类
    recognizer = speech_recognition.Recognizer() # 创建语音识别器实例，recognizer 用于处理语音识别任务

    def __init__(self): # 构造函数，暂时没有初始化操作
        pass

    def voiceToText(self, voice_file): # 定义语音转文本的函数
        with speech_recognition.AudioFile(voice_file) as source: # 使用语音文件作为音频源
            audio = self.recognizer.record(source)  # 从音频源中录制音频数据
        try:
            text = self.recognizer.recognize_google(audio, language="zh-CN") # 使用 Google 的语音识别服务将音频转为文本，指定语言为中文
            logger.info("[Google] voiceToText text={} voice file name={}".format(text, voice_file))  # 记录日志，输出识别到的文本及文件名
            reply = Reply(ReplyType.TEXT, text) # 创建文本类型的回复对象，返回识别出的文本
        except speech_recognition.UnknownValueError:  # 如果无法理解语音（如噪音或不清楚）
            reply = Reply(ReplyType.ERROR, "抱歉，我听不懂") # 返回错误类型的回复，表示无法识别语音
        except speech_recognition.RequestError as e: # 如果请求 Google 语音识别服务失败（如网络问题）
            reply = Reply(ReplyType.ERROR, "抱歉，无法连接到 Google 语音识别服务；{0}".format(e)) # 返回错误类型的回复，表示无法连接到服务
        finally:
            return reply # 返回回复对象，不论是否出错

    def textToVoice(self, text): # 定义文本转语音的函数
        try:
            # 使用时间戳和文本哈希生成唯一的文件名，避免多线程下文件名冲突
            mp3File = TmpDir().path() + "reply-" + str(int(time.time())) + "-" + str(hash(text) & 0x7FFFFFFF) + ".mp3"
            tts = gTTS(text=text, lang="zh") # 使用 gTTS 库将文本转换为语音，指定语言为中文
            tts.save(mp3File) # 将转换后的语音保存为 MP3 文件
            logger.info("[Google] textToVoice text={} voice file name={}".format(text, mp3File)) # 记录日志，输出生成的语音文件路径
            reply = Reply(ReplyType.VOICE, mp3File)  # 创建语音类型的回复对象，返回生成的语音文件路径
        except Exception as e: # 如果转换过程出现异常（如文件保存失败等）
            reply = Reply(ReplyType.ERROR, str(e)) # 返回错误类型的回复，表示发生异常并返回异常信息
        finally:
            return reply  # 返回回复对象，不论是否出错