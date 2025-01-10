from bot.session_manager import Session
from common.log import logger

class OpenAISession(Session): # 定义一个 OpenAISession 类，继承自 Session 类
     # 初始化会话对象，传入会话 ID 和可选的系统提示和模型
    def __init__(self, session_id, system_prompt=None, model="text-davinci-003"):
        super().__init__(session_id, system_prompt) # 调用父类的构造方法，初始化会话
        self.model = model # 设置默认的 AI 模型为 "text-davinci-003"
        self.reset() # 设置消息列表为只有系统提示的状态
    def __str__(self): # 把当前会话对应的消息列表的消息变成字符串的形式
        prompt = "" # 初始化一个空字符串
        for item in self.messages: # 遍历会话对应的消息列表中的所有消息
            if item["role"] == "system": # 如果消息的角色是 system
                prompt += item["content"] + "<|endoftext|>\n\n\n" # 添加系统消息内容并标记结束
            elif item["role"] == "user":  # 如果消息的角色是 user
                prompt += "Q: " + item["content"] + "\n" # 添加用户问题并标记为 "Q:"
            elif item["role"] == "assistant": # 如果消息的角色是 assistant
                prompt += "\n\nA: " + item["content"] + "<|endoftext|>\n"  # 添加助手回答并标记为 "A:"
        # 如果最后一条消息是用户的提问，给出一个 "A: " 作为回答的提示
        if len(self.messages) > 0 and self.messages[-1]["role"] == "user":
            prompt += "A: "
        return prompt # 返回构建好的对话字符串
     # 当消息列表中包含的总token超出最大时,做限制处理(一般多用于多轮对话)
    def discard_exceeding(self, max_tokens, cur_tokens=None):
        precise = True # 标记是否使用精确的 token 计数方法
        try:
            cur_tokens = self.calc_tokens() # 计算当前消息的 token 数量
        except Exception as e: # 如果出现异常
            precise = False # 使用非精确方法
            if cur_tokens is None: # 如果传入的 cur_tokens 是 None，抛出异常
                raise e
            # 这里记录的是cur_tokens不是None的情况,因为是None的话都程序中断了
            logger.debug("Exception when counting tokens precisely for query: {}".format(e)) # 记录调试日志
        while cur_tokens > max_tokens: # 当当前 token 数量超过最大限制时，删除多余的消息
            if len(self.messages) > 1:  # 如果消息列表中有多条消息
                self.messages.pop(0) # 删除最早的一条消息
             # 如果只有一条消息且为助手消息,助手消息要和用户query消息配对才有用,这里删除助手消息是对的
            elif len(self.messages) == 1 and self.messages[0]["role"] == "assistant": 
                self.messages.pop(0)  # 删除这条消息,因为这里删除了,所以下面需要重新计算
                if precise: # 如果是精确计算 token 数
                    cur_tokens = self.calc_tokens() # 重新计算当前 token 数
                else:  # 否则，使用非精确计算
                    cur_tokens = len(str(self)) # 使用字符串长度来估算 token 数
                break # 退出循环
            elif len(self.messages) == 1 and self.messages[0]["role"] == "user": # 如果只有一条消息且为用户提问
                logger.warn("user question exceed max_tokens. total_tokens={}".format(cur_tokens)) # 记录警告日志
                break  # 这里不需要重新计算是因为用户消息的长度不需要被限制(因为如果截断,会改变语义),退出循环
            else: 
                logger.debug("max_tokens={}, total_tokens={}, len(conversation)={}".format(max_tokens, cur_tokens, len(self.messages)))
                break # 退出循环
            # 这个处理的其实是len(self.messages) > 1时的情况,因为上面删除了最早的消息
            if precise:  
                cur_tokens = self.calc_tokens() # 使用精确方法计算 token 数
            else:
                cur_tokens = len(str(self)) # 使用字符串长度估算 token 数
        return cur_tokens

    def calc_tokens(self): # 计算当前会话的 token 数
        return num_tokens_from_string(str(self), self.model) # 计算并返回当前对话的 token 数量

# refer to https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
def num_tokens_from_string(string: str, model: str) -> int:
    import tiktoken # 导入 tiktoken 库，它是 OpenAI 提供的用于处理 token 的工具
    encoding = tiktoken.encoding_for_model(model)  # 获取指定模型的编码器
    num_tokens = len(encoding.encode(string, disallowed_special=())) # 编码字符串并计算 token 数量
    return num_tokens
