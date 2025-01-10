# 导入所需的库和模块
import os, time, copy  # 导入标准库中的 os, time 和 copy 模块
from threading import Lock # 导入 Lock 用于多线程同步

# 导入其他模块中的类和组件
from .messagequeue import Queue  # 导入消息队列类 Queue
from .templates import (
    ContactList, AbstractUserDict, User, # 联系人相关类
    MassivePlatform, Chatroom, ChatroomMember) # 公众号、聊天室、聊天室成员相关类
# 定义装饰器，用于在修改联系人数据时加锁，确保线程安全
def contact_change(fn):
    def _contact_change(core, *args, **kwargs):
        with core.storageClass.updateLock: # 使用存储类中的 updateLock 来加锁
            return fn(core, *args, **kwargs) # 执行原函数
    return _contact_change

# 你的机器人是通过登录一个微信账号（机器人账号）与微信服务器交互。微信服务器返回的所有数据（例如好友列表、群成员信息）只
# 针对这个机器人账号，且存储在你定义的 Storage 类中。
# 其他用户的设备只运行微信客户端，不会加载你的程序，也不会存储这些数据。
# Storage 类管理的是你的机器人账号与其好友、群聊的交互数据。
# 它的存储和处理范围是本地的，不涉及其他用户设备的存储或代码运行。
# 群成员的数据是在他们的微信客户端中管理的，而不是与你的程序共享。
class Storage(object):
    def __init__(self, core):
        # 初始化存储对象的各项属性
        self.userName          = None # 用户名
        self.nickName          = None  # 昵称
        self.updateLock        = Lock() # 创建一个锁，用于多线程同步
        self.memberList        = ContactList() # 创建一个联系人列表
        self.mpList            = ContactList() # 创建一个公众号列表
        self.chatroomList      = ContactList() # 创建一个聊天室列表
        self.msgList           = Queue(-1) # 创建一个消息队列，大小无限制（-1）
        self.lastInputUserName = None # 最后输入的用户名
        # 为各个联系人列表设置默认的联系人类
        self.memberList.set_default_value(contactClass=User)
        self.memberList.core = core # 设置 core 属性
        # 为公众号列表设置公众号类
        self.mpList.set_default_value(contactClass=MassivePlatform)
        self.mpList.core = core # 设置 core 属性
        # 为聊天室列表设置聊天室类
        self.chatroomList.set_default_value(contactClass=Chatroom)
        self.chatroomList.core = core # 设置 core 属性
    # 序列化存储类对象（将其转换为字典）
    def dumps(self):
        return {
            'userName'          : self.userName,
            'nickName'          : self.nickName,
            'memberList'        : self.memberList,
            'mpList'            : self.mpList,
            'chatroomList'      : self.chatroomList,
            'lastInputUserName' : self.lastInputUserName, }
    
    # 反序列化存储类对象（将字典加载回对象）
    def loads(self, j):
        self.userName = j.get('userName', None) # 从字典中获取用户名
        self.nickName = j.get('nickName', None) # 从字典中获取昵称
        del self.memberList[:] # 清空现有的联系人列表
        for i in j.get('memberList', []): # 从字典加载联系人
            self.memberList.append(i)
        del self.mpList[:] # 清空公众号列表
        for i in j.get('mpList', []):  # 从字典加载公众号
            self.mpList.append(i)
        del self.chatroomList[:] # 清空聊天室列表
        for i in j.get('chatroomList', []): # 从字典加载聊天室
            self.chatroomList.append(i)
        # 遍历所有聊天室，重新绑定成员与聊天室信息
        for chatroom in self.chatroomList:
            if 'MemberList' in chatroom:  # 如果聊天室有成员列表
                for member in chatroom['MemberList']:
                    member.core = chatroom.core # 设置成员的core为聊天室的core
                    member.chatroom = chatroom # 设置成员所属的群为当前聊天室
            if 'Self' in chatroom: # 如果聊天室包含 "Self" 字段
                chatroom['Self'].core = chatroom.core  # 设置当前用户（Self）的 core 属性为聊天室的 core
                chatroom['Self'].chatroom = chatroom # 设置当前用户（Self）所属的群为当前聊天室
        # 当你让 机器人帮忙处理回复 时，lastInputUserName 记录的其实就是机器人和 最后一个互动的用户。这个信息会被用
        # 来决定是否在机器人后续的行为中作出相应的反应
        self.lastInputUserName = j.get('lastInputUserName', None) 
    # 查找好友，支持按不同的属性进行查询
    def search_friends(self, name=None, userName=None, remarkName=None, nickName=None,
            wechatAccount=None):
        with self.updateLock: # 使用锁来确保线程安全
            # 这段代码的目的是检查给定的多个变量是否 都 为 None，如果是的话，条件将为 True，代码会进入 if 语
            # 句的代码块。如果有任何一个变量不为 None，则 if 条件会被跳过。
            if (name or userName or remarkName or nickName or wechatAccount) is None:
                return copy.deepcopy(self.memberList[0]) 
            elif userName: # 如果提供了 userName，则返回匹配的联系人
                for m in self.memberList:
                    if m['UserName'] == userName:
                        return copy.deepcopy(m)
            else: # 如果没提供username,又不是都为None
                matchDict = {
                    'RemarkName' : remarkName, # 备注名称
                    'NickName'   : nickName,
                    'Alias'      : wechatAccount, } # 别名
                for k in ('RemarkName', 'NickName', 'Alias'): # 删除匹配字典中对应值为None的项
                    if matchDict[k] is None:
                        del matchDict[k]
                if name: # 如果提供了 name，则根据 name 查找
                    contact = [] # 返回匹配到的联系人
                    for m in self.memberList: # 遍历self.memberList 中的每一个联系人
                        # 列表推导式生成一个包含 3 个布尔值的列表，并由 any() 检查这个列表是否有任何一个 True，从
                        # 而确定是否该联系人匹配了 name。
                        if any([m.get(k) == name for k in ('RemarkName', 'NickName', 'Alias')]):
                            contact.append(m)
                else: # 没提供name的情况
                    contact = self.memberList[:] # 临时设置为全部成员
                if matchDict: # 如果匹配字典不是空字典 {}
                    friendList = [] # 用来存储所有符合条件的联系人
                    for m in contact: # 遍历 contact 列表中的每个联系人
                        # 检查是否所有的 matchDict 中的字段都匹配。
                        if all([m.get(k) == v for k, v in matchDict.items()]):
                            friendList.append(m)
                    return copy.deepcopy(friendList)
                else: # 否则返回所有
                    return copy.deepcopy(contact)
    # 查找聊天室，支持按名称或 userName 查找
    def search_chatrooms(self, name=None, userName=None):
        with self.updateLock:  # 使用锁来确保线程安全
            if userName is not None: # 如果userName不是None
                for m in self.chatroomList: # 遍历聊天室列表中的每个聊天室
                    if m['UserName'] == userName: # 如果聊天室名称和username一致
                        return copy.deepcopy(m) # 返回匹配到的聊天室
            elif name is not None: 
                matchList = []
                for m in self.chatroomList:
                    if name in m['NickName']: # 根据聊天室昵称进行匹配
                        matchList.append(copy.deepcopy(m))
                return matchList
    # 查找公众号，支持按名称或 userName 查找
    def search_mps(self, name=None, userName=None):
        with self.updateLock: # 使用锁来确保线程安全
            if userName is not None: # 如果username不是None
                for m in self.mpList: # 遍历公众号列表
                    if m['UserName'] == userName: # 如果匹配到一样的
                        return copy.deepcopy(m)
            elif name is not None:
                matchList = []
                for m in self.mpList:
                    if name in m['NickName']: # 根据公众号昵称进行匹配
                        matchList.append(copy.deepcopy(m))
                return matchList
