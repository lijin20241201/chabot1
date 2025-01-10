import time
import re
import io
import json
import copy
import logging

from .. import config, utils
from ..returnvalues import ReturnValue
from ..storage import contact_change
from ..utils import update_info_dict

# 设置日志记录器，日志记录器的名称为 'itchat'
# 如果你在不同的文件或模块中调用 logging.getLogger('itchat')，它们会得到同一个日志对象，只要它们使用相同的名称 'itchat'。
logger = logging.getLogger('itchat')

# 将不同的联系人相关功能加载到核心对象 `core` 中,将联系人的相关功能绑定到 core 对象。
def load_contact(core):
    core.update_chatroom = update_chatroom # 更新聊天室
    core.update_friend = update_friend # 更新好友
    core.get_contact = get_contact # 获取联系人
    core.get_friends = get_friends # 获取好友列表
    core.get_chatrooms = get_chatrooms  # 获取聊天室列表
    core.get_mps = get_mps # 获取公众号列表
    core.set_alias = set_alias  # 设置好友备注
    core.set_pinned = set_pinned # 设置置顶状态
    core.accept_friend = accept_friend # 接受好友请求
    core.get_head_img = get_head_img # 获取头像
    core.create_chatroom = create_chatroom # 创建聊天室
    core.set_chatroom_name = set_chatroom_name # 设置聊天室名称
    core.delete_member_from_chatroom = delete_member_from_chatroom  # 从聊天室删除成员
    core.add_member_into_chatroom = add_member_into_chatroom # 将成员添加到聊天室

# 更新聊天室的信息，支持批量获取聊天成员详细信息。
def update_chatroom(self, userName, detailedMember=False):
    if not isinstance(userName, list): # 如果传入的 userName 不是列表形式，将其转换为列表
        userName = [userName]
    # URL 是用于向微信服务器请求 批量获取联系人信息（包括聊天室信息）接口的地址。
    url = '%s/webwxbatchgetcontact?type=ex&r=%s' % ( # 构建请求 URL，包含时间戳用于避免缓存
        self.loginInfo['url'], int(time.time()))
    headers = { # 设置请求头，使用自定义的用户代理
        'ContentType': 'application/json; charset=UTF-8',
        'User-Agent': config.USER_AGENT}
    data = { # 构建请求数据，包括登录信息和要查询的聊天室
        'BaseRequest': self.loginInfo['BaseRequest'],
        'Count': len(userName),
        'List': [{
            'UserName': u,
            'ChatRoomId': '', } for u in userName], }
    # 发送请求并解析返回的聊天室列表,.decode('utf8', 'replace'): 这将字节串解码为 UTF-8 编码的字符串。
    # 'replace': 这是处理解码错误的策略。当某些字节无法按 UTF-8 解码时，使用替代字符（通常是 �）来替换那些无法解码的字符。
    # 虽然用的是ContactList,其实返回的是名称列表内的聊天室对象
    chatroomList = json.loads(self.s.post(url, data=json.dumps(data), headers=headers
                                          ).content.decode('utf8', 'replace')).get('ContactList')
    if not chatroomList: # 如果没有找到任何聊天室，返回错误信息
        return ReturnValue({'BaseResponse': {
            'ErrMsg': 'No chatroom found',
            'Ret': -1001, }})
    if detailedMember: # 如果需要获取详细的成员信息
        # 定义一个函数，用于获取聊天室成员的详细信息
        def get_detailed_member_info(encryChatroomId, memberList):
            url = '%s/webwxbatchgetcontact?type=ex&r=%s' % ( # 构建请求 URL，获取详细成员信息
                self.loginInfo['url'], int(time.time()))
            headers = { # 设置请求头
                'ContentType': 'application/json; charset=UTF-8',
                'User-Agent': config.USER_AGENT, }
            data = { # 构建请求数据，包含要查询的成员信息
                'BaseRequest': self.loginInfo['BaseRequest'],
                'Count': len(memberList),
                'List': [{
                    'UserName': member['UserName'],
                    'EncryChatRoomId': encryChatroomId}
                    for member in memberList], }
            # 发送请求并返回解析后的成员列表
            return json.loads(self.s.post(url, data=json.dumps(data), headers=headers
                                          ).content.decode('utf8', 'replace'))['ContactList']
        MAX_GET_NUMBER = 50 # 设置每次获取成员的最大数量，避免一次请求过多导致失败
        for chatroom in chatroomList: # 遍历每个聊天室，获取成员详细信息
            totalMemberList = [] # 存储所有成员的详细信息
            for i in range(int(len(chatroom['MemberList']) / MAX_GET_NUMBER + 1)):
                # 按照 MAX_GET_NUMBER 分批获取成员信息
                memberList = chatroom['MemberList'][i *
                                                    MAX_GET_NUMBER: (i+1)*MAX_GET_NUMBER]
                totalMemberList += get_detailed_member_info(
                    chatroom['EncryChatRoomId'], memberList)
            chatroom['MemberList'] = totalMemberList # 更新聊天室的成员列表
    # 更新本地存储中的聊天室信息
    update_local_chatrooms(self, chatroomList)
    # 使用存储类查询并返回每个聊天室的信息
    r = [self.storageClass.search_chatrooms(userName=c['UserName'])
         for c in chatroomList]
    # 如果只有一个聊天室，返回该聊天室，否则返回聊天室列表
    return r if 1 < len(r) else r[0]
# 更新好友列表
def update_friend(self, userName):
    if not isinstance(userName, list): # 如果传入的userName不是列表，则将其转化为列表
        userName = [userName]
    url = '%s/webwxbatchgetcontact?type=ex&r=%s' % ( # 设置请求的url，加入当前时间戳
        self.loginInfo['url'], int(time.time()))
    headers = { # 设置请求头信息
        'ContentType': 'application/json; charset=UTF-8',
        'User-Agent': config.USER_AGENT}
    data = { # 设置请求体，包含了BaseRequest和userName列表
        'BaseRequest': self.loginInfo['BaseRequest'],
        'Count': len(userName),
        'List': [{
            'UserName': u,
            'EncryChatRoomId': '', } for u in userName], }
    # 发起请求并解析返回的JSON数据，获取联系人的列表
    friendList = json.loads(self.s.post(url, data=json.dumps(data), headers=headers
                                        ).content.decode('utf8', 'replace')).get('ContactList')

    update_local_friends(self, friendList) # 更新本地的好友列表
    r = [self.storageClass.search_friends(userName=f['UserName']) # 根据返回的好友信息，查询本地存储的好友信息，并返回
         for f in friendList]
    return r if len(r) != 1 else r[0]  # 如果有多个匹配的好友则返回列表，否则返回单个好友

# 更新本地存储的聊天室信息,返回更新后的聊天室列表
@contact_change # 表示加锁,使用线程安全的方式
def update_local_chatrooms(core, l):
    for chatroom in l: # 遍历传入的聊天室更新列表 l，每次循环处理一个聊天室数据。
        # 格式化聊天室的 NickName 字段，处理其中的表情符号或特殊字符，确保显示一致性。
        utils.emoji_formatter(chatroom, 'NickName') 
        # 遍历聊天室的每个成员，检查成员是否有 NickName、DisplayName 或 RemarkName 字段，并且如果存在这些字段
        # ，就使用 emoji_formatter 来格式化这些字段中的表情符号或特殊字符。
        for member in chatroom['MemberList']:
            if 'NickName' in member:
                utils.emoji_formatter(member, 'NickName')
            if 'DisplayName' in member:
                utils.emoji_formatter(member, 'DisplayName')
            if 'RemarkName' in member:
                utils.emoji_formatter(member, 'RemarkName')
        # 查找旧聊天室信息,通过 UserName 匹配，判断当前聊天室是否已存在于本地存储。
        oldChatroom = utils.search_dict_list(
            core.chatroomList, 'UserName', chatroom['UserName'])
        # 如果找到了本地的旧聊天室数据 oldChatroom，则调用 update_info_dict 函数来更新该聊天室的字段信息。
        if oldChatroom: 
            update_info_dict(oldChatroom, chatroom) # 更新旧的聊天室的信息
            # 获取当前聊天室的成员列表。如果没有成员列表，默认返回空列表。
            memberList = chatroom.get('MemberList', [])
            oldMemberList = oldChatroom['MemberList'] # 获取本地旧聊天室的成员列表。
            if memberList: # 如果存在 memberList（当前聊天室的成员列表），则遍历每个成员
                for member in memberList:
                    oldMember = utils.search_dict_list( # 查找该成员是否在本地旧聊天室的成员列表中（通过 UserName 来匹配）。
                        oldMemberList, 'UserName', member['UserName'])
                    if oldMember: # 如果找到了该成员（oldMember），则更新该成员的信息。
                        update_info_dict(oldMember, member)
                    # 如果没有找到该成员，说明是一个新成员，直接将该成员添加到本地的 oldMemberList 成员列表中。
                    else:
                        oldMemberList.append(member)
        # 如果没有找到本地旧聊天室（意味着这是一个新聊天室），则将当前 chatroom 添加到本地聊天室列表 core.chatroomList 中。
        # 然后再次搜索这个新加入的聊天室。
        else:
            core.chatroomList.append(chatroom)
            oldChatroom = utils.search_dict_list(
                core.chatroomList, 'UserName', chatroom['UserName'])
        # 删除不再属于聊天室的成员
        # 如果当前聊天室的 MemberList 成员数量与本地聊天室的成员数量不同，并且 MemberList 不为空
        if len(chatroom['MemberList']) != len(oldChatroom['MemberList']) and \
                chatroom['MemberList']:
            # 创建一个包含当前成员 UserName 的列表 existsUserNames。
            existsUserNames = [member['UserName']
                               for member in chatroom['MemberList']]
            delList = []
            # 遍历旧聊天室的 MemberList，如果成员的 UserName 不在 existsUserNames 中，就记录下该成员的索引。
            # 这个说明这些成员已经不再更新后的聊天室里,说明他们已经离开群
            for i, member in enumerate(oldChatroom['MemberList']):
                if member['UserName'] not in existsUserNames:
                    delList.append(i)
            # 将这些索引存储在 delList 中，并按从后到前的顺序进行删除，以避免因删除操作导致索引错乱。
            delList.sort(reverse=True)
            for i in delList:
                del oldChatroom['MemberList'][i]
        # 如果 本地的聊天室存在群创建者 和 成员列表
        if oldChatroom.get('ChatRoomOwner') and oldChatroom.get('MemberList'):
            # 根据username查找聊天室的群创建者
            owner = utils.search_dict_list(oldChatroom['MemberList'],
                                           'UserName', oldChatroom['ChatRoomOwner'])

            # 获取群创建者的 Uin（微信唯一标识符）。
            oldChatroom['OwnerUin'] = (owner or {}).get('Uin', 0)
        # 如果'OwnerUin' in oldChatroom: 确保旧聊天室数据中包含 OwnerUin 字段。oldChatroom['OwnerUin'] != 0: 
        # 确保 OwnerUin 值不为 0（0 通常表示无效的所有者标识）。
        if 'OwnerUin' in oldChatroom and oldChatroom['OwnerUin'] != 0:
            # 通过对比当前聊天室的所有者 OwnerUin 和当前登录用户的唯一标识符 wxuin。
            # 如果两者相等，说明当前登录用户是群所有者（即群的创建者），此时将 IsAdmin 设置为 True。
            # 如果不相等，则说明当前用户不是群所有者，IsAdmin 设置为 False。
            oldChatroom['IsAdmin'] = \
                oldChatroom['OwnerUin'] == int(core.loginInfo['wxuin'])
        # 如果没有 OwnerUin 字段或者其值为 0，说明无法确定聊天室的所有者。oldChatroom['IsAdmin'] = None: 
        # 设置 IsAdmin 为 None，表示无法判断当前用户是否是管理员。
        else:  # 如果条件不满足
            oldChatroom['IsAdmin'] = None
        # 通过 core.storageClass.userName（即机器人自己的用户名）在聊天室的成员列表中查找对应的成员数据。
        # 机器人自身信息更新
        newSelf = utils.search_dict_list(oldChatroom['MemberList'],
                                         'UserName', core.storageClass.userName)
        oldChatroom['Self'] = newSelf or copy.deepcopy(core.loginInfo['User'])
    # 这是一个系统内部的返回消息，目的是告知调用者（通常是机器人自身或其他模块）聊天室数据已更新。
    # FromUserName 和 ToUserName 设置为机器人自身，表明这不是一条需要发送给用户的消息，而是供系统内部消费的。
    return {
        'Type': 'System', # 表明消息类型是系统内部的状态更新。
        'Text': [chatroom['UserName'] for chatroom in l], # 返回更新的聊天室 UserName 列表。
        'SystemInfo': 'chatrooms', # 附加信息标识为“chatrooms”。
        'FromUserName': core.storageClass.userName, 
        'ToUserName': core.storageClass.userName, }

# 更新本地的好友列表
@contact_change
def update_local_friends(core, l):
    # 合并core中的成员列表和公众号列表，存储在fullList中
    fullList = core.memberList + core.mpList
    for friend in l: # 遍历传入的好友/公众号数据l
        # 如果好友数据中包含NickName字段，使用emoji_formatter进行格式化处理
        if 'NickName' in friend:
            utils.emoji_formatter(friend, 'NickName')
        # 如果好友数据中包含DisplayName字段，使用emoji_formatter进行格式化处理
        if 'DisplayName' in friend:
            utils.emoji_formatter(friend, 'DisplayName')
        # 如果好友数据中包含RemarkName字段，使用emoji_formatter进行格式化处理
        if 'RemarkName' in friend:
            utils.emoji_formatter(friend, 'RemarkName')
        # 在本地的好友列表和公众号列表中查找与当前名称相同的
        oldInfoDict = utils.search_dict_list(
            fullList, 'UserName', friend['UserName'])
        # 如果没有找到相应的记录，说明这是一个新朋友或公众号
        if oldInfoDict is None:
            oldInfoDict = copy.deepcopy(friend) # 创建一个好友或公众号的副本
            # 判断好友的VerifyFlag字段，如果VerifyFlag & 8 == 0，则是普通成员
            if oldInfoDict['VerifyFlag'] & 8 == 0:
                core.memberList.append(oldInfoDict) # 新成员,添加
            else: # 否则是公众号，将其添加到mpList中
                core.mpList.append(oldInfoDict)
        else: # 如果已经存在
            update_info_dict(oldInfoDict, friend) # 更新

@contact_change
def update_local_uin(core, msg):
    # 使用正则表达式从消息的内容中提取所有的 UIN（用户唯一标识符）
    uins = re.search('<username>([^<]*?)<', msg['Content'])
    usernameChangedList = []  # 初始化一个列表，用来存储已经更改 UIN 的用户名
    r = {
        'Type': 'System',  # 返回的类型为系统类型
        'Text': usernameChangedList, # 返回修改的用户名列表
        'SystemInfo': 'uins', } # 系统信息为 'uins'
    if uins: # 如果正则表达式成功提取到了 UIN
        uins = uins.group(1).split(',') # 将 UIN 字符串按照逗号分割，形成 UIN 列表
        usernames = msg['StatusNotifyUserName'].split(',') # 将通知的用户名字符串按照逗号分割，形成用户名列表
        # 如果 UIN 列表和用户名列表的长度一致且大于 0，则进行下一步处理
        if 0 < len(uins) == len(usernames):
            # 将 UIN 和用户名按顺序配对，进行逐一处理
            for uin, username in zip(uins, usernames):
                if not '@' in username: # 如果用户名不包含 '@'，则跳过
                    continue
                # 获取成员列表、聊天室列表和公众号列表，形成一个完整的联系人列表
                fullContact = core.memberList + core.chatroomList + core.mpList
                # 在联系人列表中查找是否存在该用户名
                userDicts = utils.search_dict_list(fullContact,
                                                   'UserName', username)
                if userDicts:  # 如果找到了该用户数据
                    if userDicts.get('Uin', 0) == 0: # 如果该用户的 Uin 字段为 0，说明该用户没有 UIN 信息
                        userDicts['Uin'] = uin # 更新 UIN 信息
                        usernameChangedList.append(username) # 将该用户名添加到更改列表中
                        logger.debug('Uin fetched: %s, %s' % (username, uin)) # 打印调试日志
                    else: # 如果该用户已有 UIN 且与当前的 UIN 不一致，打印调试日志
                        if userDicts['Uin'] != uin:
                            logger.debug('Uin changed: %s, %s' % (
                                userDicts['Uin'], uin))
                else: # 如果找不到该用户数据，且用户名包含 '@@'（表示聊天室）
                    if '@@' in username:
                        core.storageClass.updateLock.release() # 释放锁
                        update_chatroom(core, username) # 更新聊天室信息
                        core.storageClass.updateLock.acquire() # 重新获取锁
                        newChatroomDict = utils.search_dict_list( # 查找更新后的聊天室数据
                            core.chatroomList, 'UserName', username)
                        if newChatroomDict is None: # 如果聊天室数据为空，创建新的聊天室数据
                            newChatroomDict = utils.struct_friend_info({
                                'UserName': username,
                                'Uin': uin,
                                'Self': copy.deepcopy(core.loginInfo['User'])})
                            core.chatroomList.append(newChatroomDict)   # 将聊天室数据添加到聊天室列表中
                        else: # 更新聊天室的 UIN 信息
                            newChatroomDict['Uin'] = uin
                    elif '@' in username: # 如果是普通好友（用户名包含 '@'）
                        core.storageClass.updateLock.release() # 释放锁
                        update_friend(core, username) # 更新好友信息
                        core.storageClass.updateLock.acquire()  # 重新获取锁
                        newFriendDict = utils.search_dict_list(  # 查找更新后的好友数据
                            core.memberList, 'UserName', username)
                        if newFriendDict is None: # 如果好友数据为空，创建新的好友数据
                            newFriendDict = utils.struct_friend_info({
                                'UserName': username,
                                'Uin': uin, })
                            core.memberList.append(newFriendDict) # 将好友数据添加到好友列表中
                        else:  # 更新好友的 UIN 信息
                            newFriendDict['Uin'] = uin
                    usernameChangedList.append(username)  # 将用户名添加到更改列表中
                    logger.debug('Uin fetched: %s, %s' % (username, uin))  # 打印调试日志
        else: # 如果 UIN 列表和用户名列表的长度不一致，打印调试日志
            logger.debug('Wrong length of uins & usernames: %s, %s' % (
                len(uins), len(usernames)))
    else: # 如果没有提取到 UIN，打印调试日志
        logger.debug('No uins in 51 message')
        logger.debug(msg['Content'])
    return r # 返回包含已更改用户名列表的字典

# 获取聊天室列表
def get_contact(self, update=False):
    if not update: # 如果不需要更新，则直接返回深拷贝的聊天群列表
        return utils.contact_deep_copy(self, self.chatroomList)
    def _get_contact(seq=0): # 定义内部函数，用于获取联系人信息
        # 构造请求的URL，带有时间戳、序列号和密钥
        url = '%s/webwxgetcontact?r=%s&seq=%s&skey=%s' % (self.loginInfo['url'],
                                                          int(time.time()), seq, self.loginInfo['skey'])
        headers = { # 请求头，设置ContentType和User-Agent
            'ContentType': 'application/json; charset=UTF-8',
            'User-Agent': config.USER_AGENT, }
        try:
            r = self.s.get(url, headers=headers) # 发送请求获取联系人数据
        except: # 如果请求失败，记录日志并尝试更新聊天群成员
            logger.info(
                'Failed to fetch contact, that may because of the amount of your chatrooms')
            # 有可能是聊天室过多,这时候一个个的更新
            for chatroom in self.get_chatrooms():
                self.update_chatroom(chatroom['UserName'], detailedMember=True)
            return 0, []  # 返回默认值
        j = json.loads(r.content.decode('utf-8', 'replace')) # 解析返回的JSON数据
        return j.get('Seq', 0), j.get('MemberList') # 返回序列号和成员列表
    seq, memberList = 0, [] # 初始化序列号和成员列表
    while 1: # 继续请求直到获取所有联系人信息
        seq, batchMemberList = _get_contact(seq)
        memberList.extend(batchMemberList) # 将新获取的成员信息添加到成员列表中
        if seq == 0: # 如果序列号为0，表示所有联系人已经获取完成
            break
    chatroomList, otherList = [], [] # 分别存储聊天群列表和其他联系人列表
    for m in memberList: # 遍历所有成员，根据条件将其分类
        if m['Sex'] != 0: # 如果是其他联系人（性别不为0），添加到otherList
            otherList.append(m)
        elif '@@' in m['UserName']:  # 如果是聊天群（UserName包含@@），添加到chatroomList
            chatroomList.append(m)
        elif '@' in m['UserName']: # 如果是公众号（UserName包含@），也添加到otherList
            otherList.append(m)
    if chatroomList: # 如果有新的聊天群信息，更新本地聊天群
        update_local_chatrooms(self, chatroomList)
    if otherList: # 如果有新的联系人信息，更新本地好友列表
        update_local_friends(self, otherList)
    return utils.contact_deep_copy(self, chatroomList) # 返回深拷贝的聊天群列表

# 获取好友列表
def get_friends(self, update=False):
    if update: # 如果需要更新联系人信息，则先获取最新的联系人
        self.get_contact(update=True)
    # 返回深拷贝的好友列表
    return utils.contact_deep_copy(self, self.memberList)

# 获取聊天室
def get_chatrooms(self, update=False, contactOnly=False):
    if contactOnly: # 如果contactOnly为True,更新聊天室列表,并返回更新后的聊天室列表
        return self.get_contact(update=True) 
    else:  # 如果contactOnly为False
        if update: # 如果需要更新
            self.get_contact(True) # 更新聊天室列表
        # 无论update是不是True,返回旧的聊天室列表
        return utils.contact_deep_copy(self, self.chatroomList)
# 获取公众号
def get_mps(self, update=False):
    if update: # 如果需要更新
        self.get_contact(update=True) # 更新联系人(聊天室和公众号和联系人)
    # 返回的是旧的数据
    return utils.contact_deep_copy(self, self.mpList)

# 设置联系人别名（备注名）
def set_alias(self, userName, alias):
    oldFriendInfo = utils.search_dict_list( # 查找 userName 对应的联系人信息。
        self.memberList, 'UserName', userName)
    if oldFriendInfo is None: # 如果没有找到对应的联系人信息
        return ReturnValue({'BaseResponse': { # 返回一个带有错误代码 -1001 的响应。
            'Ret': -1001, }})
    # 构造请求 URL，URL 用于发送修改备注的操作。lang 设置为 'zh_CN'（简体中文），pass_ticket 是一个用于验证请求的安全密钥。
    url = '%s/webwxoplog?lang=%s&pass_ticket=%s' % (
        self.loginInfo['url'], 'zh_CN', self.loginInfo['pass_ticket'])
    data = { # 构造请求数据 data
        'UserName': userName, # 目标联系人的用户名
        'CmdId': 2, # 表示设置备注名；
        'RemarkName': alias, # 新的备注名（别名）
        'BaseRequest': self.loginInfo['BaseRequest'], } # 登录请求的基本信息
    headers = {'User-Agent': config.USER_AGENT} # 设置请求头，指定 User-Agent 来模拟请求来源。
    # 使用 POST 请求发送数据。将 data 转换为 JSON 格式并编码为 UTF-8
    r = self.s.post(url, json.dumps(data, ensure_ascii=False).encode('utf8'),
                    headers=headers)
    r = ReturnValue(rawResponse=r) # 将返回的响应 r 封装为 ReturnValue 对象。
    if r: # 如果请求成功（即 r 为真），则更新本地联系人信息中的备注名。
        oldFriendInfo['RemarkName'] = alias
    return r

# 设置联系人是否置顶。
def set_pinned(self, userName, isPinned=True):
    url = '%s/webwxoplog?pass_ticket=%s' % ( # 构造请求 URL，包含 pass_ticket 用于验证请求。
        self.loginInfo['url'], self.loginInfo['pass_ticket'])
    data = { # 构造请求数据 data
        'UserName': userName, # 目标联系人的用户名
        'CmdId': 3, # 操作命令标识符，3 表示置顶操作；
        'OP': int(isPinned), # 操作标识，1 表示置顶，0 表示取消置顶；
        'BaseRequest': self.loginInfo['BaseRequest'], } # 登录请求的基本信息。
    headers = {'User-Agent': config.USER_AGENT} # 设置请求头，指定 User-Agent。
    r = self.s.post(url, json=data, headers=headers)  # 使用 POST 请求发送数据。
    return ReturnValue(rawResponse=r) # 返回请求的响应封装为 ReturnValue 对象

# 接受好友请求
def accept_friend(self, userName, v4='', autoUpdate=True):
    # 构建请求URL，传入当前时间戳和pass_ticket
    url = f"{self.loginInfo['url']}/webwxverifyuser?r={int(time.time())}&pass_ticket={self.loginInfo['pass_ticket']}"
    data = { # 构建请求数据
        'BaseRequest': self.loginInfo['BaseRequest'],  # 登录信息
        'Opcode': 3,  # 操作码，3代表接受好友请求
        'VerifyUserListSize': 1, # 待验证用户数量
        'VerifyUserList': [{
            'Value': userName, # 需要验证的用户名
            'VerifyUserTicket': v4, }],  # 验证票据
        'VerifyContent': '', # 验证信息内容，通常为空
        'SceneListCount': 1,  # 场景列表数量
        'SceneList': [33], # 场景类型，33代表接受好友请求
        'skey': self.loginInfo['skey'], } # skey，登录凭证
    headers = { # 请求头，指定内容类型和用户代理
        'ContentType': 'application/json; charset=UTF-8',
        'User-Agent': config.USER_AGENT}
    r = self.s.post(url, headers=headers, # 发送POST请求
                    data=json.dumps(data, ensure_ascii=False).encode('utf8', 'replace'))
    if autoUpdate: # 如果autoUpdate为True，更新好友信息
        self.update_friend(userName)
    return ReturnValue(rawResponse=r) # 返回请求结果

# 当 chatroomUserName 为 None 时，系统会查找该 userName 对应的好友信息，然后获取该好友的头像。
# 如果 userName 为空，系统会根据 chatroomUserName 获取群聊的头像。此时会更新 URL 为获取群聊头像的地址。
# (这种情况是指你想获取一个群聊的头像（不是某个成员的头像，而是整个群聊的头像）。)
# 如果 userName 和 chatroomUserName 都不为空，系统会首先查找群聊信息，如果群聊存在且有加密聊天室 ID，则使用加密 
# ID 来获取群聊成员的头像。(这种情况是指你想获取某个群聊成员的头像（即某个群聊中的具体成员头像）。)
# (每次调用时，只会返回一个头像)
def get_head_img(self, userName=None, chatroomUserName=None, picDir=None):
    ''' 获取头像
     * 如果只想获取聊天对象的头像：只设置userName
     * 如果只想获取群聊头像：只设置chatroomUserName
     * 如果想获取群聊成员头像：需要同时设置userName和chatroomUserName
    '''
    params = { # 构建请求参数
        'userName': userName or chatroomUserName or self.storageClass.userName, # 选择用户名或群聊用户名
        'skey': self.loginInfo['skey'],  # 登录凭证
        'type': 'big', }  # 获取大图
    url = '%s/webwxgeticon' % self.loginInfo['url'] # 设置头像请求的URL
    # 如果chatroomUserName为空，获取个人好友头像
    if chatroomUserName is None:
        infoDict = self.storageClass.search_friends(userName=userName) # 根据id查找当前对象
        if infoDict is None: # 如果找不到好友
            return ReturnValue({'BaseResponse': {
                'ErrMsg': 'No friend found', # 错误消息：未找到好友
                'Ret': -1001, }})  # 错误返回码
    else: # 如果chatroomUserName不为空
        if userName is None:  # 如果username为空
            url = '%s/webwxgetheadimg' % self.loginInfo['url'] # 更新URL用于获取群聊头像
        else: # 如果两者都不是None
            chatroom = self.storageClass.search_chatrooms( # 查找群聊信息
                userName=chatroomUserName)
            if chatroomUserName is None: # 如果没有找到群聊
                return ReturnValue({'BaseResponse': {
                    'ErrMsg': 'No chatroom found',  # 错误消息：未找到群聊
                    'Ret': -1001, }})
            # 如果找到了群聊，如果有加密聊天室ID,获取群聊的加密ID
            if 'EncryChatRoomId' in chatroom:
                params['chatroomid'] = chatroom['EncryChatRoomId'] # 设置聊天室id参数
            params['chatroomid'] = params.get( # 设置群聊ID，若没有加密ID则使用普通ID
                'chatroomid') or chatroom['UserName']
    headers = {'User-Agent': config.USER_AGENT}  # 请求头，指定用户代理
    # stream=True 表示当你发送 GET 请求时，不立即下载响应的内容，而是保持连接开放，直到你明确地需要读取响应体的内容。这
    # 对于处理大文件（例如图片、视频、或者其他大型资源）特别有用，因为它可以逐块下载响应内容，而不必一次性加载整个文件到内存中。
    r = self.s.get(url, params=params, stream=True, headers=headers)  # 发送GET请求获取头像
    tempStorage = io.BytesIO() # 创建内存中的存储空间，用于保存下载的头像
    for block in r.iter_content(1024): # 下载头像数据流,# 每次读取1024字节
        tempStorage.write(block)  # 将数据写入内存
    if picDir is None: # 如果没有指定保存路径，则直接返回头像数据
        return tempStorage.getvalue()
    with open(picDir, 'wb') as f: # 否则将头像保存到指定路径
        f.write(tempStorage.getvalue())
    tempStorage.seek(0) # 将内存指针移动到文件开头
    return ReturnValue({'BaseResponse': { # 返回成功消息和图片格式后缀
        'ErrMsg': 'Successfully downloaded',  # 成功消息
        'Ret': 0, }, # 成功返回码
        'PostFix': utils.get_image_postfix(tempStorage.read(20)), })   # 获取图片后缀

# 创建聊天室
def create_chatroom(self, memberList, topic=''):
     # 构建创建聊天室的 URL，包含必要的 pass_ticket 和当前时间戳
    url = '%s/webwxcreatechatroom?pass_ticket=%s&r=%s' % (
        self.loginInfo['url'], self.loginInfo['pass_ticket'], int(time.time()))
    data = { # 构建请求的 JSON 数据，包含 BaseRequest、成员列表和群聊话题
        'BaseRequest': self.loginInfo['BaseRequest'], # 请求所需的 BaseRequest，用于认证
        'MemberCount': len(memberList.split(',')), # 成员数量（通过逗号分隔的用户名列表）
        'MemberList': [{'UserName': member} for member in memberList.split(',')], # 每个成员的 UserName
        'Topic': topic, }
    headers = { # 设置请求头，指定内容类型和用户代理
        'content-type': 'application/json; charset=UTF-8',  # 设置为 JSON 格式
        'User-Agent': config.USER_AGENT} # 设置 User-Agent，通常用来标识客户端
    r = self.s.post(url, headers=headers, # 发送 POST 请求，提交 JSON 数据
                    data=json.dumps(data, ensure_ascii=False).encode('utf8', 'ignore')) # 将 data 转换为 JSON 格式并编码
    return ReturnValue(rawResponse=r) # 返回请求的原始响应

# 设置聊天室名称
def set_chatroom_name(self, chatroomUserName, name):
    # 构建更新聊天室名称的 URL，包含 pass_ticket
    url = '%s/webwxupdatechatroom?fun=modtopic&pass_ticket=%s' % (
        self.loginInfo['url'], self.loginInfo['pass_ticket'])
    # 构建请求数据，包含 BaseRequest、聊天室的 UserName 和新话题名称
    data = {
        'BaseRequest': self.loginInfo['BaseRequest'], # 请求所需的 BaseRequest，用于认证
        'ChatRoomName': chatroomUserName,  # 要更新名称的聊天室的 UserName
        'NewTopic': name, }  # 新的聊天室话题（即新的聊天室名称）
    headers = { # 设置请求头，指定内容类型和用户代理
        'content-type': 'application/json; charset=UTF-8',  # 设置为 JSON 格式
        'User-Agent': config.USER_AGENT}
    r = self.s.post(url, headers=headers, # 发送 POST 请求，提交 JSON 数据
                    data=json.dumps(data, ensure_ascii=False).encode('utf8', 'ignore'))
    return ReturnValue(rawResponse=r) # 返回请求的原始响应

# 删除聊天室成员
def delete_member_from_chatroom(self, chatroomUserName, memberList):
    # 构建移除成员的 URL，包含 pass_ticket
    url = '%s/webwxupdatechatroom?fun=delmember&pass_ticket=%s' % (
        self.loginInfo['url'], self.loginInfo['pass_ticket'])
    # 构建请求的数据，包含 BaseRequest、聊天室的 UserName 和要删除成员的 UserName 列表
    data = {
        'BaseRequest': self.loginInfo['BaseRequest'], # 请求所需的 BaseRequest，用于认证
        'ChatRoomName': chatroomUserName,  # 要操作的聊天室 UserName
         # 将 memberList 中每个成员的 UserName 提取并通过逗号连接起来，作为待删除成员列表
        'DelMemberList': ','.join([member['UserName'] for member in memberList]), }
    headers = { # 设置请求头，指定内容类型和用户代理
        'content-type': 'application/json; charset=UTF-8',
        'User-Agent': config.USER_AGENT}
    # 发送 POST 请求，提交数据并删除成员
    r = self.s.post(url, data=json.dumps(data), headers=headers)
    return ReturnValue(rawResponse=r) # 返回请求的原始响应

# 为聊天室添加成员
# 微信的群聊在不同的成员数范围内，采取不同的添加或邀请方式。通常
# 小于 40 人的群聊：可以直接添加成员，无需邀请。
# 超过 40 人的群聊：微信限制了直接添加成员的操作，必须通过邀请的方式，成员才能加入群聊。
# 在微信中，确实是超过一定人数（通常是 40 人）后，才会使用邀请的方式来添加新成员。
# 这个设计是为了确保群聊的稳定性和安全性，避免直接添加成员对群聊管理带来的负面影响。

def add_member_into_chatroom(self, chatroomUserName, memberList,
                             useInvitation=False):
     # 如果不使用邀请方式，检查聊天室成员数，决定是否需要使用邀请方式
    if not useInvitation:
        chatroom = self.storageClass.search_chatrooms( # 查找指定聊天室的详细信息
            userName=chatroomUserName)
        if not chatroom: # 如果没有找到聊天室信息，更新聊天室信息
            chatroom = self.update_chatroom(chatroomUserName)
        # 如果聊天室成员超过了设置的邀请限制人数，则使用邀请方式
        if len(chatroom['MemberList']) > self.loginInfo['InviteStartCount']:
            useInvitation = True
    # 根据是否需要邀请方式，设置操作函数和成员列表的参数名
    if useInvitation:
        fun, memberKeyName = 'invitemember', 'InviteMemberList'  # 使用邀请方式时，操作函数是 'invitemember'
    else: # 否则，不使用邀请方式时,操作函数是 'addmember'
        fun, memberKeyName = 'addmember', 'AddMemberList'
     # 构建请求 URL，使用指定的操作函数（addmember 或 invitemember）
    url = '%s/webwxupdatechatroom?fun=%s&pass_ticket=%s' % (
        self.loginInfo['url'], fun, self.loginInfo['pass_ticket'])
    # 构建请求数据，包括 BaseRequest、聊天室的 UserName 和成员列表
    params = {
        'BaseRequest': self.loginInfo['BaseRequest'], # 请求所需的 BaseRequest，用于认证
        'ChatRoomName': chatroomUserName,   # 要操作的聊天室 UserName
        memberKeyName: memberList, }  # 要添加或邀请的成员列表
    headers = { # 设置请求头，指定内容类型和用户代理
        'content-type': 'application/json; charset=UTF-8',
        'User-Agent': config.USER_AGENT}
    r = self.s.post(url, data=json.dumps(params), headers=headers) # 发送 POST 请求，提交数据来添加或邀请成员
    return ReturnValue(rawResponse=r) # 返回请求的原始响应
