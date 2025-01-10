import json

import openai

from bridge.reply import Reply, ReplyType # 引入回复类型和回复类
from common.log import logger  # 引入日志模块
from config import conf # 引入配置
from voice.voice import Voice  # 引入语音相关的父类
import requests # 引入HTTP请求库
from common import const # 引入常量定义
import datetime, random # 引入日期时间和随机数模块

class OpenaiVoice(Voice):
    def __init__(self):
        openai.api_key = conf().get("open_ai_api_key")  # 初始化时配置 OpenAI API 密钥
    # 语音转文本
    def voiceToText(self, voice_file):
        logger.debug("[Openai] voice file name={}".format(voice_file)) # 输出调试日志，记录语音文件名
        try:
            file = open(voice_file, "rb") # 以二进制读取方式打开语音文件
            api_base = conf().get("open_ai_api_base") or "https://api.openai.com/v1" # 获取 OpenAI API 基本地址
            url = f'{api_base}/audio/transcriptions' # 设置请求的URL地址，调用Whisper模型进行语音转文字
            headers = {
                'Authorization': 'Bearer ' + conf().get("open_ai_api_key"),  # 设置授权头
                # 'Content-Type': 'multipart/form-data' # 加了会报错，不知道什么原因
            }
            files = {
                "file": file, # 要上传的语音文件
            }
            data = {
                "model": "whisper-1",  # 使用Whisper模型进行转录
            }
            # 发起HTTP POST请求，传递文件和参数
            response = requests.post(url, headers=headers, files=files, data=data)
            response_data = response.json() # 获取响应数据并转换为JSON格式
            text = response_data['text']  # 从响应数据中提取转录的文本
            reply = Reply(ReplyType.TEXT, text)  # 创建文本类型的回复对象
            logger.info("[Openai] voiceToText text={} voice file name={}".format(text, voice_file)) # 输出日志，记录转录后的文本
        except Exception as e:
            reply = Reply(ReplyType.ERROR, "我暂时还无法听清您的语音，请稍后再试吧~") # 出现异常时，返回错误信息
        finally:
            return reply # 返回回复对象

    # 文本转语音
    def textToVoice(self, text):
        try:
            api_base = conf().get("open_ai_api_base") or "https://api.openai.com/v1"  # 获取 OpenAI API 基本地址
            url = f'{api_base}/audio/speech' # 设置请求的URL地址，调用文本转语音接口
            headers = {
                'Authorization': 'Bearer ' + conf().get("open_ai_api_key"), # 设置授权头
                'Content-Type': 'application/json'  # 设置请求内容类型为JSON
            }
            data = { # 请求参数，指定模型、输入文本和语音类型
                'model': conf().get("text_to_voice_model") or const.TTS_1,   # 获取或默认使用TTS模型
                'input': text, # 输入的文本
                'voice': conf().get("tts_voice_id") or "alloy"  # 语音ID，默认为"alloy"
            }
            # 发起HTTP POST请求，传递JSON数据
            response = requests.post(url, headers=headers, json=data)
            # 构造文件名，保存生成的语音文件
            file_name = "tmp/" + datetime.datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(0, 1000)) + ".mp3"
            logger.debug(f"[OPENAI] text_to_Voice file_name={file_name}, input={text}")  # 输出调试日志，记录生成的语音文件名
            with open(file_name, 'wb') as f:
                f.write(response.content) # 将返回的音频数据写入文件
            logger.info(f"[OPENAI] text_to_Voice success") # 输出日志，表示文本转语音成功
            reply = Reply(ReplyType.VOICE, file_name) # 创建语音类型的回复对象，返回音频文件名
        except Exception as e:  # 记录错误日志
            logger.error(e)
            reply = Reply(ReplyType.ERROR, "遇到了一点小问题，请稍后再问我吧") # 出现异常时，返回错误信息
        finally:
            return reply # 返回回复对象