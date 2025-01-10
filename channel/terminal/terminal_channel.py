import sys

from bridge.context import *
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel, check_prefix
from channel.chat_message import ChatMessage
from common.log import logger
from config import conf

# 定义一个终端消息类，用于模拟用户与机器人之间的消息交互
class TerminalMessage(ChatMessage):
    def __init__(
        self,
        msg_id, # 消息唯一标识
        content,  # 消息内容
        ctype=ContextType.TEXT, # 消息类型，默认是文本
        from_user_id="User", # 发送消息的用户 ID，默认是 "User"
        to_user_id="Chatgpt", # 接收消息的用户 ID，默认是 "Chatgpt"
        other_user_id="Chatgpt", # 对方的ID，默认是 "Chatgpt"
    ):
        self.msg_id = msg_id # 初始化消息 ID
        self.ctype = ctype # 初始化消息类型
        self.content = content # 初始化消息内容
        self.from_user_id = from_user_id  # 初始化发送用户 ID
        self.to_user_id = to_user_id  # 初始化接收用户 ID
        self.other_user_id = other_user_id # 初始化对方的ID

# 定义一个终端交互的通道类，模拟聊天机器人在终端中的对话
class TerminalChannel(ChatChannel):
    NOT_SUPPORT_REPLYTYPE = [ReplyType.VOICE] # 定义不支持的回复类型，比如语音类型
    # 定义发送消息的方法，用于输出机器人回复
    def send(self, reply: Reply, context: Context):
        print("\nBot:") # 输出机器人回复的前缀
        if reply.type == ReplyType.IMAGE: # 如果回复类型是图片
            from PIL import Image
            image_storage = reply.content # 获取图片内容
            image_storage.seek(0) # 重置图片数据流的指针位置
            img = Image.open(image_storage)  # 打开图片
            print("<IMAGE>")  # 输出图片标记
            img.show() # 显示图片
        elif reply.type == ReplyType.IMAGE_URL:  # 如果回复类型是图片 URL
            import io
            import requests
            from PIL import Image

            img_url = reply.content # 获取图片的 URL
            pic_res = requests.get(img_url, stream=True) # 从网络下载图片
            image_storage = io.BytesIO()  # 创建一个内存字节流对象
            for block in pic_res.iter_content(1024): # 分块读取图片数据
                image_storage.write(block) # 写入字节流
            image_storage.seek(0) # 重置字节流的指针位置
            img = Image.open(image_storage) # 打开图片
            print(img_url) # 输出图片 URL
            img.show()  # 显示图片
        else: # 如果回复类型是文本
            print(reply.content) # 输出文本内容
        print("\nUser:", end="")  # 提示用户输入下一条消息
        sys.stdout.flush() # 刷新标准输出缓冲区
        return
    
    def startup(self):
        context = Context() # 初始化消息上下文对象
        logger.setLevel("WARN") # 设置日志级别为 "WARN"（仅显示警告及以上的日志）
        print("\nPlease input your question:\nUser:", end="") # 提示用户输入问题
        sys.stdout.flush() # 刷新标准输出缓冲区
        msg_id = 0  # 初始化消息 ID
        while True: # 循环监听用户输入
            try:
                prompt = self.get_input() # 获取用户输入内容
            except KeyboardInterrupt:  # 捕获用户中断（Ctrl+C）事件
                print("\nExiting...") # 输出退出提示
                sys.exit() # 终止程序
            msg_id += 1 # 自增消息 ID
            # 获取配置中的触发前缀，默认为空字符串
            trigger_prefixs = conf().get("single_chat_prefix", [""])
            if check_prefix(prompt, trigger_prefixs) is None: # 检查用户输入是否包含触发前缀
                prompt = trigger_prefixs[0] + prompt  # 给没触发前缀的消息加上触发前缀
            # 对用户消息做一些基础的处理,msg作为context的一个属性被设置到context
            context = self._compose_context(ContextType.TEXT, prompt, msg=TerminalMessage(msg_id, prompt))
            context["isgroup"] = False  # 设置为私聊
            if context: # 如果返回消息,把消息放入消息队列,和session_Id绑定,并放入self.sessions中
                self.produce(context)
            else: # 如果没有返回,抛出异常
                raise Exception("context is None")
    # 单行输入
    def get_input(self):
        # 刷新标准输出缓冲区，确保之前输出的内容立即显示在终端中。这在提示用户输入时很有用，因为终端输出可能被缓冲。
        sys.stdout.flush()
        # 调用 input()，程序会暂停，等待用户输入。用户输入的内容（字符串）在按下回车键后被返回，并存储在变量 line 中。
        line = input() 
        return line # 返回用户输入内容
