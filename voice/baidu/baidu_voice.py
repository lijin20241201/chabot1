"""
baidu voice service
"""
import json # 导入需要的库
import os
import time

from aip import AipSpeech  # 导入百度语音SDK

from bridge.reply import Reply, ReplyType  # 导入回复类，用于构建返回的消息
from common.log import logger
from common.tmp_dir import TmpDir
from config import conf # 导入配置读取方法
from voice.audio_convert import get_pcm_from_wav # 导入wav转pcm的函数
from voice.voice import Voice # 导入基类Voice
"""
    百度的语音识别API.
    dev_pid:
        - 1936: 普通话远场
        - 1536：普通话(支持简单的英文识别)
        - 1537：普通话(纯中文识别)
        - 1737：英语
        - 1637：粤语
        - 1837：四川话
    要使用本模块, 首先到 yuyin.baidu.com 注册一个开发者账号,
    之后创建一个新应用, 然后在应用管理的"查看key"中获得 API Key 和 Secret Key
    然后在 config.json 中填入这两个值, 以及 app_id, dev_pid
"""
class BaiduVoice(Voice): # BaiduVoice 类继承自Voice基类，提供百度语音识别和合成的功能
    def __init__(self):
        try:
            curdir = os.path.dirname(__file__) # 获取当前脚本所在的目录
            config_path = os.path.join(curdir, "config.json") # 配置文件路径
            bconf = None
            if not os.path.exists(config_path): # 如果配置文件不存在，则创建一个默认的配置文件
                bconf = {"lang": "zh", "ctp": 1, "spd": 5, "pit": 5, "vol": 5, "per": 0}
                with open(config_path, "w") as fw:
                    json.dump(bconf, fw, indent=4)
            else: # 如果配置文件存在，则读取配置文件
                with open(config_path, "r") as fr:
                    bconf = json.load(fr)
            # 从配置中获取API相关信息
            self.app_id = str(conf().get("baidu_app_id"))
            self.api_key = str(conf().get("baidu_api_key"))
            self.secret_key = str(conf().get("baidu_secret_key"))
            self.dev_id = conf().get("baidu_dev_pid") # dev_pid用于指定语言类型
            self.lang = bconf["lang"] # 设置语言
            self.ctp = bconf["ctp"] # 设置开发者标识
            self.spd = bconf["spd"]  # 设置语速
            self.pit = bconf["pit"] # 设置语调
            self.vol = bconf["vol"] # 设置音量
            self.per = bconf["per"] # 设置发音人
            # 初始化百度语音客户端
            self.client = AipSpeech(self.app_id, self.api_key, self.secret_key)
        except Exception as e:
            logger.warn("BaiduVoice init failed: %s, ignore " % e) # 出现异常时记录日志并忽略

    def voiceToText(self, voice_file):
        # 识别本地音频文件
        logger.debug("[Baidu] voice file name={}".format(voice_file)) # 输出调试日志，记录音频文件名
        pcm = get_pcm_from_wav(voice_file) # 将音频文件转换为pcm格式
        res = self.client.asr(pcm, "pcm", 16000, {"dev_pid": self.dev_id}) # 调用百度语音识别API
        if res["err_no"] == 0: # 判断是否识别成功
            logger.info("百度语音识别到了：{}".format(res["result"]))  # 输出识别结果日志
            text = "".join(res["result"]) # 将识别结果拼接成完整文本
            reply = Reply(ReplyType.TEXT, text) # 构建文本类型的回复对象
        else:
            logger.info("百度语音识别出错了: {}".format(res["err_msg"])) # 输出错误日志
            if res["err_msg"] == "request pv too much": # 如果超出请求限制
                logger.info("  出现这个原因很可能是你的百度语音服务调用量超出限制，或未开通付费")
            reply = Reply(ReplyType.ERROR, "百度语音识别出错了；{0}".format(res["err_msg"]))
        return reply

    def textToVoice(self, text):
        result = self.client.synthesis( # 调用语音合成客户端，将文本转换为语音
            text,  # 要转换的文本
            self.lang,  # 语言类型
            self.ctp, # 客户端类型
            {"spd": self.spd, "pit": self.pit, "vol": self.vol, "per": self.per},  # 语速、音调、音量、发音人等设置
        )
        # 如果返回的结果不是字典类型（意味着合成成功，返回的是音频数据）
        if not isinstance(result, dict):
            # 为了避免多线程中生成相同的文件名，使用当前时间戳和文本哈希值作为文件名
            fileName = TmpDir().path() + "reply-" + str(int(time.time())) + "-" + str(hash(text) & 0x7FFFFFFF) + ".mp3"
            with open(fileName, "wb") as f:   # 将语音数据写入文件
                f.write(result)
            logger.info("[Baidu] textToVoice text={} voice file name={}".format(text, fileName)) # 记录日志，输出合成结果文件名
            reply = Reply(ReplyType.VOICE, fileName) # 创建回复对象，包含语音文件路径
        else:
            logger.error("[Baidu] textToVoice error={}".format(result))  # 如果合成失败，记录错误信息并返回错误回复
            reply = Reply(ReplyType.ERROR, "抱歉，语音合成失败")
        return reply # 返回回复对象