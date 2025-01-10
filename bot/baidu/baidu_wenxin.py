# encoding:utf-8

import requests
import json
from common import const
from bot.bot import Bot
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf
from bot.baidu.baidu_wenxin_session import BaiduWenxinSession
# 从配置文件中获取百度 API 密钥和秘密密钥
BAIDU_API_KEY = conf().get("baidu_wenxin_api_key")
BAIDU_SECRET_KEY = conf().get("baidu_wenxin_secret_key")

class BaiduWenxinBot(Bot):

    def __init__(self):
        super().__init__()
        # 因为''不是None,所以这里这样设置,如果从配置中获取到的是有效字符串,就设定前面,否则如果是'',设定默认
        wenxin_model = conf().get("baidu_wenxin_model") or "eb-instant"
        self.prompt_enabled = conf().get("baidu_wenxin_prompt_enabled")
        if self.prompt_enabled: # 如果设置了提示启用,这个是用ernie character model时
            self.prompt = conf().get("character_desc", "") # 获取系统提示(模型人格描述)
            # 如果未指定提示,警告
            if self.prompt == "": 
                logger.warn("[BAIDU] Although you enabled model prompt, character_desc is not specified.")
        if wenxin_model is None: # 这里判断wenxin_model如果是None,这种情况是配置中不存在这个键的情况
            if conf().get("model") and conf().get("model") == const.WEN_XIN:
                wenxin_model = "completions"
            elif conf().get("model") and conf().get("model") == const.WEN_XIN_4:
                wenxin_model = "completions_pro"
        # 初始化会话管理器
        self.sessions = SessionManager(BaiduWenxinSession, model=wenxin_model)
    # 获取回复内容
    def reply(self, query, context=None):
        if context and context.type: # 如果有上下文
            if context.type == ContextType.TEXT: # 如果消息的类型是文本
                logger.info("[BAIDU] query={}".format(query)) # 打印日志
                session_id = context["session_id"] # 获取当前会话id
                reply = None # 初始化回复
                if query == "#清除记忆": # 如果是清除记忆
                    self.sessions.clear_session(session_id) # 删除当前会话
                    reply = Reply(ReplyType.INFO, "记忆已清除") # 设置回复记忆已清除
                elif query == "#清除所有": # 如果是清除所有
                    self.sessions.clear_all_session() # 删除所有session(这个用在更新模型,更新服务器时)
                    reply = Reply(ReplyType.INFO, "所有人记忆已清除")
                else:
                    session = self.sessions.session_query(query, session_id) # 构建用户会话,设置用户query
                    result = self.reply_text(session) # 获取模型回复
                    # 模型返回的是个字典,根据字典获取总的token数,助手回复的token数,助手回复的内容
                    total_tokens, completion_tokens, reply_content = (
                        result["total_tokens"],
                        result["completion_tokens"],
                        result["content"],
                    )
                    # 打印调试日志
                    logger.debug(
                        "[BAIDU] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(session.messages, session_id, reply_content, completion_tokens)
                    )
                    if total_tokens == 0: # 这种情况是发生异常的情况
                        reply = Reply(ReplyType.ERROR, reply_content)
                    else: # 这种是正常生成回复的情况
                        self.sessions.session_reply(reply_content, session_id, total_tokens) # 改变会话中的消息列表
                        reply = Reply(ReplyType.TEXT, reply_content)
                return reply # 返回回复
            elif context.type == ContextType.IMAGE_CREATE: # 如果消息类型是图片创建
                ok, retstring = self.create_img(query, 0)
                reply = None # 初始化回复
                if ok: # 如果成功创建,设置回复为图片的url
                    reply = Reply(ReplyType.IMAGE_URL, retstring) 
                else: # 如果创建失败,设置回复为错误信息
                    reply = Reply(ReplyType.ERROR, retstring) 
                return reply # 返回回复
    
    def reply_text(self, session: BaiduWenxinSession, retry_count=0):
        try:
            logger.info("[BAIDU] model={}".format(session.model)) # 记录当前使用的模型
            access_token = self.get_access_token() # 获取访问令牌（access token）
            if access_token == 'None': # 如果访问令牌获取失败，记录警告并返回默认值
                logger.warn("[BAIDU] access token 获取失败")
                return {
                    "total_tokens": 0,
                    "completion_tokens": 0,
                    "content": 0,
                    }
            # 构建请求URL，包含访问令牌和模型
            url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/" + session.model + "?access_token=" + access_token
            # 设置请求头，指定内容类型为JSON
            headers = {
                'Content-Type': 'application/json'
            }
            # 准备请求数据，根据是否启用系统提示，选择不同的消息结构
            payload = {'messages': session.messages, 'system': self.prompt} if self.prompt_enabled else {'messages': session.messages}
            # 向百度文心API发送POST请求,dumps将python字典对象变成json字符串
            response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
            response_text = json.loads(response.text) # 解析API返回的JSON响应,loads将json字符串变成python字典
            logger.info(f"[BAIDU] response text={response_text}")  # 记录返回的响应数据，方便调试
            res_content = response_text["result"]  # 从响应中提取内容、总令牌数和完成令牌数
            total_tokens = response_text["usage"]["total_tokens"]
            completion_tokens = response_text["usage"]["completion_tokens"]
            logger.info("[BAIDU] reply={}".format(res_content)) # 记录返回的回复内容，方便调试
            return { # 返回提取的结果：总令牌数、完成令牌数和回复内容
                "total_tokens": total_tokens,
                "completion_tokens": completion_tokens,
                "content": res_content,
            }
        except Exception as e: # 如果发生异常，判断是否需要重试（最多重试2次）
            need_retry = retry_count < 2 # 这个在超过两次时变成False
            logger.warn("[BAIDU] Exception: {}".format(e))
            need_retry = False # 这个直接设定是省略了重试逻辑
            self.sessions.clear_session(session.session_id) # 从sessions字典中删除当前会话
            result = {"total_tokens": 0, "completion_tokens": 0, "content": "出错了: {}".format(e)}
            return result # 返回结果
    # 使用 AK，SK 生成鉴权签名（Access Token）
    def get_access_token(self):
        url = "https://aip.baidubce.com/oauth/2.0/token" # 定义获取访问令牌的URL
        # 定义请求参数，包括授权类型、客户端ID和客户端密钥
        params = {"grant_type": "client_credentials", "client_id": BAIDU_API_KEY, "client_secret": BAIDU_SECRET_KEY}
        # 向百度OAuth 2.0 API发送POST请求，并从响应中提取访问令牌
        return str(requests.post(url, params=params).json().get("access_token"))
