import logging, copy, pickle  # 引入日志模块、深拷贝模块、序列化模块
from weakref import ref # 引入弱引用模块，用于避免循环引用问题

from ..returnvalues import ReturnValue
from ..utils import update_info_dict
# 初始化日志记录器，指定名称为 'itchat'
logger = logging.getLogger('itchat')
# 定义 AttributeDict 类，继承自 dict，允许通过属性访问键值
class AttributeDict(dict):
    # 重写 __getattr__ 方法，支持通过属性名访问字典中的键
    def __getattr__(self, value):
        keyName = value[0].upper() + value[1:] # 将属性名的首字母大写，符合键的命名约定
        try:
            return self[keyName]  # 尝试返回对应键的值
        except KeyError:  # 如果键不存在，则抛出 AttributeError
            raise AttributeError("'%s' object has no attribute '%s'" % (
                self.__class__.__name__.split('.')[-1], keyName))
    def get(self, v, d=None): # 重写 get 方法，支持获取键值，找不到时返回默认值
        try:
            return self[v]  # 返回键值
        except KeyError:
            return d # 如果键不存在，返回默认值

# 定义未初始化的 Itchat 类，用于在错误调用时发出警告
class UnInitializedItchat(object):
    def _raise_error(self, *args, **kwargs): # 私有方法，记录调用未初始化实例时的警告日志
        logger.warning('An itchat instance is called before initialized')
    # 重写 __getattr__ 方法，所有属性访问都触发 _raise_error
    def __getattr__(self, value):
        return self._raise_error

# 定义 ContactList 类，继承自 list，联系人列表
class ContactList(list):
    def __init__(self, *args, **kwargs):
        super(ContactList, self).__init__(*args, **kwargs) # 调用父类初始化
        self.__setstate__(None)  # 设置默认状态
    # 如果有_core属性,就返回_core,如果_core()返回的不是False,None等,就返回_core()
    # 否则返回一个默认值fakeItchat,如果没有_core属性,就返回lambda: fakeItchat,这是个函数
    # 加个括号就返回函数调用的结果fakeItchat
    @property
    def core(self):  
        return getattr(self, '_core', lambda: fakeItchat)() or fakeItchat
    @core.setter
    def core(self, value):
        self._core = ref(value) # 使用弱引用避免循环引用
    # 设置默认值函数，用于初始化联系人和指定联系人类
    def set_default_value(self, initFunction=None, contactClass=None):
        if hasattr(initFunction, '__call__'):  # 如果提供的初始化函数可调用
            self.contactInitFn = initFunction
        if hasattr(contactClass, '__call__'):  # 如果提供的联系人类可调用
            self.contactClass = contactClass
    # 重写 append 方法，在添加联系人时进行初始化和格式化
    def append(self, value):
        contact = self.contactClass(value) # 使用指定的联系人类创建联系人对象
        contact.core = self.core  # 关联核心对象
        if self.contactInitFn is not None: # 如果定义了初始化函数
            contact = self.contactInitFn(self, contact) or contact # 调用初始化函数
        super(ContactList, self).append(contact)  # 将联系人添加到列表
    # 重写深拷贝方法，确保拷贝时保留初始化函数和联系人类
    def __deepcopy__(self, memo):
        # 因为本类继承自列表,所以用列表推导式,elf.__class__ 并不是一个构造方法，而是当前类（ContactList）
        # 的引用，用于动态地创建与当前类相同类型的新实例。神拷贝当前类中的联系人对象,并且创建一个新的对象
        r = self.__class__([copy.deepcopy(v) for v in self]) 
        r.contactInitFn = self.contactInitFn  # 设置初始化函数
        r.contactClass = self.contactClass # 设置联系人类
        r.core = self.core # 设置核心对象
        return r
    def __getstate__(self): # 获取序列化保存的状态
        return 1 # 返回固定值作为状态
    def __setstate__(self, state): # 定义反序列化时的默认状态
        self.contactInitFn = None  # 初始化函数默认为 None
        self.contactClass = User # 联系人类默认为 User
    def __str__(self): # 重写 __str__ 方法，返回列表内容的字符串表示
        return '[%s]' % ', '.join([repr(v) for v in self])  # 列出每个联系人的字符串表示
    # 重写 __repr__ 方法，返回正式的对象表示
    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__.split('.')[-1],
            self.__str__())  # 显示类名和内容

# 继承自 AttributeDict，扩展用户字典功能
class AbstractUserDict(AttributeDict):
    def __init__(self, *args, **kwargs):
        super(AbstractUserDict, self).__init__(*args, **kwargs)  # 调用父类初始化方法
    @property
    def core(self): # 找_core属性,找不到默认返回lambda: fakeItchat
        return getattr(self, '_core', lambda: fakeItchat)() or fakeItchat  # 返回核心对象或默认值
    @core.setter
    def core(self, value):  # 设置 core 属性，存储为弱引用，避免循环引用
        self._core = ref(value)
    # 更新操作
    def update(self):
        return ReturnValue({'BaseResponse': {
            'Ret': -1006, # 错误码
            'ErrMsg': '%s can not be updated' % \
                self.__class__.__name__, }, }) # 错误消息
    # 设置别名操作
    def set_alias(self, alias): 
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s can not set alias' % \
                self.__class__.__name__, }, })
    def set_pinned(self, isPinned=True):  # 置顶操作
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s can not be pinned' % \
                self.__class__.__name__, }, })
    def verify(self): # 验证操作
        return ReturnValue({'BaseResponse': {
            'Ret': -1006, # 错误码
            'ErrMsg': '%s do not need verify' % \
                self.__class__.__name__, }, })  # 错误消息
    def get_head_image(self, imageDir=None): # 获取头像
        return self.core.get_head_img(self.userName, picDir=imageDir) # 调用核心方法获取头像
    def delete_member(self, userName): # 删除成员操作
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s can not delete member' % \
                self.__class__.__name__, }, })
    def add_member(self, userName): # 添加成员操作
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s can not add member' % \
                self.__class__.__name__, }, })
    def send_raw_msg(self, msgType, content): # 发送原始消息
        return self.core.send_raw_msg(msgType, content, self.userName) # 调用核心方法发送消息
    def send_msg(self, msg='Test Message'):  # 发送普通文本消息
        return self.core.send_msg(msg, self.userName)  # 调用核心方法发送消息
    def send_file(self, fileDir, mediaId=None): # 发送文件
        return self.core.send_file(fileDir, self.userName, mediaId)
    def send_image(self, fileDir, mediaId=None): # 发送图片
        return self.core.send_image(fileDir, self.userName, mediaId)
    def send_video(self, fileDir=None, mediaId=None):  # 发送视频
        return self.core.send_video(fileDir, self.userName, mediaId)
    def send(self, msg, mediaId=None): # 发送任意消息类型
        return self.core.send(msg, self.userName, mediaId)
    def search_member(self, name=None, userName=None, remarkName=None, nickName=None,
            wechatAccount=None): # 搜索成员操作
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s do not have members' % \
                self.__class__.__name__, }, })
    def __deepcopy__(self, memo): # 深拷贝实现
        r = self.__class__() # 创建当前类的新实例
        for k, v in self.items(): # 深拷贝字典中的每个键值对
            r[copy.deepcopy(k)] = copy.deepcopy(v)
        r.core = self.core # 设置核心对象
        return r
    def __str__(self): # 自定义字符串表示
        return '{%s}' % ', '.join(
            ['%s: %s' % (repr(k),repr(v)) for k,v in self.items()]) # 显示字典内容
    def __repr__(self): # 自定义对象的正式表示
        return '<%s: %s>' % (self.__class__.__name__.split('.')[-1],
            self.__str__()) # 显示类名和内容
    def __getstate__(self): # 定义获取对象的序列化状态
        return 1  # 返回固定值作为状态
    def __setstate__(self, state): # 定义反序列化行为
        pass # 不做任何操作
        
class User(AbstractUserDict):
    def __init__(self, *args, **kwargs):
        super(User, self).__init__(*args, **kwargs) # 调用父类的初始化方法
        self.__setstate__(None) # 初始化对象的状态
    def update(self):
        r = self.core.update_friend(self.userName) # 更新好友信息
        if r:  # 更新当前对象的信息字典
            update_info_dict(self, r)
        return r # 返回更新结果
    def set_alias(self, alias):
        return self.core.set_alias(self.userName, alias) # 设置用户别名
    def set_pinned(self, isPinned=True):
        return self.core.set_pinned(self.userName, isPinned) # 置顶用户
    def verify(self): # 验证好友申请
        return self.core.add_friend(**self.verifyDict)
    def __deepcopy__(self, memo):
        r = super(User, self).__deepcopy__(memo) # 深拷贝对象
        r.verifyDict = copy.deepcopy(self.verifyDict)  # 深拷贝验证字典
        return r # 返回深拷贝的对象
    def __setstate__(self, state):
        super(User, self).__setstate__(state) # 设置对象状态
        # verifyDict 用来存储与验证好友请求相关的各种信息，通常会包括请求者的信息、验证消息和其他验证参数。
        self.verifyDict = {}
        # 对于用户对象（User），'MemberList' 表示该用户的联系人或好友列表。
        self['MemberList'] = fakeContactList 

class MassivePlatform(AbstractUserDict): # 公众号平台类
    def __init__(self, *args, **kwargs):
        super(MassivePlatform, self).__init__(*args, **kwargs) # 调用父类初始化方法
        self.__setstate__(None)  # 初始化对象状态
    def __setstate__(self, state):
        super(MassivePlatform, self).__setstate__(state) # 设置对象状态
        self['MemberList'] = fakeContactList # 初始化联系人列表

class Chatroom(AbstractUserDict):
    def __init__(self, *args, **kwargs):
        super(Chatroom, self).__init__(*args, **kwargs)
        memberList = ContactList() # 创建成员列表对象
        userName = self.get('UserName', '') # 获取聊天室用户名
        refSelf = ref(self)  # 弱引用当前对象
        def init_fn(parentList, d):
            d.chatroom = refSelf() or \
                parentList.core.search_chatrooms(userName=userName) # 初始化成员关联的聊天室
        memberList.set_default_value(init_fn, ChatroomMember)  # 设置成员列表默认值和类型
        if 'MemberList' in self: # 如果成员列表已存在
            for member in self.memberList:
                memberList.append(member)  # 将现有成员添加到成员列表
        self['MemberList'] = memberList # 更新聊天室的成员列表
    @property
    def core(self): # 获取核心对象，默认为fakeItchat
        return getattr(self, '_core', lambda: fakeItchat)() or fakeItchat
    @core.setter
    def core(self, value):
        self._core = ref(value) # 设置核心对象的弱引用
        self.memberList.core = value # 更新成员列表的核心对象
        for member in self.memberList: # 更新每个成员的核心对象
            member.core = value
    def update(self, detailedMember=False):  # 更新聊天室信息
        r = self.core.update_chatroom(self.userName, detailedMember)
        if r:
            update_info_dict(self, r)  # 更新聊天室对象的信息字典
            self['MemberList'] = r['MemberList'] # 更新成员列表
        return r  # 返回更新结果
    def set_alias(self, alias):  # 设置聊天室别名
        return self.core.set_chatroom_name(self.userName, alias)
    def set_pinned(self, isPinned=True): # 置顶聊天室
        return self.core.set_pinned(self.userName, isPinned)
    def delete_member(self, userName): # 从聊天室删除成员
        return self.core.delete_member_from_chatroom(self.userName, userName)
    def add_member(self, userName): # 添加成员到聊天室
        return self.core.add_member_into_chatroom(self.userName, userName)
    def search_member(self, name=None, userName=None, remarkName=None, nickName=None,
            wechatAccount=None):
        with self.core.storageClass.updateLock:  # 使用更新锁保护操作
            if (name or userName or remarkName or nickName or wechatAccount) is None:
                return None # 如果没有指定条件，返回None
            elif userName: # 如果有usename
                for m in self.memberList: # 返回匹配到的成员
                    if m.userName == userName:
                        return copy.deepcopy(m)
            else: # 如果没有username
                matchDict = { # 定义一个匹配字典
                    'RemarkName' : remarkName, # 备注名称
                    'NickName'   : nickName,
                    'Alias'      : wechatAccount, }
                for k in ('RemarkName', 'NickName', 'Alias'): # 如果对应的值是None,删除对应项
                    if matchDict[k] is None: 
                        del matchDict[k]
                if name: # 如果有name
                    contact = [] # 保存搜索到的匹配成员
                    for m in self.memberList: # 如果匹配到任何一个,就加入列表
                        if any([m.get(k) == name for k in ('RemarkName', 'NickName', 'Alias')]):
                            contact.append(m)
                else: # 如果没传入name
                    contact = self.memberList[:] # 默认设置全部成员
                if matchDict: # 如果匹配字典不是None
                    friendList = []
                    for m in contact: # 必须所有匹配项都一致,才会加入好友列表
                        if all([m.get(k) == v for k, v in matchDict.items()]):
                            friendList.append(m)
                    return copy.deepcopy(friendList)
                else: # 如果匹配字典是None
                    return copy.deepcopy(contact)
    def __setstate__(self, state):
        super(Chatroom, self).__setstate__(state) # 设置对象状态
        if not 'MemberList' in self:  # 如果MemberList在实例中不存在,设置个默认的假的成员列表
            self['MemberList'] = fakeContactList
# 聊天室成员类
class ChatroomMember(AbstractUserDict):
    def __init__(self, *args, **kwargs):
        super(AbstractUserDict, self).__init__(*args, **kwargs) # 调用父类 AbstractUserDict 的初始化方法
        self.__setstate__(None) # 初始化当前对象的状态
    @property
    def chatroom(self):
        # 如果存在_chatroom,就用这个类实例,否则调用lambda函数,返回默认的fakeChatroom
        r = getattr(self, '_chatroom', lambda: fakeChatroom)()
        if r is None: # 如果r是None
            userName = getattr(self, '_chatroomUserName', '') # 获取聊天室名称属性
            r = self.core.search_chatrooms(userName=userName) # 搜索指定名称的聊天室
            if isinstance(r, dict): # 如果是字典类型
                self.chatroom = r # 指定当前聊天室成员所属的聊天室
        return r or fakeChatroom # 返回r,如果r是None,False,则返回默认的假数据
    @chatroom.setter
    def chatroom(self, value): # 设置成员所属的聊天室
        if isinstance(value, dict) and 'UserName' in value: 
            self._chatroom = ref(value) # 设置实例属性聊天室
            self._chatroomUserName = value['UserName'] # 设置聊天室名称
    def get_head_image(self, imageDir=None): # 获取 chatroom 成员的头像
        return self.core.get_head_img(self.userName, self.chatroom.userName, picDir=imageDir)
    def delete_member(self, userName): # 从 chatroom 中删除成员
        return self.core.delete_member_from_chatroom(self.chatroom.userName, self.userName)
    def send_raw_msg(self, msgType, content): # 发送原消息方法
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s can not send message directly' % \
                self.__class__.__name__, }, })
    def send_msg(self, msg='Test Message'): # 发送消息方法
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s can not send message directly' % \
                self.__class__.__name__, }, })
    def send_file(self, fileDir, mediaId=None):  # 发送文件
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s can not send message directly' % \
                self.__class__.__name__, }, })
    def send_image(self, fileDir, mediaId=None): # 发送图片
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s can not send message directly' % \
                self.__class__.__name__, }, })
    def send_video(self, fileDir=None, mediaId=None): # 发送视频
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s can not send message directly' % \
                self.__class__.__name__, }, })
    def send(self, msg, mediaId=None): # 发送任意消息
        return ReturnValue({'BaseResponse': {
            'Ret': -1006,
            'ErrMsg': '%s can not send message directly' % \
                self.__class__.__name__, }, })
    def __setstate__(self, state): # 设置对象状态，同时为聊天室成员设置假联系人列表
        super(ChatroomMember, self).__setstate__(state)
        self['MemberList'] = fakeContactList

def wrap_user_dict(d): # 根据用户字典的内容返回相应的用户类型实例
    userName = d.get('UserName')   # 获取 UserName 字段
    if '@@' in userName: # 如果 UserName 中有 '@@'，则是群聊
        r = Chatroom(d)
    elif d.get('VerifyFlag', 8) & 8 == 0: # 如果 VerifyFlag 条件满足，则是普通用户
        r = User(d)
    else:  # 否则是公众号
        r = MassivePlatform(d)
    return r
# 假的全局变量，用于模拟未初始化的接口和联系人
fakeItchat = UnInitializedItchat() # 未初始化的 itchat 接口
fakeContactList = ContactList() # 假联系人列表
fakeChatroom = Chatroom() # 假群聊实例
