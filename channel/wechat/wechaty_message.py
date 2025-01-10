import asyncio # 导入asyncio，用于异步编程
import re # 导入正则表达式模块
# wechaty 是一个开源的聊天机器人框架，支持多种聊天平台（如微信、Telegram、Slack 等），通过它可以方便地创建和管理聊天机器人。
from wechaty import MessageType # 导入微信消息类型
from wechaty.user import Message # 导入Wechaty消息类

from bridge.context import ContextType # 导入上下文类型（如文本、语音等）
from channel.chat_message import ChatMessage  # 导入聊天消息基类
from common.log import logger # 导入日志模块
from common.tmp_dir import TmpDir # 导入临时目录管理类

class aobject(object):
    async def __new__(cls, *a, **kw):
        instance = super().__new__(cls) # 创建实例
        await instance.__init__(*a, **kw) # 异步初始化
        return instance # 返回实例

    async def __init__(self):
        pass # 默认的异步初始化方法

# 因为实例的创建是先new,后init,所以是先调用aobject的new方法,之后调用object的new方法,之后异步等待WechatyMessage
# 的init方法,之后调用ChatMessage的init方法,之后调用WechatyMessage后面的一堆初始化，最后调用aobject.new中的return instance返回实例
class WechatyMessage(ChatMessage, aobject):
    async def __init__(self, wechaty_msg: Message):
        #  wechaty_msg是wechaty框架的消息对象,这里传入参数了,所以调用的是ChatMessage的初始化方法
        super().__init__(wechaty_msg) 
        room = wechaty_msg.room()  # 获取消息所属的群（如果是群消息）
        self.msg_id = wechaty_msg.message_id  # 消息的唯一标识
        self.create_time = wechaty_msg.payload.timestamp # 消息创建时间
        self.is_group = room is not None # 判断消息是否为群消息
        # 如果消息类型为文本
        if wechaty_msg.type() == MessageType.MESSAGE_TYPE_TEXT:
            self.ctype = ContextType.TEXT # 消息类型为文本
            self.content = wechaty_msg.text() # 获取文本内容
        # 如果消息类型是语音
        elif wechaty_msg.type() == MessageType.MESSAGE_TYPE_AUDIO:
            self.ctype = ContextType.VOICE # 设置消息类型为语音
            # wechaty_msg.to_file_box() 是一个异步方法，这意味着它是一个 协程函数。协程函数（由 async def 定义的函数）
            # 返回的并不是直接的结果，而是一个协程对象,这里await会挂起协程
            voice_file = await wechaty_msg.to_file_box()  
            self.content = TmpDir().path() + voice_file.name   # 将语音文件保存到临时目录
            # 定义异步函数，确保文件保存到正确的路径
            def func():
                loop = asyncio.get_event_loop()  # 获取当前事件循环
                # 这个是把携程对象交给事件循环执行
                asyncio.run_coroutine_threadsafe(voice_file.to_file(self.content), loop).result() # 异步保存文件
            # 第一步：asyncio.run_coroutine_threadsafe(voice_file.to_file(self.content), loop) 会将协程 voice_file.to_file
            # (self.content) 提交给事件循环。
            # 第二步：.result() 会阻塞当前线程，直到文件保存任务执行完毕。这里的阻塞是为了确保文件保存操作完成后再进行后续操作。
            # 第三步：self._prepare_fn = func 会将 func 保存到 self._prepare_fn，但这行代码 在 result() 执行完之前不会执行。
            self._prepare_fn = func # 保存异步函数
        else: # 不支持的消息类型,抛出异常
            raise NotImplementedError("Unsupported message type: {}".format(wechaty_msg.type()))
        
        from_contact = wechaty_msg.talker() # 获取消息的发送者
        self.from_user_id = from_contact.contact_id # 发送者的用户ID
        self.from_user_nickname = from_contact.name  # 发送者的昵称
        # group中的from和to，wechaty跟itchat含义不一样
        # wecahty: from是消息实际发送者, to:所在群
        # itchat: 如果是你发送群消息，from和to是你自己和所在群，如果是别人发群消息，from和to是所在群和你自己
        # 但这个差别不影响逻辑，group中只使用到：1.用from来判断是否是自己发的，2.actual_user_id来判断实际发送用户
        # 用来设置to_user_id
        if self.is_group: # 如果是群聊
            self.to_user_id = room.room_id # 群聊的接收者为群ID
            self.to_user_nickname = await room.topic()  # 群聊的名称
        else: # 如果是私聊
            to_contact = wechaty_msg.to() # 获取接收者（如果是私聊消息）
            self.to_user_id = to_contact.contact_id # 接收者的用户ID
            self.to_user_nickname = to_contact.name # 接收者的昵称
        # 如果是群消息，other_user设置为群，如果是私聊消息(or后边)，而且自己发的，就设置成对方。
        if self.is_group or wechaty_msg.is_self():  
            self.other_user_id = self.to_user_id
            self.other_user_nickname = self.to_user_nickname
        else: # 除去上面的条件,就剩下是私聊,并且是别人发的
            self.other_user_id = self.from_user_id # 这时因为是别人发的,设置为发送消息者的id
            self.other_user_nickname = self.from_user_nickname 
        # 如果是群聊
        # 这段代码的目的是检查机器人是否在群聊消息中被提及。如果消息中没有直接使用 @机器人 的方式来提及机器人，代码会通过检查
        # 消息内容中是否包含机器人的名字（通常发生在复制粘贴的情况下）来判断机器人是否应当回应该消息。
        if self.is_group:  # wechaty群聊中，实际发送用户就是from_user
            # 检查消息是否有使用微信提供的 @自己 功能来标记当前用户。如果返回 True，表示当前用户被直接@了。
            # wechaty_msg.wechaty.user_self().name 获取的是机器人的名字，用来匹配消息内容是否包含 @ 符号和机器人的名称。
            self.is_at = await wechaty_msg.mention_self()  # 获取机器人自己是否被@ 
            if not self.is_at: # 如果没被@
                # 复制粘贴的消息中可能仍然包含了 @ 符号和机器人。为了兼容这种情况，代码通过正则表达式进一步检查了消息内容，确保能正确识别“被@”的情况。
                name = wechaty_msg.wechaty.user_self().name  # 机器人的名称
                pattern = f"@{re.escape(name)}(\u2005|\u0020)" # 构造匹配@机器人自己的名称的正则表达式
                if re.search(pattern, self.content): # 如果文本内容中包含@机器人名称
                    logger.debug(f"wechaty message {self.msg_id} include at")  # 打印日志
                    self.is_at = True # 设置标记为True
            # 在群聊中，实际发送用户是发送者
            self.actual_user_id = self.from_user_id
            self.actual_user_nickname = self.from_user_nickname
