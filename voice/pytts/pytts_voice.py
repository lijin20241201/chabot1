"""
pytts voice service (offline)
"""

import os
import sys
import time

import pyttsx3 # 导入pyttsx3库，用于实现离线语音合成功能

from bridge.reply import Reply, ReplyType
from common.log import logger
from common.tmp_dir import TmpDir
from voice.voice import Voice


class PyttsVoice(Voice): # 定义PyttsVoice类，继承自Voice类，表示使用pyttsx3实现的离线语音服务
    engine = pyttsx3.init() # 初始化pyttsx3语音合成引擎，返回一个引擎实例

    def __init__(self): # 初始化方法
        # 语速设置为125
        self.engine.setProperty("rate", 125)  # 设置语音的语速
        # 音量设置为最大值1.0
        self.engine.setProperty("volume", 1.0) # 设置音量为最大
        if sys.platform == "win32":  # 如果操作系统是Windows
            # 遍历所有语音，选择包含“Chinese”的语音
            for voice in self.engine.getProperty("voices"):
                if "Chinese" in voice.name: # 如果语音名称中包含"Chinese"
                    self.engine.setProperty("voice", voice.id) # 设置语音为该中文语音
        else:
            # 如果不是Windows，则选择“zh”语音
            self.engine.setProperty("voice", "zh") # 设置语音为中文（zh）
            # 如果espeak的问题解决，可以使用runAndWait()方法
            # TODO: 检查是否能在win32上工作
            self.engine.startLoop(useDriverLoop=False) # 启动引擎，避免使用driver loop（用于非Windows平台）

    def textToVoice(self, text):  # 定义文本转语音方法
        try:
            # 避免多线程下生成相同的文件名
            wavFileName = "reply-" + str(int(time.time())) + "-" + str(hash(text) & 0x7FFFFFFF) + ".wav"  # 生成唯一的文件名
            wavFile = TmpDir().path() + wavFileName  # 获取临时目录并拼接文件名
            logger.info("[Pytts] textToVoice text={} voice file name={}".format(text, wavFile))  # 记录生成语音的文本和文件名
            # 使用pyttsx3将文本保存为语音文件
            self.engine.save_to_file(text, wavFile) # 将文本转换为语音并保存到指定文件

            if sys.platform == "win32": # 如果操作系统是Windows
                self.engine.runAndWait()  # 等待语音合成完成（Windows下使用runAndWait方法）
            else:
                # 在Ubuntu等系统上，runAndWait()并不会等到文件生成完成，因此手动控制等待
                # 在espeak修复之前，我们通过迭代生成器并控制等待来解决这个问题
                self.engine.iterate()  # 迭代pyttsx3引擎任务队列
                while self.engine.isBusy() or wavFileName not in os.listdir(TmpDir().path()): # 等待任务完成并确保文件生成
                    time.sleep(0.1) # 每0.1秒检查一次

            reply = Reply(ReplyType.VOICE, wavFile) # 创建一个语音回复对象，包含生成的语音文件路径

        except Exception as e:  # 如果发生异常
            reply = Reply(ReplyType.ERROR, str(e)) # 返回错误信息作为回复
        finally:
            return reply # 返回语音或错误回复对象
