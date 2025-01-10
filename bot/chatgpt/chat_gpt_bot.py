# encoding:utf-8
import time
import openai
import openai.error
import requests
from common import const
from bot.bot import Bot
from bot.chatgpt.chat_gpt_session import ChatGPTSession
from bot.openai.open_ai_image import OpenAIImage # 导入OpenAI图像生成类
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.token_bucket import TokenBucket  # 导入令牌桶限流工具
from config import conf, load_config
from bot.baidu.baidu_wenxin_session import BaiduWenxinSession

# OpenAI对话模型API
class ChatGPTBot(Bot, OpenAIImage):
    def __init__(self):
        super().__init__() # 调用父类初始化方法
         # 设置OpenAI的API密钥
        openai.api_key = conf().get("open_ai_api_key")
        if conf().get("open_ai_api_base"): # 如果配置了自定义API地址，进行设置
            openai.api_base = conf().get("open_ai_api_base")
        proxy = conf().get("proxy")  # 获取代理配置
        if proxy:
            openai.proxy = proxy # 设置代理
        if conf().get("rate_limit_chatgpt"):  # 如果配置了限速功能
            self.tb4chatgpt = TokenBucket(conf().get("rate_limit_chatgpt", 20)) # 初始化令牌桶
        conf_model = conf().get("model") or "gpt-3.5-turbo" # 设置默认模型
        # 初始化会话管理器
        self.sessions = SessionManager(ChatGPTSession, model=conf().get("model") or "gpt-3.5-turbo")
        self.args = { # 初始化模型参数
            "model": conf_model,  # 对话模型的名称
            "temperature": conf().get("temperature", 0.9),  # 回复随机性，越高越随机
            # "max_tokens":4096,  # 回复最大的字符数
            "top_p": conf().get("top_p", 1), # 控制采样范围
            "frequency_penalty": conf().get("frequency_penalty", 0.0),  #对重复内容的惩罚, [-2,2]之间，该值越大则更倾向于产生不同的内容
            "presence_penalty": conf().get("presence_penalty", 0.0),  # 生成新内容的倾向,[-2,2]之间，该值越大则更倾向于产生不同的内容
            "request_timeout": conf().get("request_timeout", None),  # 请求超时时间
            "timeout": conf().get("request_timeout", None), # 重试的超时时间
        }
        # o1相关模型不支持system prompt，暂时用文心模型的session,o1相关模型固定了部分参数，暂时去掉
        if conf_model in [const.O1, const.O1_MINI]:
            # 如果是o1,使用文心的会话
            self.sessions = SessionManager(BaiduWenxinSession, model=conf().get("model") or const.O1_MINI)
            remove_keys = ["temperature", "top_p", "frequency_penalty", "presence_penalty"]
            for key in remove_keys: # 如果键不存在，使用 None 来避免抛出错误
                self.args.pop(key, None) 
    # 获取回复内容
    def reply(self, query, context=None):
        if context.type == ContextType.TEXT: # 如果是文本请求
            logger.info("[CHATGPT] query={}".format(query))  # 记录日志

            session_id = context["session_id"] # 获取会话ID
            reply = None
            clear_memory_commands = conf().get("clear_memory_commands", ["#清除记忆"]) # 获取清除记忆命令列表
            if query in clear_memory_commands:  # 如果请求为清除记忆
                self.sessions.clear_session(session_id) # 清除当前会话
                reply = Reply(ReplyType.INFO, "记忆已清除")
            elif query == "#清除所有":  # 如果请求为清除所有会话
                self.sessions.clear_all_session() # 清空所有会话
                reply = Reply(ReplyType.INFO, "所有人记忆已清除")
            elif query == "#更新配置":  # 如果请求为更新配置
                load_config() # 重新加载配置
                reply = Reply(ReplyType.INFO, "配置已更新")
            if reply: # 有回复说明是上述指令
                return reply 
            #  构建会话,并把用户消息添加进消息列表
            session = self.sessions.session_query(query, session_id)
            logger.debug("[CHATGPT] session query={}".format(session.messages)) # 记录会话内容
            api_key = context.get("openai_api_key")  # 获取上下文中的API密钥
            model = context.get("gpt_model") # 获取指定的模型
            new_args = None
            if model:
                new_args = self.args.copy() # 复制参数
                new_args["model"] = model # 使用指定模型
            # if context.get('stream'):
            #     # reply in stream
            #     return self.reply_text_stream(query, new_query, session_id)
            reply_content = self.reply_text(session, api_key, args=new_args)  # 调用生成文本方法
            logger.debug(
                "[CHATGPT] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                    session.messages,
                    session_id,
                    reply_content["content"],
                    reply_content["completion_tokens"],
                )
            )
            # 如果出现异常,并且有错误消息
            if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
            # 如果正常生成
            elif reply_content["completion_tokens"] > 0:
                # 把回复消息添加到消息列表
                self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            else: # 这种情况没有消息,也是出错
                reply = Reply(ReplyType.ERROR, reply_content["content"])
                logger.debug("[CHATGPT] reply {} used 0 tokens.".format(reply_content))
            return reply
        
        elif context.type == ContextType.IMAGE_CREATE: # 如果是图像生成请求
            ok, retstring = self.create_img(query, 0) # 调用图像生成方法
            reply = None
            if ok:
                reply = Reply(ReplyType.IMAGE_URL, retstring) # 返回图像URL
            else:
                reply = Reply(ReplyType.ERROR, retstring) # 返回错误信息
            return reply
        else:
             # 不支持的消息类型
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply

    def reply_text(self, session: ChatGPTSession, api_key=None, args=None, retry_count=0) -> dict:
        """
        调用OpenAI的ChatCompletion获取回答
        :param session: 会话对象
        :param api_key: API密钥
        :param args: 请求参数
        :param retry_count: 当前重试次数
        :return: 回复内容的字典
        """
        try:
            # 如果设置了生成速率限制,并且当前没获取到token
            if conf().get("rate_limit_chatgpt") and not self.tb4chatgpt.get_token():
                raise openai.error.RateLimitError("RateLimitError: rate limit exceeded") # 超出速率限制
            # 如果未指定参数，使用默认的参数配置
            if args is None:
                args = self.args
            # 调用OpenAI的ChatCompletion API获取回答
            response = openai.ChatCompletion.create(api_key=api_key, messages=session.messages, **args)
            # logger.debug("[CHATGPT] response={}".format(response))
            # logger.info("[ChatGPT] reply={}, total_tokens={}".format(response.choices[0]['message']['content'], response["usage"]["total_tokens"]))
            return {
                "total_tokens": response["usage"]["total_tokens"], # 消息列表中的总token数
                "completion_tokens": response["usage"]["completion_tokens"], # 助手新生成的token数
                "content": response.choices[0]["message"]["content"], # 助手生成文本
            }
        except Exception as e:
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}  # 默认的错误回复内容
            if isinstance(e, openai.error.RateLimitError):
                logger.warn("[CHATGPT] RateLimitError: {}".format(e))
                result["content"] = "提问太快啦，请休息一下再问我吧"
                if need_retry:
                    time.sleep(20)
            elif isinstance(e, openai.error.Timeout):
                logger.warn("[CHATGPT] Timeout: {}".format(e))
                result["content"] = "我没有收到你的消息"
                if need_retry:
                    time.sleep(5)
            elif isinstance(e, openai.error.APIError):
                logger.warn("[CHATGPT] Bad Gateway: {}".format(e))
                result["content"] = "请再问我一次"
                if need_retry:
                    time.sleep(10)
            elif isinstance(e, openai.error.APIConnectionError): # 处理API连接错误
                logger.warn("[CHATGPT] APIConnectionError: {}".format(e))
                result["content"] = "我连接不到你的网络"
                if need_retry:
                    time.sleep(5)
            else: # 其他错误
                logger.exception("[CHATGPT] Exception: {}".format(e))
                need_retry = False # 非常规错误不重试
                self.sessions.clear_session(session.session_id) # 清除当前会话
            # 如果允许重试，递归调用自身
            if need_retry:
                logger.warn("[CHATGPT] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, api_key, args, retry_count + 1)
            else:
                return result # 返回最终失败的结果


class AzureChatGPTBot(ChatGPTBot): 
    def __init__(self):
        super().__init__()
        openai.api_type = "azure" # 设置为Azure类型的API
        openai.api_version = conf().get("azure_api_version", "2023-06-01-preview") # 配置Azure API版本
        self.args["deployment_id"] = conf().get("azure_deployment_id") # 设置部署ID，用于指定Azure OpenAI服务中的部署

    def create_img(self, query, retry_count=0, api_key=None):
        text_to_image_model = conf().get("text_to_image") # 获取文本转图像模型的配置
        if text_to_image_model == "dall-e-2":
            api_version = "2023-06-01-preview" # 设置API版本和端点
            endpoint = conf().get("azure_openai_dalle_api_base","open_ai_api_base")
            # 检查endpoint是否以/结尾
            if not endpoint.endswith("/"):
                endpoint = endpoint + "/" 
            # 请求的url
            url = "{}openai/images/generations:submit?api-version={}".format(endpoint, api_version)
            api_key = conf().get("azure_openai_dalle_api_key","open_ai_api_key")
            headers = {"api-key": api_key, "Content-Type": "application/json"}
            
            try:
                # 请求体包含提示词、图片大小和生成数量
                body = {"prompt": query, "size": conf().get("image_create_size", "256x256"),"n": 1}
                submission = requests.post(url, headers=headers, json=body)
                operation_location = submission.headers['operation-location'] # 获取操作位置，用于查询任务状态
                status = "" 
                while (status != "succeeded"): # 当status为succeeded时退出循环，表示成功
                    if retry_count > 3: # 超过3次失败,返回图片生成失败
                        return False, "图片生成失败"
                    response = requests.get(operation_location, headers=headers)
                    status = response.json()['status']
                    retry_count += 1
                image_url = response.json()['result']['data'][0]['url'] # 声称图片的url
                return True, image_url  # 这里返回生成成功的状态和url
            except Exception as e: # 出现异常时的报错,返回创建失败
                logger.error("create image error: {}".format(e))
                return False, "图片生成失败"
        elif text_to_image_model == "dall-e-3":
            api_version = conf().get("azure_api_version", "2024-02-15-preview") # 设置API版本和端点
            endpoint = conf().get("azure_openai_dalle_api_base","open_ai_api_base")
            # 检查endpoint是否以/结尾
            if not endpoint.endswith("/"):
                endpoint = endpoint + "/" # 确保端点以/结尾
            url = "{}openai/deployments/{}/images/generations?api-version={}".format(endpoint, conf().get("azure_openai_dalle_deployment_id","text_to_image"),api_version)
            api_key = conf().get("azure_openai_dalle_api_key","open_ai_api_key")
            headers = {"api-key": api_key, "Content-Type": "application/json"}
            try:
                # 请求体包含提示词、图片大小和质量
                body = {"prompt": query, "size": conf().get("image_create_size", "1024x1024"), "quality": conf().get(\
                    "dalle3_image_quality", "standard")}
                response = requests.post(url, headers=headers, json=body)
                response.raise_for_status()  # 检查请求是否成功
                data = response.json()
                # 检查响应中是否包含图像 URL
                if 'data' in data and len(data['data']) > 0 and 'url' in data['data'][0]:
                    image_url = data['data'][0]['url']
                    return True, image_url
                else:
                    error_message = "响应中没有图像 URL"
                    logger.error(error_message)
                    return False, "图片生成失败"
            # 捕获请求相关的异常并提取错误信息
            except requests.exceptions.RequestException as e:
                # 捕获所有请求相关的异常
                try:
                    error_detail = response.json().get('error', {}).get('message', str(e))
                except ValueError:
                    error_detail = str(e)
                error_message = f"{error_detail}"
                logger.error(error_message)
                return False, error_message
            except Exception as e:
                # 捕获所有其他异常
                error_message = f"生成图像时发生错误: {e}"
                logger.error(error_message)
                return False, "图片生成失败"
        else: # 如果未正确配置`text_to_image`参数，则返回失败
            return False, "图片生成失败，未配置text_to_image参数"
