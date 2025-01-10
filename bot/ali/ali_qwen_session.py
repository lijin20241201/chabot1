from bot.session_manager import Session
from common.log import logger
"""
    这是self.messages列表内的顺序
    [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Who won the world series in 2020?"},
        {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
        {"role": "user", "content": "Where was it played?"}
    ]
"""
# 定义AliQwenSession类，继承自Session类，负责管理AliQwen模型的会话
class AliQwenSession(Session):
    def __init__(self, session_id, system_prompt=None, model="qianwen"):
        super().__init__(session_id, system_prompt) # 初始化，调用父类的构造函数并设置模型类型
        self.model = model # 设置使用的模型类型（默认为"qianwen"）
        self.reset() # 重置会话(会重置self.messages = [system_item])
    # 这个最大的用处是对多轮会话的长度做限制处理,保证如果超出最大长度，会self.messages.pop(1),以保证长度适宜
    def discard_exceeding(self, max_tokens, cur_tokens=None):
        precise = True  # 精确计算token数的标志
        try:
            cur_tokens = self.calc_tokens() # 尝试精确计算当前token数
        # 如果self.messages内的消息设置错误（例如，包含了None值等），calc_tokens()可能会
        # 遇到无法处理的情况。
        except Exception as e: 
            precise = False # 如果计算token数时发生异常，则设定为不精确
            if cur_tokens is None:  
                # 如果 cur_tokens 为 None，并且在 self.calc_tokens() 中发生异常，raise e 会抛出异常，后续代码不会继续执行。
                raise e 
            logger.debug("Exception when counting tokens precisely for query: {}".format(e)) # 记录计算token数时的异常信息
        # 循环直到token数小于等于最大值
        while cur_tokens > max_tokens:
            # self.messages内部是系统提示->用户查询-->助手回复,所以这里删除的是最早的用户消息
            if len(self.messages) > 2:
                self.messages.pop(1)
            # 如果消息列表中只有两条消息，并且第二条是助手回复，则删除第二条
            elif len(self.messages) == 2 and self.messages[1]["role"] == "assistant":
                self.messages.pop(1) # 删除助手回复的消息
                if precise: # 如果是精确计算，则重新计算弹出助手回复后的token数
                    cur_tokens = self.calc_tokens() 
                # max_tokens = 1000，即限制最大token数为1000。
                # 初始的cur_tokens可能已经很大，但由于某些异常，我们无法准确计算cur_tokens的当前值。
                # 如果precise=False，我们就会假设cur_tokens太大，于是采用cur_tokens = cur_tokens - max_tokens的方式
                # precise=False时，我们使用cur_tokens = cur_tokens - max_tokens是为了在无法精确计算token数时，采取一种简化的、
                # 粗略的方式减少cur_tokens，防止其超过max_tokens的限制。
                else:
                    cur_tokens = cur_tokens - max_tokens  
                break # 跳出循环，完成丢弃操作
            # 如果消息列表中只有两条消息，并且第二条是用户消息，则打印警告信息并退出(这个方法是对助手回复token数限制的)
            elif len(self.messages) == 2 and self.messages[1]["role"] == "user":
                logger.warn("user message exceed max_tokens. total_tokens={}".format(cur_tokens))
                break
            else: # 如果消息列表中只有一条消息，则打印调试信息并退出(本方法是为了限制回复的token数,所以这里不处理)
                logger.debug("max_tokens={}, total_tokens={}, len(messages)={}".format(max_tokens, cur_tokens, len(self.messages)))
                break
            if precise: # 能走到这里,是删除了用户消息的情况,这时会计算token数,如果比max_tokens大,会继续循环处理
                cur_tokens = self.calc_tokens()
            else:
                cur_tokens = cur_tokens - max_tokens  
        return cur_tokens # 返回最终的token数
    # 计算当前会话的token数
    def calc_tokens(self):
        return num_tokens_from_messages(self.messages)
# 计算消息列表使用的token数
def num_tokens_from_messages(messages):
    """返回消息列表所使用的token数。"""
    # 说明：1个中文token通常对应一个汉字，1个英文token通常对应3-4个字母或1个单词
    # 详细规则可以参考阿里云文档：https://help.aliyun.com/document_detail/2586397.html
    # 目前采用字符串长度的粗略估算方式来计算token数
    tokens = 0 # 初始化token计数
    # 遍历所有消息，累加每条消息的长度（即字符数）作为token数
    for msg in messages:
        tokens += len(msg["content"])
    return tokens 
