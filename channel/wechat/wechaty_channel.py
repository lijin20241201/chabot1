# encoding:utf-8

import asyncio
import base64
import os
import time

from wechaty import Contact, Wechaty # 引入Wechaty模块，用于与微信的交互
from wechaty.user import Message # 引入Message模块，用于处理消息
from wechaty_puppet import FileBox # 引入FileBox，用于处理文件

from bridge.context import * 
from bridge.context import Context 
from bridge.reply import *
from channel.chat_channel import ChatChannel 
from channel.wechat.wechaty_message import WechatyMessage # 引入自定义的WechatyMessage类
from common.log import logger # 引入日志模块
from common.singleton import singleton # 引入单例模式工具
from config import conf
# 尝试导入音频转换工具模块
try:
    from voice.audio_convert import any_to_sil # 用于将音频转换为.sil格式
except Exception as e:
    pass # 如果导入失败则不做处理
# ChatChannel：通用的消息通道类，包含了基本的消息收发逻辑，适用于所有类型的消息通道。
# WechatyChannel：继承自 ChatChannel，是专门为微信通道定制的类，包含了与微信互动的具体逻辑（比如 Wechaty 的实例化、登录、消息监听等）。
@singleton # 使用单例模式
class WechatyChannel(ChatChannel): # 继承ChatChannel类
    NOT_SUPPORT_REPLYTYPE = [] # 不支持的回复类型，空列表表示当前无不支持类型
    def __init__(self):
        super().__init__()  # 调用父类的构造函数
    def startup(self):
        config = conf() # 获取配置
        # 这个token需要申请wechaty来获取
        token = config.get("wechaty_puppet_service_token")  # 从配置中获取token
        os.environ["WECHATY_PUPPET_SERVICE_TOKEN"] = token # 设置环境变量
        asyncio.run(self.main()) # 异步运行main函数
    # main 是异步启动方法：main(self) 是一个异步函数（async def），它用于启动 Wechaty 机器人并开始监听和处理事件。它是在启动过程中调用的，
    # 用于初始化和启动所有需要的协程。因为 Wechaty 需要与微信 API 进行异步交互，所以它必须放在一个异步函数中启动。你不能在 __init__ 中执行 
    # await，而需要将其放入异步方法（main）中
    # handler_pool 是模块级的全局变量，它在整个模块中是共享的，因此 WechatyChannel 和 ChatChannel 都可以访问它。
    # self.handler_pool 访问的是 模块级的全局变量，因为 WechatyChannel 类没有显式定义 handler_pool。
    # self 是类的实例，但由于 handler_pool 是全局变量并且没有在类中覆盖它，所以访问 self.handler_pool 时会自动访问模块级的 handler_pool。
    # (就是父类模块中的那个全局线程池)多线程和事件循环的绑定 (_initializer) 是为了确保每个工作线程都有自己的事件循环。
    # 每个线程都会绑定一个事件循环，但这些事件循环是独立的，并且 每个线程有自己的事件循环实例。
    async def main(self):
        loop = asyncio.get_event_loop() # 获取当前事件循环
        # 将asyncio的loop传入处理线程
        # main 中设置的属性确实是属于子类实例的。你在 main 方法中初始化了 self.bot，并且绑定了登录和消息处理的事件。
        # 这些都是通过子类（即 WechatyChannel）实例化后设置的属性。
        # 虽然 loop 是在主线程中创建的，但是每个线程都会复制一个事件循环对象。这些事件循环对象是独立的，每个线程都会拥有自己独立的 
        # asyncio 环境。这是因为 asyncio 需要为每个线程维护自己的任务队列、I/O 操作和回调等。
        self.handler_pool._initializer = lambda: asyncio.set_event_loop(loop)
        self.bot = Wechaty() # 初始化Wechaty对象
        self.bot.on("login", self.on_login) # 绑定登录事件处理
        self.bot.on("message", self.on_message) # 绑定消息事件处理
        await self.bot.start()  # 启动Wechaty bot

    async def on_login(self, contact: Contact):
        self.user_id = contact.contact_id # 设置当前用户ID
        self.name = contact.name # 设置当前用户名称
        logger.info("[WX] login user={}".format(contact))  # 打印登录信息

    # 统一的发送函数，每个Channel自行实现，根据reply的type字段发送不同类型的消息
    def send(self, reply: Reply, context: Context):
        receiver_id = context["receiver"] # 获取接收者ID
        loop = asyncio.get_event_loop()  # 获取当前事件循环
        # asyncio.run_coroutine_threadsafe 主要用于在 非异步线程 中调度 异步协程。
        # 线程安全：它是线程安全的，允许你在不同的线程中调度异步任务而不产生竞态条件。
        # 使用场景：它通常用于多线程环境中，需要调度异步任务的情况。例如，当你有一个主线程运行事件循环，但有一些任务在子线程中完成
        # 时，可以通过它将异步任务安全地调度到主线程的事件循环中执行。
        if context["isgroup"]:  # 如果是群组消息
            # 根据群聊的 ID 找到对应的 Room 对象，进而执行群聊相关的操作。
            receiver = asyncio.run_coroutine_threadsafe(self.bot.Room.find(receiver_id), loop).result() 
        else:  # 个人消息时，receiver_id 是个人消息接收者的 ID，Contact.find() 方法会找到这个联系人对象。
            receiver = asyncio.run_coroutine_threadsafe(self.bot.Contact.find(receiver_id), loop).result() # 获取联系人对象
        msg = None # 初始化消息
        if reply.type == ReplyType.TEXT: # 如果是文本消息
            msg = reply.content # 文本内容
            asyncio.run_coroutine_threadsafe(receiver.say(msg), loop).result() # 发送文本消息
            logger.info("[WX] sendMsg={}, receiver={}".format(reply, receiver)) # 打印发送日志
        elif reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO: # 如果是错误或信息类型
            msg = reply.content # 内容为错误或信息
            asyncio.run_coroutine_threadsafe(receiver.say(msg), loop).result()  # 发送消息
            logger.info("[WX] sendMsg={}, receiver={}".format(reply, receiver)) # 打印发送日志
        elif reply.type == ReplyType.VOICE:  # 如果是语音消息
            voiceLength = None # 初始化语音长度
            file_path = reply.content # 获取语音文件路径
            sil_file = os.path.splitext(file_path)[0] + ".sil" # 将语音文件转换为.sil格式
            voiceLength = int(any_to_sil(file_path, sil_file)) # 转换音频并获取语音时长
            if voiceLength >= 60000:  # 如果语音长度超过60秒
                voiceLength = 60000 # 将语音时长限制为60秒
                logger.info("[WX] voice too long, length={}, set to 60s".format(voiceLength)) # 打印日志
            # 发送语音
            t = int(time.time()) # 获取当前时间戳
            msg = FileBox.from_file(sil_file, name=str(t) + ".sil") # 创建语音消息
            if voiceLength is not None:  # 如果语音时长存在
                msg.metadata["voiceLength"] = voiceLength # 将语音时长添加到元数据
            asyncio.run_coroutine_threadsafe(receiver.say(msg), loop).result() # 发送语音消息
            try:
                os.remove(file_path) # 删除原始音频文件
                if sil_file != file_path:
                    os.remove(sil_file) # 删除.sil格式文件
            except Exception as e:
                pass # 如果删除文件失败则忽略
            logger.info("[WX] sendVoice={}, receiver={}".format(reply.content, receiver)) # 打印发送日志
        elif reply.type == ReplyType.IMAGE_URL:  # 如果是图片URL
            img_url = reply.content  # 获取图片URL
            t = int(time.time()) # 获取当前时间戳
            msg = FileBox.from_url(url=img_url, name=str(t) + ".png") # 创建图片消息
            asyncio.run_coroutine_threadsafe(receiver.say(msg), loop).result() # 发送图片
            logger.info("[WX] sendImage url={}, receiver={}".format(img_url, receiver)) # 打印发送日志
        elif reply.type == ReplyType.IMAGE:  # 如果是图片文件
            image_storage = reply.content  # 获取图片文件
            image_storage.seek(0) # 重置文件指针
            t = int(time.time()) # 获取当前时间戳
            msg = FileBox.from_base64(base64.b64encode(image_storage.read()), str(t) + ".png") # 创建图片消息
            asyncio.run_coroutine_threadsafe(receiver.say(msg), loop).result() # 发送图片
            logger.info("[WX] sendImage, receiver={}".format(receiver)) # 打印发送日志
    # 当收到消息时触发
    async def on_message(self, msg: Message):
        try:
            cmsg = await WechatyMessage(msg)  # 将消息转换为WechatyMessage对象
        except NotImplementedError as e:
            logger.debug("[WX] {}".format(e))  # 如果消息类型未实现，则记录调试日志
            return  # 返回不做处理
        except Exception as e: # 捕获其他异常并记录
            logger.exception("[WX] {}".format(e))
            return  # 直接 return 会隐式返回 None。
        logger.debug("[WX] message:{}".format(cmsg))  # 打印消息内容
        room = msg.room()  # 获取消息来自的群聊. 如果消息不是来自群聊, 则返回None
        isgroup = room is not None # 判断是否为群聊消息
        ctype = cmsg.ctype # 获取消息类型
        # 调用父类的方法处理消息,包括设置origin_ctype
        context = self._compose_context(ctype, cmsg.content, isgroup=isgroup, msg=cmsg)  
        if context: # 如果有返回
            logger.info("[WX] receiveMsg={}, context={}".format(cmsg, context))   # 打印原消息和处理后的消息
            self.produce(context)   # 把消息放入生产者处理,包括给session_id绑定消息队列和信号量,之后的父类线程调用消费者
