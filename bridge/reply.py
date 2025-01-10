# encoding:utf-8
from enum import Enum

class ReplyType(Enum):
    TEXT = 1  # 文本
    VOICE = 2  # 音频文件
    IMAGE = 3  # 图片文件
    IMAGE_URL = 4  # 图片URL
    VIDEO_URL = 5  # 视频URL
    FILE = 6  # 文件
    CARD = 7  # 微信名片，仅支持ntchat
    INVITE_ROOM = 8  # 邀请好友进群
    INFO = 9
    ERROR = 10
    TEXT_ = 11  # 强制文本
    VIDEO = 12
    MINIAPP = 13  # 小程序
    def __str__(self):
        return self.name
# Reply 类封装了机器人的回复内容。它包含两个主要属性
# type: 使用 ReplyType 枚举类型，表示回复的类型（例如文本、图片、音频等）。
# content: 回复的具体内容，这个内容根据类型可能是字符串、文件、图片 URL 等。
class Reply:
    def __init__(self, type: ReplyType = None, content=None):
        self.type = type
        self.content = content

    def __str__(self):
        return "Reply(type={}, content={})".format(self.type, self.content)
