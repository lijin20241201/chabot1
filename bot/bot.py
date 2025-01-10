from bridge.context import Context
from bridge.reply import Reply

# bot基类
class Bot(object):
    def reply(self, query, context: Context = None) -> Reply: # 回复方法
        
        raise NotImplementedError
