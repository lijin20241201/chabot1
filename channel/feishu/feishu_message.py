from bridge.context import ContextType
from channel.chat_message import ChatMessage
import json
import requests
from common.log import logger
from common.tmp_dir import TmpDir
from common import utils

# 定义FeishuMessage类，继承自ChatMessage类
class FeishuMessage(ChatMessage):
    # 初始化方法，接受事件字典、是否为群聊标识、以及access_token作为参数
    def __init__(self, event: dict, is_group=False, access_token=None):
        super().__init__(event) # 调用父类的初始化方法
        msg = event.get("message") # 从事件中获取消息部分
        sender = event.get("sender")  # 从事件中获取发送者信息
        self.access_token = access_token # 设置access_token
        self.msg_id = msg.get("message_id")  # 获取消息ID
        self.create_time = msg.get("create_time")  # 获取消息创建时间
        self.is_group = is_group # 设置是否为群聊
        msg_type = msg.get("message_type") # 获取消息类型
        if msg_type == "text":  # 如果消息类型为文本
            self.ctype = ContextType.TEXT # 设置消息类型为文本
            content = json.loads(msg.get('content')) # 解析消息内容（JSON格式）
            self.content = content.get("text").strip()  # 获取文本内容并去除前后空格
        elif msg_type == "file": # 如果消息类型为文件
            self.ctype = ContextType.FILE # 设置消息类型为文件
            content = json.loads(msg.get("content")) # 解析文件内容（JSON格式）
            file_key = content.get("file_key")  # 获取文件的唯一键
            file_name = content.get("file_name") # 获取文件名
            # 设置文件保存路径
            self.content = TmpDir().path() + file_key + "." + utils.get_path_suffix(file_name)
             # 定义文件下载函数
            def _download_file():
                # 如果响应状态码是200，则将响应内容写入本地文件
                url = f"https://open.feishu.cn/open-apis/im/v1/messages/{self.msg_id}/resources/{file_key}"  # 设置文件下载URL
                # 设置Authorization头部，值为Bearer加上access_token
                headers = {
                    "Authorization": "Bearer " + access_token, 
                }
                params = { # 设置请求参数，表示请求的是文件类型
                    "type": "file"
                }
                response = requests.get(url=url, headers=headers, params=params)  # 发送GET请求获取文件
                if response.status_code == 200: # 如果响应状态码是200，表示下载成功
                    with open(self.content, "wb") as f: # 打开文件并以二进制写模式写入
                        f.write(response.content)  # 将响应内容写入文件
                else:  # 如果响应状态码不是200
                    # 记录下载失败的日志
                    logger.info(f"[FeiShu] Failed to download file, key={file_key}, res={response.text}")
            self._prepare_fn = _download_file # 将文件下载函数赋值给_prepare_fn属性
        else: # 如果消息类型不是文本或文件
            raise NotImplementedError("Unsupported message type: Type:{} ".format(msg_type))  # 抛出不支持的消息类型错误
        # 无论是私聊还是群聊，from_user_id 都是指发送消息的用户，它的值是相同的。也就是说，如果用户 123 发送了一条消息，
        # 无论是在私聊中还是群聊中，from_user_id 都会是 123，表示消息的发送者是 123 这个用户。
        # 你在飞书客户端发送了一条消息，假设是私聊给聊天机器人应用。这时，消息的 发送者（from_user_id）是你，而目标应用
        # （to_user_id）是聊天机器人应用的 app_id。
        # 飞书将你的消息转发给聊天机器人应用。这个应用（机器人）会通过飞书提供的 API 或 Webhook 获取消息内容，并处理该消息。
        # 聊天机器人应用内部会根据收到的消息内容做出处理或生成回复。这个过程通常是应用逻辑的一部分，机器人根据预设规则、自然语言处
        # 理（NLP）、对话管理等技术来生成合适的回应。生成的回复将通过飞书的 API 发送回你。
        self.from_user_id = sender.get("sender_id").get("open_id")  # 设置消息发送者为用户id
        self.to_user_id = event.get("app_id") # 设置to_user_id 为聊天机器人应用的id
        if is_group:  # 如果是群聊
            self.other_user_id = msg.get("chat_id")  # 在群聊中的对方id为群聊id
            self.actual_user_id = self.from_user_id # 真实用户ID为发送者ID
            self.content = self.content.replace("@_user_1", "").strip() # 移除内容中的@用户信息并去除空格
            # self.actual_user_nickname = "" 的空字符串表示没有指定的**“真实用户昵称”**，尤其是在群聊中，它可能会涉及多
            # 个用户。因此，我们不需要或不能在群聊消息中为每个发送者显式设置昵称，特别是在处理这些消息时，昵称可能并不是主要的关键信息。
            self.actual_user_nickname = "" 
        else: # 如果是私聊
            self.other_user_id = self.from_user_id # 设置对方用户id为发送者
            self.actual_user_id = self.from_user_id # 设置真实用户ID为发送者ID
