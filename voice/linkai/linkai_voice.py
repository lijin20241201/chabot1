import random # 导入random模块，用于生成随机数
import requests # 导入requests模块，用于发送HTTP请求
from voice import audio_convert # 从voice模块中导入audio_convert，用于音频文件转换
from bridge.reply import Reply, ReplyType # 从bridge模块中导入Reply类和ReplyType枚举，用于构建回复对象
from common.log import logger # 从common.log模块中导入logger对象，用于记录日志
from config import conf # 从config模块中导入conf函数，用于获取配置
from voice.voice import Voice # 从voice.voice模块中导入Voice类，作为基类
from common import const # 从common模块中导入const常量，包含一些常用的常量
import os  # 导入os模块，用于文件操作
import datetime # 导入datetime模块，用于获取当前时间

class LinkAIVoice(Voice): # 定义继承自Voice类的LinkAIVoice类，用于语音转换功能
    def __init__(self):
        pass # 初始化方法，这里不执行任何操作

    def voiceToText(self, voice_file): # 定义语音转文本方法
        logger.debug("[LinkVoice] voice file name={}".format(voice_file))  # 记录传入的语音文件名
        try:
             # 获取API的基本URL，并拼接成完整的请求URL
            url = conf().get("linkai_api_base", "https://api.link-ai.tech") + "/v1/audio/transcriptions"
            # 获取API请求需要的Authorization头
            headers = {"Authorization": "Bearer " + conf().get("linkai_api_key")}
            model = None # 初始化语音识别模型为None
            # 判断是否使用OpenAI的模型
            if not conf().get("text_to_voice") or conf().get("voice_to_text") == "openai":
                model = const.WHISPER_1 # 如果配置使用OpenAI，设置模型为WHISPER_1
            if voice_file.endswith(".amr"): # 如果语音文件是.amr格式，则需要转换为.mp3
                try:
                    mp3_file = os.path.splitext(voice_file)[0] + ".mp3" # 生成转换后的MP3文件名
                    audio_convert.any_to_mp3(voice_file, mp3_file) # 调用音频转换方法
                    voice_file = mp3_file # 更新文件路径为转换后的MP3文件
                except Exception as e:
                    # 如果转换失败，记录警告并直接发送AMR文件
                    logger.warn(f"[LinkVoice] amr file transfer failed, directly send amr voice file: {format(e)}")
            file = open(voice_file, "rb")  # 打开语音文件（以二进制读取）
            file_body = {
                "file": file  # 包装语音文件数据
            }
            data = {
                "model": model # 配置使用的语音识别模型
            }
            # 发送POST请求到API进行语音识别
            res = requests.post(url, files=file_body, headers=headers, data=data, timeout=(5, 60))
            if res.status_code == 200: # 如果请求成功（状态码200）
                text = res.json().get("text") # 获取返回的文本结果
            else:
                res_json = res.json()  # 获取错误信息
                logger.error(f"[LinkVoice] voiceToText error, status_code={res.status_code}, msg={res_json.get('message')}")
                return None # 返回None，表示失败
            reply = Reply(ReplyType.TEXT, text) # 创建一个文本回复对象
            logger.info(f"[LinkVoice] voiceToText success, text={text}, file name={voice_file}") # 记录成功日志
        except Exception as e: 
            logger.error(e) # 记录异常日志
            return None # 返回None，表示出现异常
        return reply # 返回回复对象

    def textToVoice(self, text):  # 定义文本转语音方法
        try:
            # 获取API的基本URL，并拼接成完整的请求URL
            url = conf().get("linkai_api_base", "https://api.link-ai.tech") + "/v1/audio/speech"
            headers = {"Authorization": "Bearer " + conf().get("linkai_api_key")} # 获取API请求需要的Authorization头
            model = const.TTS_1  # 默认选择TTS_1语音模型
            # 如果配置中没有指定或选择OpenAI模型，则使用TTS_1模型
            if not conf().get("text_to_voice") or conf().get("text_to_voice") in ["openai", const.TTS_1, const.TTS_1_HD]:
                model = conf().get("text_to_voice_model") or const.TTS_1 # 如果没有配置文本转语音模型，则使用默认模型TTS_1
            data = { # 准备请求的参数
                "model": model,
                "input": text, # 要转换的文本
                "voice": conf().get("tts_voice_id"),  # 选择的语音ID
                "app_code": conf().get("linkai_app_code") # 应用代码
            }
            # 发送POST请求到API进行文本转语音
            res = requests.post(url, headers=headers, json=data, timeout=(5, 120))
            if res.status_code == 200:  # 如果请求成功（状态码200）
                # 生成一个临时文件名，并保存语音文件
                tmp_file_name = "tmp/" + datetime.datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(0, 1000)) + ".mp3"
                with open(tmp_file_name, 'wb') as f:
                    f.write(res.content) # 将返回的音频内容写入文件
                reply = Reply(ReplyType.VOICE, tmp_file_name) # 创建一个语音回复对象
                logger.info(f"[LinkVoice] textToVoice success, input={text}, model={model}, voice_id={data.get('voice')}")
                return reply # 返回语音回复对象
            else:  # 获取错误信息
                res_json = res.json()
                logger.error(f"[LinkVoice] textToVoice error, status_code={res.status_code}, msg={res_json.get('message')}")
                return None # 返回None，表示失败
        except Exception as e:
            logger.error(e) # 记录异常日志
            # reply = Reply(ReplyType.ERROR, "遇到了一点小问题，请稍后再问我吧") 
            return None # 返回None，表示出现异常
