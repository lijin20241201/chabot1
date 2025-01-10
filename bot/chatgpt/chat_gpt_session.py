from bot.session_manager import Session
from common.log import logger
from common import const

"""
    [ # 多轮对话的消息列表
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Who won the world series in 2020?"},
        {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
        {"role": "user", "content": "Where was it played?"}
    ]
"""
class ChatGPTSession(Session):
    def __init__(self, session_id, system_prompt=None, model="gpt-3.5-turbo"):
        super().__init__(session_id, system_prompt) # 调用父类的构造函数初始化会话ID和系统提示
        self.model = model  # 设置默认的模型（默认为gpt-3.5-turbo），并初始化模型
        self.reset() # 调用reset方法初始化会话状态

    def discard_exceeding(self, max_tokens, cur_tokens=None):
        precise = True # 默认开启精确计算标志
        try:
            cur_tokens = self.calc_tokens() # 尝试精确计算当前令牌数
        except Exception as e:
            precise = False # 如果计算令牌数时发生异常，关闭精确计算
            if cur_tokens is None: # # 如果cur_tokens也没有提供，则抛出异常
                raise e
            # 记录计算令牌数时发生的异常
            logger.debug("Exception when counting tokens precisely for query: {}".format(e))
        while cur_tokens > max_tokens: # 循环直到当前令牌数小于最大令牌数
            if len(self.messages) > 2: # 如果消息超过两个，则删除第一个用户消息,只有这个可能会循环操作(多轮对话时)
                self.messages.pop(1) 
            # 如果只有两个消息，并且第二个消息是助手的，则删除第二条消息(这时第一条是系统提示)
            elif len(self.messages) == 2 and self.messages[1]["role"] == "assistant":
                self.messages.pop(1)
                if precise: # 如果精确计算标志为True，则重新计算当前令牌数
                    cur_tokens = self.calc_tokens()
                else: # 如果没有精确计算，直接从当前令牌数中减去最大令牌数
                    cur_tokens = cur_tokens - max_tokens
                break # 退出循环
            # 如果只有两个消息，并且第二个消息是用户的，记录警告并跳出循环
            elif len(self.messages) == 2 and self.messages[1]["role"] == "user":
                logger.warn("user message exceed max_tokens. total_tokens={}".format(cur_tokens))
                break
            else: # 如果只有一条消息(这个是系统提示),记录调试日志,之后break
                logger.debug("max_tokens={}, total_tokens={}, len(messages)={}".format(max_tokens, cur_tokens, len(self.messages)))
                break
            if precise: # 如果精确计算标志为True，则重新计算当前令牌数
                cur_tokens = self.calc_tokens()
            else: # 如果没有精确计算，则直接从当前令牌数中减去最大令牌数
                cur_tokens = cur_tokens - max_tokens
        return cur_tokens # 返回调整后的令牌数
    # 计算当前会话中的令牌数
    def calc_tokens(self):
        return num_tokens_from_messages(self.messages, self.model)

# refer to https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
# 返回一系列消息所使用的token数量
def num_tokens_from_messages(messages, model):
    # 如果模型是wenxin、xunfei之一，或者模型名称以gemini-1.0-pro开头,则使用基于字符长度的不同方法来计算token数量
    if model in ["wenxin", "xunfei"] or model.startswith(const.GEMINI):
        return num_tokens_by_character(messages)
    import tiktoken # 导入tiktoken库来进行token化
    # 如果模型是指定的3.5系列模型，则调用相同的函数，但使用"gpt-3.5-turbo"模型进行token计数
    if model in ["gpt-3.5-turbo-0301", "gpt-35-turbo", "gpt-3.5-turbo-1106", "moonshot", const.LINKAI_35]:
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo")
    # 如果模型是指定的4系列模型，则调用相同的函数，但使用"gpt-4"模型进行token计数
    elif model in ["gpt-4-0314", "gpt-4-0613", "gpt-4-32k", "gpt-4-32k-0613", "gpt-3.5-turbo-0613",
                   "gpt-3.5-turbo-16k", "gpt-3.5-turbo-16k-0613", "gpt-35-turbo-16k", "gpt-4-turbo-preview",
                   "gpt-4-1106-preview", const.GPT4_TURBO_PREVIEW, const.GPT4_VISION_PREVIEW, const.GPT4_TURBO_01_25,
                   const.GPT_4o, const.GPT_4O_0806, const.GPT_4o_MINI, const.LINKAI_4o, const.LINKAI_4_TURBO]:
        return num_tokens_from_messages(messages, model="gpt-4")
    # 如果模型是claude-3系列，则回退到使用"gpt-3.5-turbo"进行token计数
    elif model.startswith("claude-3"):
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo")
    try:
        encoding = tiktoken.encoding_for_model(model) # 尝试获取模型的token化编码
    except KeyError: # 如果模型编码未找到，则使用默认的"cl100k_base"编码
        logger.debug("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo": # 根据模型设置默认的token计数
        tokens_per_message = 4  # # 每条消息有4个token的开销，格式为<|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1 # 如果消息包含名称，则角色字段不再使用，因此不加额外token
    elif model == "gpt-4":
        tokens_per_message = 3 # 每条消息有3个token的开销，格式为<|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = 1 # 如果消息包含名称，角色字段需要1个额外的token
    else: # 如果模型不在支持的范围内，则假定是"gpt-3.5-turbo"进行token计数
        # 没有实现模型 {model} 的token计数。默认返回gpt-3.5-turbo的token数量。")
        logger.warn(f"num_tokens_from_messages() is not implemented for model {model}. Returning num tokens assuming gpt-3.5-turbo.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo")
    num_tokens = 0 # 初始化token计数
    for message in messages:  # 遍历消息列表中的每条消息
        num_tokens += tokens_per_message  # 每条消息的开销token数量
        for key, value in message.items(): # 遍历消息中的每个键值对
            num_tokens += len(encoding.encode(value))  # 计算消息内容（值）所占用的token数量
            if key == "name":  # 如果键是"name"，则添加角色字段的token
                num_tokens += tokens_per_name
    num_tokens += 3  # 每个回复都会被预先加上<|start|>的token
    return num_tokens # 返回总的token数量
# 返回一系列消息所使用的token数量（按字符计算）
def num_tokens_by_character(messages):
    tokens = 0  # 初始化token计数
    for msg in messages: # 遍历消息列表中的每条消息
        tokens += len(msg["content"])  # 计算每条消息内容（字符长度）的token数量
    return tokens # 返回按字符计算的token数量
