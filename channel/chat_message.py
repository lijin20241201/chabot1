# 本类表示聊天消息，用于对itchat和wechaty的消息进行统一的封装。
class ChatMessage(object):
    msg_id = None # 消息ID，唯一标识每条消息 (必填)
    create_time = None # 消息创建时间戳
    ctype = None # 消息类型，例如文本、图片、音频等 (必填)
    content = None # 消息内容，对于非文本消息（如声音/图片），这里存储的是文件路径 (必填)
    from_user_id = None # 发送者id (必填)
    from_user_nickname = None # 发送者昵称
    to_user_id = None # 接收者id (必填)
    to_user_nickname = None # 接收者昵称
    other_user_id = None # 对方的ID，用于区分群聊中的发送者或接收者；如果是群消息，这始终是群ID (必填)
    other_user_nickname = None # 对应other_user_id的昵称
    my_msg = False # 标记是不是其他人发给机器人的消息
    # display_name：表示机器人在当前聊天场景中的展示名称。
    # 群聊：机器人在群中的群昵称。例如，某些平台允许机器人在群聊中拥有单独的群昵称。
    # 私聊：通常为 None，因为私聊中一般不涉及昵称的展示。
    self_display_name = None 
    is_group = False # 标记是否为群聊消息 (群聊必填)
    is_at = False # 标记消息中是否包含@机器人
    actual_user_id = None # 实际发送者ID (群聊必填)，用于识别具体哪位成员发送了消息
    actual_user_nickname = None # 实际发送者的昵称
    at_list = None # 包含被@用户的列表
    _prepare_fn = None # 准备函数，用于准备消息的内容，比如下载附件等
    _prepared = False  # 标记是否已经调用过准备函数
    _rawmsg = None  # 原始消息对象，通常是从外部API获取的消息数据
    # 构造函数，初始化时传入原始消息对象
    def __init__(self, _rawmsg):
        self._rawmsg = _rawmsg
    # 调用准备函数来处理需要额外准备的消息内容，如下载图片等。只会在第一次调用时执行实际的准备工作。
    def prepare(self):
        if self._prepare_fn and not self._prepared:
            self._prepared = True
            self._prepare_fn()
    # 返回一个字符串表示形式的消息内容，便于调试和日志记录
    def __str__(self):
        return "ChatMessage: id={}, create_time={}, ctype={}, content={}, from_user_id={}, from_user_nickname={}, to_user_id={}, to_user_nickname={}, other_user_id={}, other_user_nickname={}, is_group={}, is_at={}, actual_user_id={}, actual_user_nickname={}, at_list={}".format(
            self.msg_id,
            self.create_time,
            self.ctype,
            self.content,
            self.from_user_id,
            self.from_user_nickname,
            self.to_user_id,
            self.to_user_nickname,
            self.other_user_id,
            self.other_user_nickname,
            self.is_group,
            self.is_at,
            self.actual_user_id,
            self.actual_user_nickname,
            self.at_list
        )
