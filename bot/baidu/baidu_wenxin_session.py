from bot.session_manager import Session
from common.log import logger

"""
    # 消息列表(可以看到是一条用户消息,一条助手消息,这样往复)
     [
        {"role": "user", "content": "Who won the world series in 2020?"},
        {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
        {"role": "user", "content": "Where was it played?"}
    ]
"""


class BaiduWenxinSession(Session):
    def __init__(self, session_id, system_prompt=None, model="gpt-3.5-turbo"):
        super().__init__(session_id, system_prompt)  # 调用父类的初始化方法，初始化session_id和system_prompt
        self.model = model # 设置模型类型（默认为gpt-3.5-turbo）
        # 百度文心不支持system prompt
        # self.reset()
    # 用于设定多轮对话中,超出限制后,删除最早的轮次的对话
    def discard_exceeding(self, max_tokens, cur_tokens=None):
        precise = True  # 默认使用精确计算token数量
        try:
            cur_tokens = self.calc_tokens()  # 尝试计算当前tokens数量
        except Exception as e:
            precise = False # 如果精确计算失败，设置为不精确计算
            if cur_tokens is None: # 如果在计算过程中出现异常,并且cur_tokens为None,程序中断
                raise e
            logger.debug("Exception when counting tokens precisely for query: {}".format(e)) # 记录token计算异常
        while cur_tokens > max_tokens: # 当当前token数量超过最大限制时，开始丢弃历史消息
            if len(self.messages) >= 2: # 如果消息列表中有2条及以上消息
                 # 删除第一个消息,这个操作其实是删除最早的一轮用户对话(但是有个潜在的条件,其实是不可能只有两个的，如果用户消息不允许分段的话)
                self.messages.pop(0)
                self.messages.pop(0) # 删除第二个消息
            else:  # 如果消息列表中少于2条消息,记录日志，显示最大token数、总token数和消息长度
                logger.debug("max_tokens={}, total_tokens={}, len(messages)={}".format(max_tokens, cur_tokens, len(self.messages)))
                break # 退出循环，不丢弃,因为只有最新的用户提示
            if precise: # 如果之前是精确计算token数
                cur_tokens = self.calc_tokens() # 重新计算当前token数
            else: # 如果是粗略计算token数
                cur_tokens = cur_tokens - max_tokens # 直接减少最大token数
        return cur_tokens  # 返回最终的token数量
    # 调用num_tokens_from_messages函数计算当前消息列表的token数量
    def calc_tokens(self):
        return num_tokens_from_messages(self.messages)
# 计算消息列表中的总token数
def num_tokens_from_messages(messages):
    tokens = 0
    for msg in messages:
        # 官方token计算规则暂不明确： "大约为 token数为 "中文字 + 其他语种单词数 x 1.3"
        # 这里先直接根据字数粗略估算吧，暂不影响正常使用，仅在判断是否丢弃历史会话的时候会有偏差
        tokens += len(msg["content"])  # 将每条消息的字数作为token数累加
    return tokens
