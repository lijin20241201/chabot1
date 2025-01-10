import re # 导入正则表达式模块
from bridge.context import ContextType
from channel.chat_message import ChatMessage
from common.log import logger
from common.tmp_dir import TmpDir
from lib import itchat # 导入itchat库，用于微信相关的操作
from lib.itchat.content import *  # 导入itchat.content中的所有常量和功能
# 封装的itchat的消息
class WechatMessage(ChatMessage):  # 定义WechatMessage类，继承自ChatMessage
    # itchat_msg 是一个字典对象，它代表了一条微信消息的详细信息，通常是从 itchat 库获取的原始消息数据。
    # 具体来说，itchat_msg 包含了关于微信消息的各类字段，包括消息的类型、发送者、接收者、消息内容等。
    def __init__(self, itchat_msg, is_group=False):  # 构造函数，初始化微信消息对象
        super().__init__(itchat_msg) # 调用父类构造函数
        self.msg_id = itchat_msg["MsgId"] # 消息ID
        self.create_time = itchat_msg["CreateTime"] # 消息创建时间
        self.is_group = is_group # 是否为群消息
        # 你可以通过将不同语言的“加入群聊”相关的通知关键词添加到 notes_join_group 列表中，来使程序支持更多语言的适配
        notes_join_group = ["加入群聊", "加入了群聊", "invited", "joined"] # 适配加入群聊通知的关键词
        notes_bot_join_group = ["邀请你", "invited you", "You've joined", "你通过扫描"]  # 适配邀请机器人加入群聊的关键词
        notes_exit_group = ["移出了群聊", "removed"]  # 适配踢出群聊通知的关键词
        notes_patpat = ["拍了拍我", "tickled my", "tickled me"] # 适配拍一拍通知的关键词
        # 根据不同的消息类型做不同的处理
        if itchat_msg["Type"] == TEXT: # 如果消息类型是文本
            self.ctype = ContextType.TEXT # 设置消息类型为文本
            self.content = itchat_msg["Text"]  # 设置消息内容
        elif itchat_msg["Type"] == VOICE: # 如果消息类型是语音
            self.ctype = ContextType.VOICE # 设置消息类型为语音
            self.content = TmpDir().path() + itchat_msg["FileName"]  # 设置content为语音文件的存储路径
            self._prepare_fn = lambda: itchat_msg.download(self.content)  # 下载语音文件的函数
        elif itchat_msg["Type"] == PICTURE and itchat_msg["MsgType"] == 3:  # 如果消息类型是图片
            self.ctype = ContextType.IMAGE # 设置消息类型为图片
            self.content = TmpDir().path() + itchat_msg["FileName"]  # 设置图片文件的存储路径
            self._prepare_fn = lambda: itchat_msg.download(self.content)  # 下载图片文件的函数
        elif itchat_msg["Type"] == NOTE and itchat_msg["MsgType"] == 10000: # 如果消息类型是通知
            if is_group: # 如果是群消息
                if any(note_bot_join_group in itchat_msg["Content"] for note_bot_join_group in notes_bot_join_group): # 如果是机器人加入群聊
                    logger.warn("机器人加入群聊消息，不处理~") # 记录日志，跳过处理
                    pass
                elif any(note_join_group in itchat_msg["Content"] for note_join_group in notes_join_group):# 如果是成员加入群聊
                    if "加入群聊" not in itchat_msg["Content"]: # 如果不是"加入群聊"的通知
                        self.ctype = ContextType.JOIN_GROUP # 设置消息类型为加入群聊
                        self.content = itchat_msg["Content"] # 设置消息内容
                        if "invited" in itchat_msg["Content"]: # 匹配英文邀请加入
                            # 使用正则提取被邀请人的昵称
                            self.actual_user_nickname = re.findall(r'invited\s+(.+?)\s+to\s+the\s+group\s+chat', itchat_msg["Content"])[0]
                        elif "joined" in itchat_msg["Content"]: # 匹配通过二维码加入的英文信息
                            self.actual_user_nickname = re.findall(r'"(.*?)" joined the group chat via the QR Code shared by', itchat_msg["Content"])[0]  # 提取昵称
                        elif "加入了群聊" in itchat_msg["Content"]:  # 如果是中文的加入了群聊通知
                            self.actual_user_nickname = re.findall(r"\"(.*?)\"", itchat_msg["Content"])[-1]
                    elif "加入群聊" in itchat_msg["Content"]:  # 如果是中文的加入群聊通知
                        self.ctype = ContextType.JOIN_GROUP # 设置为加入群聊类型
                        self.content = itchat_msg["Content"] # 设置消息内容
                        self.actual_user_nickname = re.findall(r"\"(.*?)\"", itchat_msg["Content"])[0] # 提取用户昵称

                elif any(note_exit_group in itchat_msg["Content"] for note_exit_group in notes_exit_group):  # 如果是踢出群聊通知
                    self.ctype = ContextType.EXIT_GROUP # 设置消息类型为退出群聊
                    self.content = itchat_msg["Content"] # 设置消息内容
                    self.actual_user_nickname = re.findall(r"\"(.*?)\"", itchat_msg["Content"])[0] # 提取用户昵称

                elif any(note_patpat in itchat_msg["Content"] for note_patpat in notes_patpat):  # 如果是拍一拍通知
                    self.ctype = ContextType.PATPAT # 设置消息类型为拍一拍
                    self.content = itchat_msg["Content"] # 设置消息内容
                    if "拍了拍我" in itchat_msg["Content"]: # 识别中文的拍一拍通知
                        self.actual_user_nickname = re.findall(r"\"(.*?)\"", itchat_msg["Content"])[0]  # 提取昵称
                    elif "tickled my" in itchat_msg["Content"] or "tickled me" in itchat_msg["Content"]: # 识别英文的拍一拍通知
                        self.actual_user_nickname = re.findall(r'^(.*?)(?:tickled my|tickled me)', itchat_msg["Content"])[0]
                else:  # 不支持的通知消息类型抛出异常
                    raise NotImplementedError("Unsupported note message: " + itchat_msg["Content"])
            # 如果是私聊消息(添加好友的私聊消息)       
            elif "你已添加了" in itchat_msg["Content"]: # 如果是好友添加通知
                self.ctype = ContextType.ACCEPT_FRIEND # 设置消息类型为接受好友
                self.content = itchat_msg["Content"] # 设置消息内容
            # 如果是私聊消息(拍一拍的私聊消息)
            elif any(note_patpat in itchat_msg["Content"] for note_patpat in notes_patpat):  
                self.ctype = ContextType.PATPAT
                self.content = itchat_msg["Content"]
            else: # 不支持的通知消息类型抛出异常
                raise NotImplementedError("Unsupported note message: " + itchat_msg["Content"])
        elif itchat_msg["Type"] == ATTACHMENT: # 如果消息类型为文件附件
            self.ctype = ContextType.FILE # 设置为文件类型
            self.content = TmpDir().path() + itchat_msg["FileName"] # 设置文件存储路径
            self._prepare_fn = lambda: itchat_msg.download(self.content)  # 下载文件的函数
        elif itchat_msg["Type"] == SHARING: # 如果是分享消息
            self.ctype = ContextType.SHARING  # 设置消息类型为分享
            self.content = itchat_msg.get("Url") # 获取分享的URL
        else: # 如果消息类型不支持
            raise NotImplementedError("Unsupported message type: Type:{} MsgType:{}".format(itchat_msg["Type"], itchat_msg["MsgType"]))
        # 设置消息的发送者和接收者ID
        self.from_user_id = itchat_msg["FromUserName"]
        self.to_user_id = itchat_msg["ToUserName"]
        # 这个字段存储的是当前 登录的微信账号（机器人账号） 的微信ID。也就是，你扫码登录时使用的那个微信账号的ID
        user_id = itchat.instance.storageClass.userName 
        nickname = itchat.instance.storageClass.nickName 
        # 如果发送消息者是机器人
        if self.from_user_id == user_id:
            self.from_user_nickname = nickname # 就设置发送人的昵称是机器人昵称
        # 如果接收者是机器人
        if self.to_user_id == user_id: 
            self.to_user_nickname = nickname # 就设置接收人的昵称是机器人昵称
        try: # self.my_msg = True 的意思是 消息是机器人接收到的来自其他用户的消息，而不是机器人自己发送的消息。
            # 所以，它用来区分机器人收到的消息和机器人自己发送的消息。
            self.my_msg = itchat_msg["ToUserName"] == itchat_msg["User"]["UserName"] and \
                          itchat_msg["ToUserName"] != itchat_msg["FromUserName"]
            self.other_user_id = itchat_msg["User"]["UserName"]
            self.other_user_nickname = itchat_msg["User"]["NickName"]
            if self.other_user_id == self.from_user_id: 
                self.from_user_nickname = self.other_user_nickname
            if self.other_user_id == self.to_user_id:
                self.to_user_nickname = self.other_user_nickname
            if itchat_msg["User"].get("Self"):
                # 自身的展示名，当设置了群昵称时，该字段表示群昵称
                self.self_display_name = itchat_msg["User"].get("Self").get("DisplayName")
        except KeyError as e:  # 处理偶尔没有对方信息的情况
            logger.warn("[WX]get other_user_id failed: " + str(e))
            if self.from_user_id == user_id: # 如果机器人是发送者,那说明用户是接收者
                self.other_user_id = self.to_user_id # 那么设置接收者为对方用户id
            else: # 如果机器人是接收者,那说明用户是发送者,这时设置发送者为对方用户id
                self.other_user_id = self.from_user_id 
        if self.is_group: # 如果是群聊
            self.is_at = itchat_msg["IsAt"] # 设置是否被@
            self.actual_user_id = itchat_msg["ActualUserName"] # 设置真实用户id
            if self.ctype not in [ContextType.JOIN_GROUP, ContextType.PATPAT, ContextType.EXIT_GROUP]:
                self.actual_user_nickname = itchat_msg["ActualNickName"] # 设置真实用户昵称
