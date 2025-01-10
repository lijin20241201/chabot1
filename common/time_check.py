import re # 导入正则表达式模块
import time # 导入时间处理模块
import config # 导入config模块，用于获取配置
from common.log import logger  # 导入日志记录器

# time_checker装饰器，包装传入的函数f，在调用之前检查时间限制
def time_checker(f):
    def _time_checker(self, *args, **kwargs):
        _config = config.conf() # 获取配置信息
        chat_time_module = _config.get("chat_time_module", False)  # 获取聊天时间模块是否启用

        if chat_time_module: # 如果启用了聊天时间模块
            chat_start_time = _config.get("chat_start_time", "00:00") # 获取配置中的开始时间
            chat_stop_time = _config.get("chat_stop_time", "24:00") # 获取配置中的结束时间
            # 时间格式的正则表达式，验证时间是否符合 HH:MM 格式
            time_regex = re.compile(r"^([01]?[0-9]|2[0-4])(:)([0-5][0-9])$")
            # 如果开始时间或结束时间格式不正确，记录警告并返回
            if not (time_regex.match(chat_start_time) and time_regex.match(chat_stop_time)):
                logger.warning("时间格式不正确，请在config.json中修改CHAT_START_TIME/CHAT_STOP_TIME。")
                return None
            # 获取当前时间（仅时:分部分）,这里假定了开始和结束都是同一天的情况(因为只考虑时分)
            now_time = time.strptime(time.strftime("%H:%M"), "%H:%M")
            chat_start_time = time.strptime(chat_start_time, "%H:%M") # 转换开始时间
            chat_stop_time = time.strptime(chat_stop_time, "%H:%M") # 转换结束时间
            # 结束时间小于开始时间，表示跨天的情况
            if chat_stop_time < chat_start_time and (chat_start_time <= now_time or now_time <= chat_stop_time):
                f(self, *args, **kwargs)
            # 结束时间大于开始时间，表示没有跨天
            elif chat_start_time < chat_stop_time and chat_start_time <= now_time <= chat_stop_time:
                f(self, *args, **kwargs) # 当前时间在服务时间内，执行原函数
            else:
                # 定义匹配规则，如果以 #reconf 或者  #更新配置  结尾, 非服务时间可以修改开始/结束时间并重载配置
                pattern = re.compile(r"^.*#(?:reconf|更新配置)$")
                if args and pattern.match(args[0].content):  # 如果请求内容匹配
                    f(self, *args, **kwargs) # 执行原函数
                else:
                    logger.info("非服务时间内，不接受访问") # 如果不匹配，记录日志并不处理请求
                    return None
        else:
            f(self, *args, **kwargs)  # 如果没有启用时间模块，则直接执行原函数，无限制

    return _time_checker # 返回包装后的函数
