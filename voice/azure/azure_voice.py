"""
azure voice service
"""
import json  # 导入 JSON 库，用于处理 JSON 格式的数据
import os # 导入 OS 库，用于处理文件路径和操作文件系统
import time # 导入时间库，用于生成唯一的文件名

import azure.cognitiveservices.speech as speechsdk # 导入 Azure 语音 SDK，提供语音识别和语音合成服务
from langid import classify # 导入 langid 库，用于语言自动识别
 
from bridge.reply import Reply, ReplyType # 导入回复类和回复类型，用于构建响应
from common.log import logger # 导入日志模块，用于记录日志
from common.tmp_dir import TmpDir  # 导入临时目录工具，用于生成临时文件
from config import conf # 导入配置文件管理模块，用于加载配置信息
from voice.voice import Voice  # 导入父类 Voice，作为各类语音服务的基类
"""
Azure voice
主目录设置文件中需填写azure_voice_api_key和azure_voice_region
查看可用的 voice： https://speech.microsoft.com/portal/voicegallery
"""
class AzureVoice(Voice): # 创建 AzureVoice 类，继承自 Voice 类
    def __init__(self):
        try:
            curdir = os.path.dirname(__file__) # 获取当前文件所在的目录路径
            config_path = os.path.join(curdir, "config.json") # 配置文件的路径
            config = None
            if not os.path.exists(config_path):  # 如果配置文件不存在，创建一个默认配置文件
                config = {
                    "speech_synthesis_voice_name": "zh-CN-XiaoxiaoNeural",  # 默认语音合成语音
                    "auto_detect": True,  # 是否启用自动语言检测
                    "speech_synthesis_zh": "zh-CN-XiaozhenNeural", # 中文语音合成
                    "speech_synthesis_en": "en-US-JacobNeural", # 英文语音合成
                    "speech_synthesis_ja": "ja-JP-AoiNeural",  # 日语语音合成
                    "speech_synthesis_ko": "ko-KR-SoonBokNeural", # 韩语语音合成
                    "speech_synthesis_de": "de-DE-LouisaNeural", # 德语语音合成
                    "speech_synthesis_fr": "fr-FR-BrigitteNeural",  # 法语语音合成
                    "speech_synthesis_es": "es-ES-LaiaNeural", # 西班牙语语音合成
                    "speech_recognition_language": "zh-CN", # 默认语音识别语言为中文
                }
                with open(config_path, "w") as fw:  # 如果配置文件不存在，则创建并写入默认配置
                    json.dump(config, fw, indent=4)
            else:  # 如果配置文件存在，则读取配置
                with open(config_path, "r") as fr:
                    config = json.load(fr)
            self.config = config  # 将配置保存到实例属性
            self.api_key = conf().get("azure_voice_api_key") # 获取 Azure API Key
            self.api_region = conf().get("azure_voice_region") # 获取 Azure 区域信息
            # 初始化 Azure 语音配置
            self.speech_config = speechsdk.SpeechConfig(subscription=self.api_key, region=self.api_region)
            self.speech_config.speech_synthesis_voice_name = self.config["speech_synthesis_voice_name"] # 设置语音合成默认语音
            self.speech_config.speech_recognition_language = self.config["speech_recognition_language"] # 设置语音识别默认语言
        except Exception as e:
            logger.warn("AzureVoice init failed: %s, ignore " % e) # 如果初始化出错，记录警告日志

    def voiceToText(self, voice_file):  # 定义语音转文本的方法
        audio_config = speechsdk.AudioConfig(filename=voice_file) # 配置音频文件输入
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=audio_config)  # 创建语音识别器
        result = speech_recognizer.recognize_once() # 调用识别方法识别音频文件
        if result.reason == speechsdk.ResultReason.RecognizedSpeech: # 如果识别成功
            logger.info("[Azure] voiceToText voice file name={} text={}".format(voice_file, result.text)) # 输出日志，记录识别结果
            reply = Reply(ReplyType.TEXT, result.text) # 返回识别到的文本
        else: # 如果识别失败
            cancel_details = result.cancellation_details # 获取取消的详细信息
            logger.error("[Azure] voiceToText error, result={}, errordetails={}".format(result, cancel_details)) # 输出错误日志
            reply = Reply(ReplyType.ERROR, "抱歉，语音识别失败") # 返回失败的错误信息
        return reply # 返回回复对象

    def textToVoice(self, text):  # 定义文本转语音的方法
        if self.config.get("auto_detect"):  # 如果启用了语言自动检测
            lang = classify(text)[0] # 使用 langid 库检测文本的语言
            key = "speech_synthesis_" + lang # 根据语言选择对应的语音合成模型
            if key in self.config: # 如果配置中存在该语言的语音模型
                # 输出日志，记录自动检测到的语言和语音模型
                logger.info("[Azure] textToVoice auto detect language={}, voice={}".format(lang, self.config[key]))
                self.speech_config.speech_synthesis_voice_name = self.config[key] # 设置对应语言的语音模型
            else: # 如果没有该语言模型，则使用默认模型
                self.speech_config.speech_synthesis_voice_name = self.config["speech_synthesis_voice_name"]
        else: # 如果没有启用自动检测，使用默认语音模型
            self.speech_config.speech_synthesis_voice_name = self.config["speech_synthesis_voice_name"]
        # 生成唯一的文件名，避免多线程时文件名重复
        fileName = TmpDir().path() + "reply-" + str(int(time.time())) + "-" + str(hash(text) & 0x7FFFFFFF) + ".wav"
        audio_config = speechsdk.AudioConfig(filename=fileName)  # 配置输出音频文件
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=audio_config) # 创建语音合成器
        result = speech_synthesizer.speak_text(text) # 合成语音
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted: # 如果语音合成成功
            logger.info("[Azure] textToVoice text={} voice file name={}".format(text, fileName)) # 输出日志，记录合成的语音文件路径
            reply = Reply(ReplyType.VOICE, fileName) # 返回合成的语音文件路径
        else: # 如果语音合成失败
            cancel_details = result.cancellation_details # 获取取消的详细信息
            # 输出错误日志
            logger.error("[Azure] textToVoice error, result={}, errordetails={}".format(result, cancel_details.error_details))
            reply = Reply(ReplyType.ERROR, "抱歉，语音合成失败") # 返回失败的错误信息
        return reply # 返回回复对象