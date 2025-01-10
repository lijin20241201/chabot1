TEXT       = 'Text' # 定义一个常量，表示文本消息类型
MAP        = 'Map'  # 定义一个常量，表示地图消息类型
CARD       = 'Card'  # 定义一个常量，表示卡片消息类型
NOTE       = 'Note'  # 定义一个常量，表示笔记消息类型
SHARING    = 'Sharing'  # 定义一个常量，表示共享消息类型
PICTURE    = 'Picture'  # 定义一个常量，表示图片消息类型
RECORDING  = VOICE = 'Recording' # 定义两个常量，分别表示录音消息和语音消息类型，都指向'Recording'
ATTACHMENT = 'Attachment'  # 定义一个常量，表示附件消息类型
VIDEO      = 'Video' # 定义一个常量，表示视频消息类型
FRIENDS    = 'Friends'  # 定义一个常量，表示好友消息类型
SYSTEM     = 'System' # 定义一个常量，表示系统消息类型
# 此列表包含了所有可能的消息类型。它可能用于过滤或检查接收到的消息类型，确保它们符合预期。
INCOME_MSG = [TEXT, MAP, CARD, NOTE, SHARING, PICTURE,
    RECORDING, VOICE, ATTACHMENT, VIDEO, FRIENDS, SYSTEM]
