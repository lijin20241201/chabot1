# 这个注释 有作用，它确保了文件在不同平台和不同 Python 版本下能正确读取文件内容，尤其是在处理非 ASCII 字符（如中文、特殊符号）时。
# 在 Python 3 中，尽管默认是 UTF-8，但显式声明编码仍然是一种好习惯，特别是在处理包含非 ASCII 字符的文件时。
# -*- coding: utf-8 -*-
import json
import os
import re
import time
from bridge.reply import Reply, ReplyType
from common.log import logger
from voice.audio_convert import get_pcm_from_wav
from voice.voice import Voice
from voice.ali.ali_api import AliyunTokenGenerator, speech_to_text_aliyun, text_to_speech_aliyun
from config import conf

class AliVoice(Voice):
    # 初始化AliVoice类，从配置文件加载必要的配置。
    def __init__(self):
        try:
            # __file__ 是当前脚本文件的路径（包括文件名），os.path.dirname(__file__) 则返回该文件所在的目录路径。换句话说，这一行获取了
            # 当前脚本所在的文件夹路径。
            curdir = os.path.dirname(__file__)
            # 这行代码将当前目录路径和 config.json 文件名合并，得到了 config.json 的完整路径。
            config_path = os.path.join(curdir, "config.json")
            # json.load(fr) 会解析 config.json 文件内容，并将其转换为 Python 字典对象。
            with open(config_path, "r") as fr:
                config = json.load(fr)
            self.token = None # 这个属性用于存储访问令牌（token）。
            # 这个属性存储 token 的过期时间，初始化为 0。通常，访问令牌在一段时间后会过期，因此 token_expire_time 可以用来判断当前 token 是否仍然有
            # 效。如果当前时间大于过期时间，就需要重新获取 token。
            self.token_expire_time = 0
            self.api_url_voice_to_text = config.get("api_url_voice_to_text") # 这个属性存储从配置文件中获取的 语音转文本 API 的 URL 地址。
            self.api_url_text_to_voice = config.get("api_url_text_to_voice") # 这个属性存储从配置文件中获取的 文本转语音 API 的 URL 地址。
            self.app_key = config.get("app_key") # 这个属性存储应用的 app_key，它是用于身份验证的一个重要参数
            # 这个属性存储 访问密钥 ID。访问密钥是访问云服务或 API 时必需的身份认证信息
            self.access_key_id = conf().get("qwen_access_key_id") or config.get("access_key_id")
            # 这个属性存储 访问密钥密钥（Access Key Secret）。这是与 access_key_id 配对使用的，用于进行身份认证和签名。
            self.access_key_secret = conf().get("qwen_access_key_secret") or config.get("access_key_secret")
        except Exception as e:
            logger.warn("AliVoice init failed: %s, ignore " % e)
    # 将文本转换为语音文件。param text: 要转换的文本。
    def textToVoice(self, text):
        # re.sub() 的作用是用 空字符串 替换不在正则表达式字符集中的字符，因此在这个例子中，它移除了 所有不符合要求的字符，保留了符合
        # 要求的字符（如字母、数字、中文、日文等）。
        text = re.sub(r'[^\u4e00-\u9fa5\u3040-\u30FF\uAC00-\uD7AFa-zA-Z0-9'
                      r'äöüÄÖÜáéíóúÁÉÍÓÚàèìòùÀÈÌÒÙâêîôûÂÊÎÔÛçÇñÑ，。！？,.]', '', text)
        # 提取有效的token
        token_id = self.get_valid_token()
        # 获取转换成的语音文件路径
        fileName = text_to_speech_aliyun(self.api_url_text_to_voice, text, self.app_key, token_id)
        if fileName:
            logger.info("[Ali] textToVoice text={} voice file name={}".format(text, fileName))
            # 创建回复
            reply = Reply(ReplyType.VOICE, fileName)
       # 如果返回None
        else:
            reply = Reply(ReplyType.ERROR, "抱歉，语音合成失败")
        # 返回一个Reply对象，其中包含转换得到的语音文件或错误信息。
        return reply
    # 将语音文件转换为文本。param voice_file: 要转换的语音文件。
    def voiceToText(self, voice_file):
        # 提取有效的token
        token_id = self.get_valid_token()
        logger.debug("[Ali] voice file name={}".format(voice_file))
        pcm = get_pcm_from_wav(voice_file) # 从 WAV 文件中提取 PCM数据。
        # 获取转换的结果
        text = speech_to_text_aliyun(self.api_url_voice_to_text, pcm, self.app_key, token_id)
        if text:
            logger.info("[Ali] VoicetoText = {}".format(text))
            reply = Reply(ReplyType.TEXT, text)
        else:
            reply = Reply(ReplyType.ERROR, "抱歉，语音识别失败")
        # 返回一个Reply对象，其中包含转换得到的文本或错误信息。
        return reply
    # 获取有效的阿里云token。
    def get_valid_token(self):
        current_time = time.time()
        # 如果token还没设定或者过期了
        if self.token is None or current_time >= self.token_expire_time:
            # 创建token生成器,获取token
            get_token = AliyunTokenGenerator(self.access_key_id, self.access_key_secret)
            token_str = get_token.get_token()
            token_data = json.loads(token_str) # 变成python字典形式
            self.token = token_data["Token"]["Id"] # 设置token
            # 将过期时间减少一小段时间（例如5分钟），以避免在边界条件下的过期
            self.token_expire_time = token_data["Token"]["ExpireTime"] - 300
            logger.debug(f"新获取的阿里云token：{self.token}")
        # 这种情况是存在token,也没过期
        else:
            logger.debug("使用缓存的token")
        return self.token # 返回有效的token字符串。