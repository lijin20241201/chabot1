# encoding:utf-8
import time
import openai
import openai.error
from bot.bot import Bot
from bot.openai.open_ai_image import OpenAIImage # 导入OpenAI图像生成类
from bot.openai.open_ai_session import OpenAISession
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf

user_session = dict()  # 全局变量，用于存储所有用户会话

# # 定义OpenAIBot类，用于处理文本和图像生成请求
class OpenAIBot(Bot, OpenAIImage):
    def __init__(self):
        super().__init__() # 调用父类初始化方法
        openai.api_key = conf().get("open_ai_api_key") # 设置OpenAI API密钥
        if conf().get("open_ai_api_base"): # 如果配置了自定义API地址，进行设置
            openai.api_base = conf().get("open_ai_api_base")
        proxy = conf().get("proxy") # 获取代理配置
        if proxy:
            openai.proxy = proxy # 设置代理
        # 初始化会话管理器，指定会话类和默认模型
        self.sessions = SessionManager(OpenAISession, model=conf().get("model") or "text-davinci-003")
        # 初始化OpenAI API请求参数
        self.args = {
            "model": conf().get("model") or "text-davinci-003",  # 使用的模型名称
            "temperature": conf().get("temperature", 0.9),  # 回复的随机性，越高越随机
            "max_tokens": 1200,   # 回复的最大长度
            "top_p": 1, # 控制采样的范围
            "frequency_penalty": conf().get("frequency_penalty", 0.0),  # [-2,2]之间，该值越大则更倾向于产生不同的内容
            "presence_penalty": conf().get("presence_penalty", 0.0),  # [-2,2]之间，该值越大则更倾向于产生不同的内容
            "request_timeout": conf().get("request_timeout", None),  # 请求超时时间
            "timeout": conf().get("request_timeout", None),  # 重试的超时时间
            "stop": ["\n\n\n"],  # 设置停止符号，控制生成的结束点
        }
    # 处理用户请求的主方法
    def reply(self, query, context=None):
        if context and context.type: # 如果有消息且类型已定义
            if context.type == ContextType.TEXT: # 如果是文本请求
                logger.info("[OPEN_AI] query={}".format(query)) # 记录请求日志
                session_id = context["session_id"]  # 获取会话ID
                reply = None
                if query == "#清除记忆": # 清除当前会话记忆
                    self.sessions.clear_session(session_id) # 从会话字典中删除指定会话
                    reply = Reply(ReplyType.INFO, "记忆已清除")
                elif query == "#清除所有":  # 清除所有会话记忆
                    self.sessions.clear_all_session()
                    reply = Reply(ReplyType.INFO, "所有人记忆已清除")
                else:  # 普通文本请求
                    # 构建会话并添加用户消息到消息列表中
                    session = self.sessions.session_query(query, session_id)
                    result = self.reply_text(session)  # 调用方法获取回复
                    total_tokens, completion_tokens, reply_content = (
                        result["total_tokens"], # 消息列表和新回复的总token数
                        result["completion_tokens"], # 助手新生成的回复的token数
                        result["content"], # 助手回复
                    )
                    # 打印调试信息,记录消息列表,当前会话id,助手回复,助手回复的token数
                    logger.debug(
                        "[OPEN_AI] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                            str(session), session_id, reply_content, completion_tokens)
                    )
                    if total_tokens == 0: # 如果总Token为0，表示出现异常
                        reply = Reply(ReplyType.ERROR, reply_content)
                    else: # 这个是正常回复的情况,添加助手新回复到消息列表
                        self.sessions.session_reply(reply_content, session_id, total_tokens)
                        reply = Reply(ReplyType.TEXT, reply_content)
                return reply
            elif context.type == ContextType.IMAGE_CREATE: # 如果是图像生成请求
                ok, retstring = self.create_img(query, 0) # 调用图像生成方法,0是retry_count
                reply = None
                if ok: # 如果生成成功，返回图片URL
                    reply = Reply(ReplyType.IMAGE_URL, retstring)
                else:   # 否则返回错误信息
                    reply = Reply(ReplyType.ERROR, retstring)
                return reply
     # 获取文本回复
    def reply_text(self, session: OpenAISession, retry_count=0):
        try:
            response = openai.Completion.create(prompt=str(session), **self.args) # 调用OpenAI文本生成接口
            res_content = response.choices[0]["text"].strip().replace("<|endoftext|>", "") # 获取回复内容
            total_tokens = response["usage"]["total_tokens"]  # 获取总Token数
            completion_tokens = response["usage"]["completion_tokens"] # 获取生成部分的Token数
            logger.info("[OPEN_AI] reply={}".format(res_content)) # 记录回复日志
            return {
                "total_tokens": total_tokens,
                "completion_tokens": completion_tokens,
                "content": res_content,
            }
        except Exception as e:  # 处理异常
            need_retry = retry_count < 2  # 控制重试次数(不满足条件时,返回False)
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            if isinstance(e, openai.error.RateLimitError): # 如果触发速率限制
                logger.warn("[OPEN_AI] RateLimitError: {}".format(e))
                result["content"] = "提问太快啦，请休息一下再问我吧"
                if need_retry:
                    time.sleep(20)
            elif isinstance(e, openai.error.Timeout): # 如果请求超时
                logger.warn("[OPEN_AI] Timeout: {}".format(e))
                result["content"] = "我没有收到你的消息"
                if need_retry:
                    time.sleep(5)
            elif isinstance(e, openai.error.APIConnectionError):  # 如果连接失败
                logger.warn("[OPEN_AI] APIConnectionError: {}".format(e))
                need_retry = False
                result["content"] = "我连接不到你的网络"
            else: # 其他异常
                logger.warn("[OPEN_AI] Exception: {}".format(e))
                need_retry = False
                self.sessions.clear_session(session.session_id) # 清除当前会话

            if need_retry: # 如果需要重试，递归调用
                logger.warn("[OPEN_AI] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, retry_count + 1)
            else:  # 否则返回错误结果
                return result
