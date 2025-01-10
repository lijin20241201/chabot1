from common.expired_dict import ExpiredDict # 引入过期字典和日志工具
from common.log import logger
from config import conf

# 会话类，用于管理每个会话的状态和消息
class Session(object):
    def __init__(self, session_id, system_prompt=None):
        # 初始化会话，session_id为会话的唯一标识
        self.session_id = session_id
        self.messages = [] # 存储会话中的消息
        # 如果没有传入system_prompt，则从配置文件中获取默认的system_prompt
        if system_prompt is None:
            self.system_prompt = conf().get("character_desc", "")
        else:
            self.system_prompt = system_prompt

    # 重置消息列表为只有系统提示的状态
    def reset(self):
        system_item = {"role": "system", "content": self.system_prompt}
        self.messages = [system_item]
    # 设置新的system_prompt，并重置会话
    def set_system_prompt(self, system_prompt):
        self.system_prompt = system_prompt
        self.reset()
    # 添加用户的查询，指令等
    def add_query(self, query):
        user_item = {"role": "user", "content": query}
        self.messages.append(user_item)
    # 添加助手的回复消息
    def add_reply(self, reply):
        assistant_item = {"role": "assistant", "content": reply}
        self.messages.append(assistant_item)
    # 丢弃超过最大token数的消息，具体实现未提供
    def discard_exceeding(self, max_tokens=None, cur_tokens=None):
        raise NotImplementedError
    # 计算当前会话使用的token数，具体实现未提供
    def calc_tokens(self):
        raise NotImplementedError
# 会话管理类，用于管理多个会话的创建、查询和清理
class SessionManager(object):
    def __init__(self, sessioncls, **session_args):
        # 如果配置文件中有expires_in_seconds，使用过期字典，否则使用普通字典
        if conf().get("expires_in_seconds"):
            sessions = ExpiredDict(conf().get("expires_in_seconds"))
        else:
            sessions = dict()
        self.sessions = sessions # 会话字典
        self.sessioncls = sessioncls # 会话类
        self.session_args = session_args # 会话类初始化参数
    # 构建会话，如果session_id不存在则创建新的会话
    def build_session(self, session_id, system_prompt=None):
        # 如果session_id为None
        if session_id is None:
            return self.sessioncls(session_id, system_prompt, **self.session_args)
        # 如果session_id不在sessions中,创建一个新的session并添加到sessions中
        if session_id not in self.sessions:
            self.sessions[session_id] = self.sessioncls(session_id, system_prompt, **self.session_args)
        # 走到这个分支的前提是session_id在self.sessions中,但是system_prompt不为None
        # 这时会更改系统提示
        elif system_prompt is not None:  
            self.sessions[session_id].set_system_prompt(system_prompt)
        session = self.sessions[session_id] # 获取session_id对应的session
        return session # 返回会话
    # 处理会话的查询请求
    def session_query(self, query, session_id):
        session = self.build_session(session_id) # 构建会话
        session.add_query(query) # 添加用户查询
        try:
            max_tokens = conf().get("conversation_max_tokens", 1000)  # 获取最大token数
            total_tokens = session.discard_exceeding(max_tokens, None) # 丢弃超出的token
            logger.debug("prompt tokens used={}".format(total_tokens)) # 记录调试日志
        except Exception as e:  # 异常处理
            logger.warning("Exception when counting tokens precisely for prompt: {}".format(str(e)))
        return session
    # 处理会话返回的回复
    def session_reply(self, reply, session_id, total_tokens=None):
        session = self.build_session(session_id)
        session.add_reply(reply)
        try:
            max_tokens = conf().get("conversation_max_tokens", 1000)
            tokens_cnt = session.discard_exceeding(max_tokens, total_tokens)
            logger.debug("raw total_tokens={}, savesession tokens={}".format(total_tokens, tokens_cnt))
        # 异常捕获后，程序继续运行：Python 的异常处理机制会阻止异常传播到外部函数或方法，从而避免整个函数失败。
        # except 块不会阻止后续代码执行：在 except 块执行完后，程序会继续执行 return session。
        except Exception as e:
            logger.warning("Exception when counting tokens precisely for session: {}".format(str(e)))
        return session
    # 清除指定的会话
    def clear_session(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id] # 删除sessions中的指定项
    # 清除所有会话
    def clear_all_session(self):
        self.sessions.clear()
