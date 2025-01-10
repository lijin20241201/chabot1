import sys
import time
import web
import json
from queue import Queue  # 用于实现消息队列
from bridge.context import *
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel, check_prefix
from channel.chat_message import ChatMessage
from common.log import logger
from common.singleton import singleton
from config import conf
import os

# 定义Web消息类，继承ChatMessage
class WebMessage(ChatMessage):
    def __init__(
        self,
        msg_id,  # 消息ID，唯一标识一条消息
        content, # 消息内容
        ctype=ContextType.TEXT, # 消息类型，默认为文本
        from_user_id="User", # 发送消息的用户ID，默认为"User"
        to_user_id="Chatgpt", # 接收消息的用户ID，默认为"Chatgpt"
        other_user_id="Chatgpt",  # 对方的ID，默认为"Chatgpt"
    ):
        self.msg_id = msg_id # 初始化消息ID
        self.ctype = ctype # 初始化消息类型
        self.content = content # 初始化消息内容
        self.from_user_id = from_user_id  # 初始化发送方ID
        self.to_user_id = to_user_id # 初始化接收方ID
        self.other_user_id = other_user_id # 初始化对方的ID
# 定义Web聊天通道，使用单例模式
@singleton
class WebChannel(ChatChannel):
    NOT_SUPPORT_REPLYTYPE = [ReplyType.VOICE] # 定义不支持的回复类型，如语音
    _instance = None # 单例实例
    
    # def __new__(cls):
    #     if cls._instance is None:
    #         cls._instance = super(WebChannel, cls).__new__(cls)
    #     return cls._instance
    # 初始化函数
    def __init__(self):
        super().__init__() # 调用父类的初始化方法
        self.message_queues = {}  # user_id-->消息队列
        self.msg_id_counter = 0  # 初始化消息ID计数器
    # 生成唯一消息ID的方法
    def _generate_msg_id(self):
        self.msg_id_counter += 1 # 增加消息计数器
        return str(int(time.time())) + str(self.msg_id_counter) # 返回时间戳+计数器组合的ID
    # 发送回复消息的方法
    def send(self, reply: Reply, context: Context):
        try:
            if reply.type == ReplyType.IMAGE: # 如果回复类型是图片
                from PIL import Image # 导入Pillow库处理图片
                image_storage = reply.content # 获取图片内容
                image_storage.seek(0)  # 重置文件指针
                img = Image.open(image_storage) # 打开图片
                print("<IMAGE>") # 输出占位符表示图片
                img.show() # 显示图片
            elif reply.type == ReplyType.IMAGE_URL: # 如果回复类型是图片URL
                import io # 导入IO模块
                import requests
                from PIL import Image
                img_url = reply.content # 获取图片的URL
                pic_res = requests.get(img_url, stream=True) # 通过流式请求获取图片数据
                image_storage = io.BytesIO()  # 创建内存缓冲区
                for block in pic_res.iter_content(1024):  # 每次读取1KB数据
                    image_storage.write(block) # 写入缓冲区
                image_storage.seek(0) # 重置文件指针
                img = Image.open(image_storage) # 打开图片
                print(img_url) # 输出图片URL
                img.show() # 显示图片
            else: # 如果是其他类型的回复
                print(reply.content) # 直接输出回复内容

            # 获取用户ID，如果没有则使用默认值
            # user_id = getattr(context.get("session", None), "session_id", "default_user")
            user_id = context["receiver"]
            # 如果用户ID没有对应的消息队列，则为其创建一个
            if user_id not in self.message_queues:
                self.message_queues[user_id] = Queue()
            # 构造消息数据结构
            message_data = {
                "type": str(reply.type), # 消息类型
                "content": reply.content, # 消息内容
                "timestamp": time.time()  # 消息时间戳
            }
            # 将消息加入对应用户的队列
            self.message_queues[user_id].put(message_data)
            logger.debug(f"Message queued for user {user_id}") # 日志记录消息入队成功
        except Exception as e: # 日志记录异常信息
            logger.error(f"Error in send method: {e}")
            raise  # 抛出异常
    # 处理 Server-Sent Events (SSE) 实现实时通信。
    def sse_handler(self, user_id):
        # 设置响应头，表明是 SSE 流
        web.header('Content-Type', 'text/event-stream') # 指定返回的内容类型为 SSE
        web.header('Cache-Control', 'no-cache') # 禁止缓存，确保实时性
        web.header('Connection', 'keep-alive') # 保持连接不断开，持续推送数据
        # 确保用户有对应的消息队列，如果没有则初始化一个
        if user_id not in self.message_queues:
            self.message_queues[user_id] = Queue()
        
        try:    
            while True:  # 不断循环，持续发送数据
                try:
                    # 发送心跳消息，防止连接超时
                    yield f": heartbeat\n\n"  # SSE 的注释消息格式，以确保连接活跃
                    # 检查用户消息队列是否有新消息（非阻塞）
                    if not self.message_queues[user_id].empty():
                        message = self.message_queues[user_id].get_nowait() # 从消息队列中非阻塞地获取消息
                        # 将消息内容转为 JSON 格式并发送到客户端
                        yield f"data: {json.dumps(message)}\n\n"
                    time.sleep(0.5) # 延迟 0.5 秒，降低 CPU 占用率
                except Exception as e: # 出现异常时,记录错误日志并中断循环
                    logger.error(f"SSE Error: {e}")
                    break
        finally:
            # 清理资源，确保不会因为中断或异常导致内存泄漏
            if user_id in self.message_queues:
                # 如果用户队列为空，则删除用户id和其对应的消息队列
                if self.message_queues[user_id].empty():
                    del self.message_queues[user_id]
    # 处理用户通过 POST 请求发送的消息。
    def post_message(self):
        try:
            data = web.data()  # 获取原始 POST 数据
            json_data = json.loads(data) # 将数据解析为 JSON 格式
            # 从 JSON 数据中提取用户 ID，默认值为 'default_user'
            user_id = json_data.get('user_id', 'default_user')
            # 从 JSON 数据中提取消息内容
            prompt = json_data.get('message', '')
        except json.JSONDecodeError: # 如果 JSON 解析失败，返回错误信息
            return json.dumps({"status": "error", "message": "Invalid JSON"})
        except Exception as e: # 处理其他异常，返回错误信息
            return json.dumps({"status": "error", "message": str(e)})
        # 如果没有消息,返回一个没有消息的错误信息
        if not prompt:
            return json.dumps({"status": "error", "message": "No message provided"})
            
        try:
            msg_id = self._generate_msg_id() # 生成唯一消息 ID
            # 对用户消息做基本的处理(去除@，添加receiver,原类型等),msg会变成context的kwargs中的属性
            context = self._compose_context(ContextType.TEXT, prompt, msg=WebMessage(msg_id, 
                                                                                     prompt,
                                                                                     from_user_id=user_id,
                                                                                     other_user_id = user_id
                                                                                     ))
            context["isgroup"] = False # 设置为私聊模式
            # context["session"] = web.storage(session_id=user_id)
            if not context: # 如果没有contexxt,返回一个错误信息的回复
                return json.dumps({"status": "error", "message": "Failed to process message"})
            # 到这里,一定有消息,这时放入生产者内部,绑定会话id和消息队列等的对应关系
            self.produce(context)
            return json.dumps({"status": "success", "message": "Message received"}) # 返回成功响应
        except Exception as e: # 出现异常时,记录错误日志并返回服务器错误信息
            logger.error(f"Error processing message: {e}")
            return json.dumps({"status": "error", "message": "Internal server error"})
    # 提供聊天 HTML 页面服务。使用绝对路径定位 HTML 文件
    def chat_page(self):
        file_path = os.path.join(os.path.dirname(__file__), 'chat.html') # 使用绝对路径定位 HTML 文件
        with open(file_path, 'r', encoding='utf-8') as f:  # 打开 HTML 文件并读取内容，指定编码为 UTF-8
            return f.read() # 返回 HTML 内容
    def startup(self): # 启动 WebChannel 服务。
        logger.setLevel("WARN") # 设置日志级别为 WARN，减少日志输出量
        # 输出 Web 通道启动信息，告知用户如何发送 POST 请求
        print("\nWeb Channel is running. Send POST requests to /message to send messages.")
        # 定义 URL 路由和对应的处理类
        urls = (
            '/sse/(.+)', 'SSEHandler',  # 定义 SSE 路由，用于处理用户实时推送事件，包含用户ID参数
            '/message', 'MessageHandler',  # 定义 POST 消息路由，用于接收用户发送的消息
            '/chat', 'ChatHandler',  # 定义聊天页面路由，用于提供 HTML 聊天页面
        )
        port = conf().get("web_port", 9899) # 获取配置中的端口号，默认为 9899
        # 创建 web.py 应用对象，并设置 autoreload=False 防止频繁重启
        app = web.application(urls, globals(), autoreload=False)
        # 启动 HTTP 服务器，监听所有网络接口上的指定端口
        web.httpserver.runsimple(app.wsgifunc(), ("0.0.0.0", port))
# 处理 SSE（Server-Sent Events）请求的类。
class SSEHandler:
    def GET(self, user_id): # 调用 WebChannel 的 sse_handler 方法，处理实时推送逻辑
        return WebChannel().sse_handler(user_id)

# 处理 POST 消息的类。
class MessageHandler:
    # 调用 WebChannel 的 post_message 方法，处理用户通过 POST 提交的消息
    def POST(self):
        return WebChannel().post_message()

# 提供聊天页面的类。
class ChatHandler:
    # 调用 WebChannel 的 chat_page 方法，返回聊天 HTML 页面内容
    def GET(self):
        return WebChannel().chat_page()
