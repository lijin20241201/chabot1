# encoding:utf-8

import json # 导入json模块，用于处理JSON数据
import time
from typing import List, Tuple # 导入类型提示模块，用于声明函数的参数和返回值类型
import openai # 导入OpenAI库，用于与OpenAI接口交互
import openai.error # 导入OpenAI错误处理模块
import broadscope_bailian # 导入broadscope_bailian模块，用于处理Qwen的API
from broadscope_bailian import ChatQaMessage # 从broadscope_bailian模块导入ChatQaMessage类

from bot.bot import Bot # 从bot模块导入Bot基类
from bot.ali.ali_qwen_session import AliQwenSession # 导入AliQwenSession类，用于管理Qwen会话
from bot.session_manager import SessionManager # 导入SessionManager类，用于管理会话
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common import const
from config import conf, load_config

class AliQwenBot(Bot): # 定义AliQwenBot类，继承自Bot类
    def __init__(self):
        super().__init__() # 调用父类的初始化方法
        self.api_key_expired_time = self.set_api_key()  # 设置API密钥的过期时间
        # 初始化会话管理器，使用Qwen模型
        self.sessions = SessionManager(AliQwenSession, model=conf().get("model", const.QWEN))
    # 创建并返回一个AccessTokenClient实例，用于获取API密钥
    def api_key_client(self):
        return broadscope_bailian.AccessTokenClient(access_key_id=self.access_key_id(), access_key_secret=self.access_key_secret())
    # 从配置中获取qwen_access_key_id
    def access_key_id(self):
        return conf().get("qwen_access_key_id")
    # 从配置中获取qwen_access_key_secret
    def access_key_secret(self):
        return conf().get("qwen_access_key_secret")
    # 从配置中获取qwen_agent_key
    def agent_key(self):
        return conf().get("qwen_agent_key")
     # 从配置中获取qwen_app_id
    def app_id(self):
        return conf().get("qwen_app_id")
    # 从配置中获取qwen_node_id，默认为空字符串
    def node_id(self):
        return conf().get("qwen_node_id", "")
    # 从配置中获取temperature（温度），默认为0.2
    def temperature(self):
        return conf().get("temperature", 0.2 )
    # 从配置中获取top_p值，默认为1
    def top_p(self):
        return conf().get("top_p", 1)
    # 获取回复
    def reply(self, query, context=None):
        if context.type == ContextType.TEXT: # 如果消息类型是文本消息
            logger.info("[QWEN] query={}".format(query)) # 打印日志
            session_id = context["session_id"] # 获取会话ID
            reply = None  # 初始化回复为空
            clear_memory_commands = conf().get("clear_memory_commands", ["#清除记忆"]) # 获取清除记忆的命令列表
            if query in clear_memory_commands: # 如果指令在清除记忆命令的列表内
                self.sessions.clear_session(session_id) # 从sessions中删除当前会话
                reply = Reply(ReplyType.INFO, "记忆已清除")  # 设置回复内容为“记忆已清除”
            elif query == "#清除所有": # 如果查询是清除所有命令
                self.sessions.clear_all_session()  # 清空sessions字典,就是删除所有会话
                # 系统维护：需要重置系统中的所有对话历史，以便从头开始。这时用到清除所有
                reply = Reply(ReplyType.INFO, "所有人记忆已清除") # 设置回复内容为“所有人记忆已清除”
            elif query == "#更新配置": # 如果查询是更新配置命令
                load_config() # 重新加载配置(会重新加载配置和用户数据)
                reply = Reply(ReplyType.INFO, "配置已更新") # 设置回复内容为“配置已更新”
            if reply: # 如果有回复内容，直接返回,没有的话,程序向下
                return reply
            # 如果没有命令相关的回复，设置用户查询
            session = self.sessions.session_query(query, session_id)
            logger.debug("[QWEN] session query={}".format(session.messages)) # 记录会话查询日志
            reply_content = self.reply_text(session)  # 获取助手最新的回复
            logger.debug(
                "[QWEN] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                    session.messages,
                    session_id,
                    reply_content["content"],
                    reply_content["completion_tokens"],
                )
            )
            # 如果回复的tokens为0且内容非空(出现异常)，返回错误类型的回复
            if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
            # 如果回复的tokens大于0，说明回复内容有效
            elif reply_content["completion_tokens"] > 0:
                # 把助手最新回复加入self.mesaages列表中
                self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                reply = Reply(ReplyType.TEXT, reply_content["content"]) # 设置文本类型的回复
            else:  # 如果没有有效的回复内容(特殊异常)
                reply = Reply(ReplyType.ERROR, reply_content["content"]) # 返回错误类型的回复
                logger.debug("[QWEN] reply {} used 0 tokens.".format(reply_content))  # 记录无效回复日志
            return reply # 返回最终的回复内容

        else: # 如果消息类型不是文本,返回不支持的错误回复
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply

    def reply_text(self, session: AliQwenSession, retry_count=0) -> dict:
        # 调用百炼的ChatCompletion接口获取回答,param session: 当前会话对象，包含对话历史
        # param retry_count: 当前的重试次数，默认为0,return: 包含生成内容、token信息的字典
        try:
            # 根据会话中的消息列表生成用户最新的消息和多轮对话(问答对)
            prompt, history = self.convert_messages_format(session.messages)
            self.update_api_key_if_expired() # 检查并更新API密钥，如果密钥过期
            # 调用百炼的Completions API进行生成，temperature和top_p作用类似，取较小值作为top_p传入
            # 文档说明参考：https://help.aliyun.com/document_detail/2587502.htm
             # 传入应用ID,传入消息提示,传入消息历史,取温度和top_p的较小值
            response = broadscope_bailian.Completions().call(\
                app_id=self.app_id(), prompt=prompt, history=history,top_p=min(self.temperature(), self.top_p()))
            # 从API响应中提取生成的内容(助手机器人的回复)
            completion_content = self.get_completion_content(response, self.node_id())
            # 计算助手生成的token数和消息列表和当前助手生成(多轮对话)的总token数
            completion_tokens, total_tokens = self.calc_tokens(session.messages, completion_content)
            # 返回包含token信息和生成内容的字典
            return {
                "total_tokens": total_tokens, # 总token数量
                "completion_tokens": completion_tokens,  # 助手最新回复的token数
                "content": completion_content, # 助手最新回复
            }
        except Exception as e:
            # 如果发生异常，根据异常类型处理不同的错误
            need_retry = retry_count < 2 # 判断是否需要重试，最多重试2次
            # 默认错误结果，表示服务暂时不可用
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            # 如果是RateLimitError（请求过于频繁），提示用户稍等
            if isinstance(e, openai.error.RateLimitError):
                logger.warn("[QWEN] RateLimitError: {}".format(e))
                result["content"] = "提问太快啦，请休息一下再问我吧"
                if need_retry: # 如果还可以重试，等待20秒后重试
                    time.sleep(20)
            elif isinstance(e, openai.error.Timeout): # 如果是Timeout（请求超时），提示用户未收到消息
                logger.warn("[QWEN] Timeout: {}".format(e))
                result["content"] = "我没有收到你的消息"
                if need_retry: # 如果还可以重试，等待5秒后重试
                    time.sleep(5)
            elif isinstance(e, openai.error.APIError): # 如果是APIError（API错误），提示用户稍后再试
                logger.warn("[QWEN] Bad Gateway: {}".format(e))
                result["content"] = "请再问我一次"
                if need_retry:
                    time.sleep(10)
            elif isinstance(e, openai.error.APIConnectionError): # 如果是APIConnectionError（API连接错误），提示无法连接到网络
                logger.warn("[QWEN] APIConnectionError: {}".format(e))
                need_retry = False  # 不再重试
                result["content"] = "我连接不到你的网络"
            else: # 其他类型的异常，记录异常并清除当前会话
                logger.exception("[QWEN] Exception: {}".format(e))
                need_retry = False # 不再重试
                self.sessions.clear_session(session.session_id) # 清除当前会话的历史
            # 如果仍然需要重试，则递归调用 reply_text 进行重试
            if need_retry:
                logger.warn("[QWEN] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, retry_count + 1)
            else:
                return result # 返回错误结果，或在无法重试时返回默认消息

    def set_api_key(self):
        # 调用 API 客户端创建新的 API 密钥和过期时间
        api_key, expired_time = self.api_key_client().create_token(agent_key=self.agent_key())
        broadscope_bailian.api_key = api_key # 设置 broadscope_bailian 库的 api_key 为新获取的 api_key
        return expired_time # 返回 API 密钥的过期时间

    def update_api_key_if_expired(self):
        # 检查当前时间是否超过 API 密钥的过期时间
        if time.time() > self.api_key_expired_time:
            self.api_key_expired_time = self.set_api_key() # 如果过期，重新设置 API 密钥并更新过期时间
    
    def convert_messages_format(self, messages) -> Tuple[str, List[ChatQaMessage]]:
        history = [] # 存储多轮对话(问答对)
        user_content = ''  # 用户消息内容：累积用户的输入（可能是多段消息）
        assistant_content = '' # 机器人回复的消息内容
        system_content = '' # 系统消息内容（如角色设定等)
        # 遍历消息列表，根据角色分类不同的消息内容
        # 用户在输入时，可能会发送多段消息。每次用户发送一段消息时，内容会被累积到 user_content 变量中，这样系统就能将这些连续的消息
        # 视为用户的一次完整输入。
        # 当系统接收到一条来自机器人的回复消息时（role == 'assistant'），这意味着一轮对话的结束。此时，将累积的 user_content 
        # 和机器人生成的 assistant_content 作为一对问答（Q&A pair），构成一个完整的问答对，存储到 history 中。
        # 在存储完问答对后，清空 user_content 和 assistant_content，为下一次用户输入和机器人的回答准备好空白的状态。这样做是
        # 为了避免混淆不同轮次的对话。
        for message in messages:
            role = message.get('role') # 获取消息的角色（user, assistant, system）
            if role == 'user':  # 如果是用户消息（考虑到用户可能会分段输入且机器人不立即回复）
                user_content += message.get('content') # 将用户的消息内容累积到 user_content 变量中
            elif role == 'assistant': # 如果是助手(bot)回复
                assistant_content = message.get('content')  # 获取机器人回复的内容
                history.append(ChatQaMessage(user_content, assistant_content))   # 将完整的用户消息和机器人回复作为一个问答对存入历史
                user_content = ''   # 清空 user_content，为下一轮用户输入准备
                assistant_content = ''   # 清空 assistant_content，为下一轮机器人回复准备
            elif role =='system': # 如果是系统消息（如角色设定）
                system_content += message.get('content') # 将系统消息内容累积起来
        # 如果没有用户消息，抛出异常
        if user_content == '': # 这个是用户最新的消息,所以这个必须有,因为要根据这个获取机器人最新的回复
            raise Exception('no user message')
        # 如果有系统消息，将其作为一条特殊的 ChatQaMessage 存入历史记录中
        if system_content != '':
            # NOTE 模拟系统消息，测试发现人格描述以"你需要扮演ChatGPT"开头能够起作用，而以"你是ChatGPT"开头模型会直接否认
            system_qa = ChatQaMessage(system_content, '好的，我会严格按照你的设定回答问题')
            history.insert(0, system_qa)  # 将系统qa问答对插入history中最前面
        # 调试日志：打印转换后的多轮对话
        logger.debug("[QWEN] converted qa messages: {}".format([item.to_dict() for item in history]))
        # 调试日志：打印用户的消息内容，将作为 prompt 提供给机器人
        logger.debug("[QWEN] user content as prompt: {}".format(user_content))
        return user_content, history # 返回用户消息和历史记录(多轮对话)，以便后续生成回复

    def get_completion_content(self, response, node_id):
        # 如果响应中的 Success 为 False，表示请求失败，返回错误信息
        if not response['Success']:
            return f"[ERROR]\n{response['Code']}:{response['Message']}"
        text = response['Data']['Text'] # 获取响应中的文本内容
        if node_id == '': # 如果没有指定 node_id，直接返回文本内容
            return text
        # TODO: 当使用流程编排创建大模型应用时，响应结构如下，最终结果在['finalResult'][node_id]['response']['text']中，暂时先这么写
        # {
        #     'Success': True,
        #     'Code': None,
        #     'Message': None,
        #     'Data': {
        #         'ResponseId': '9822f38dbacf4c9b8daf5ca03a2daf15',
        #         'SessionId': 'session_id',
        #         'Text': '{"finalResult":{"LLM_T7islK":{"params":{"modelId":"qwen-plus-v1","prompt":"${systemVars.query}${bizVars.Text}"},"response":{"text":"作为一个AI语言模型，我没有年龄，因为我没有生日。\n我只是一个程序，没有生命和身体。"}}}}',
        #         'Thoughts': [],
        #         'Debug': {},
        #         'DocReferences': []
        #     },
        #     'RequestId': '8e11d31551ce4c3f83f49e6e0dd998b0',
        #     'Failed': None
        # }
        text_dict = json.loads(text) # 将响应文本解析为字典
        completion_content =  text_dict['finalResult'][node_id]['response']['text'] # 从字典中提取最终生成的文本内容
        return completion_content # 返回生成的文本内容

    def calc_tokens(self, messages, completion_content):
        # 计算生成内容的 token 数量，假设每个字符为一个 token
        completion_tokens = len(completion_content)
        prompt_tokens = 0 # 计算提示消息的 token 数量，假设每个字符为一个 token
        for message in messages:
            prompt_tokens += len(message["content"])  # 累加每条消息的长度
        # 返回生成内容的 token 数量和所有消息的总 token 数量
        return completion_tokens, prompt_tokens + completion_tokens
