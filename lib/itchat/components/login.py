import os
import time
import re
import io
import threading
import json
import xml.dom.minidom
import random
import traceback
import logging
try:
    from httplib import BadStatusLine
except ImportError:
    from http.client import BadStatusLine

import requests
from pyqrcode import QRCode

from .. import config, utils
from ..returnvalues import ReturnValue
from ..storage.templates import wrap_user_dict
from .contact import update_local_chatrooms, update_local_friends
from .messages import produce_msg

logger = logging.getLogger('itchat') # 初始化 'itchat' 模块的日志记录器

# 该函数将与登录相关的方法添加到 core 对象中。
def load_login(core):
    core.login = login  # 将 login 函数赋值给 core 对象
    core.get_QRuuid = get_QRuuid # 将获取 QR UUID 的函数赋值给 core
    core.get_QR = get_QR # 将获取 QR 码的函数赋值给 core
    core.check_login = check_login # 将检查登录状态的函数赋值给 core
    core.web_init = web_init  # 将 web 初始化函数赋值给 core
    core.show_mobile_login = show_mobile_login # 将显示手机登录界面的函数赋值给 core
    core.start_receiving = start_receiving # 将开始接收消息的函数赋值给 core
    core.get_msg = get_msg # 将获取消息的函数赋值给 core
    core.logout = logout # 将登出函数赋值给 core

# 处理用户的登录流程。
def login(self, enableCmdQR=False, picDir=None, qrCallback=None,
          loginCallback=None, exitCallback=None):
    if self.alive or self.isLogging:  # 如果core正在运行或者正在登录
        logger.warning('itchat has already logged in.') # 发出警告:itchat已经登录
        return # 直接返回
    self.isLogging = True # 设置 isLogging 为 True，表示登录流程已开始
    logger.info('Ready to login.')  # 日志记录显示准备登录
    while self.isLogging: # 当core正在登录时
        uuid = push_login(self)  # 尝试推送登录请求并获取 QR 码的 UUID
        if uuid: # 如果存在uuid
            qrStorage = io.BytesIO() # 创建一个 BytesIO 流来存储 QR 码
        else: # 如果不存在uuid
            logger.info('Getting uuid of QR code.')  # 日志记录提示正在获取 QR UUID
            while not self.get_QRuuid():  # 一直循环直到成功获取 QR UUID
                time.sleep(1)  # 每隔 1 秒重试一次
            logger.info('Downloading QR code.') # 日志记录提示正在下载 QR 码
            qrStorage = self.get_QR(enableCmdQR=enableCmdQR, # 获取实际的 QR 码
                                    picDir=picDir, qrCallback=qrCallback)
            # logger.info('Please scan the QR code to log in.')  # (被注释掉) 提示用户扫描二维码登录
        isLoggedIn = False # 初始化登录状态为 False
        while not isLoggedIn:  # 持续检查登录状态，直到成功登录
            status = self.check_login()  # 检查登录状态
            if hasattr(qrCallback, '__call__'):  # 如果定义了 qrCallback 函数，如果可调用,则调用它
                qrCallback(uuid=self.uuid, status=status,
                           qrcode=qrStorage.getvalue())
            if status == '200':  # 如果状态为 '200'，说明登录成功
                isLoggedIn = True  # 设置 isLoggedIn 为 True，表示登录成功
            elif status == '201':  # 如果状态为 '201'，需要用户在手机上确认登录
                if isLoggedIn is not None:
                    logger.info('Please press confirm on your phone.')  # 提示用户在手机上确认登录
                    isLoggedIn = None # 重置 isLoggedIn 为 None
                    time.sleep(7) # 等待 7 秒后再检查
                time.sleep(0.5) # 每 0.5 秒检查一次
            # 408 是表示请求超时的状态码，用于告知客户端请求的处理超出了允许的时间范围
            elif status != '408': # 如果状态不是 '408'（超时错误）
                break # 如果发生了其他错误，则退出循环
        if isLoggedIn: # 如果成功登录，退出外层的循环
            break
        elif self.isLogging: # 如果登录过程仍然有效，且超时则重新加载二维码
            logger.info('Log in time out, reloading QR code.')
    else:  # 如果用户停止了登录过程，则退出
        return  
    logger.info('Loading the contact, this may take a little while.')  # 日志记录提示正在加载联系人
    self.web_init()  
    self.show_mobile_login() 
    self.get_contact(True) # 获取联系人列表，True 表示需要更新
    if hasattr(loginCallback, '__call__'): # 如果定义了 loginCallback 函数，则调用它
        r = loginCallback() # 调用登录回调
    else:
        # utils.clear_screen()  # (被注释掉) 清屏
        if os.path.exists(picDir or config.DEFAULT_QR):  # 检查二维码图片是否存在
            os.remove(picDir or config.DEFAULT_QR)  # 删除二维码图片文件
        logger.info('Login successfully as %s' % self.storageClass.nickName) # 日志记录成功登录信息
    self.start_receiving(exitCallback)  # 开始接收服务器消息
    self.isLogging = False  # 设置 isLogging 为 False，表示登录流程完成

# 获取uuid
def push_login(core):
    cookiesDict = core.s.cookies.get_dict() # 获取当前会话的 cookies 字典
    if 'wxuin' in cookiesDict: # 检查 cookies 中是否存在 wxuid(微信uid)
        url = '%s/cgi-bin/mmwebwx-bin/webwxpushloginurl?uin=%s' % (
            config.BASE_URL, cookiesDict['wxuin']) # 构造推送登录的请求 URL
        headers = {'User-Agent': config.USER_AGENT} # 设置请求头，指定用户代理
        r = core.s.get(url, headers=headers).json() # 发送 GET 请求并将响应转换为 JSON 格式
        # 检查返回的数据中是否包含 'uuid' 且 'ret' 值为 0
        if 'uuid' in r and r.get('ret') in (0, '0'):
            core.uuid = r['uuid'] # 保存 'uuid' 到 core 对象
            return r['uuid'] # 返回获取到的 'uuid'
    return False  # 如果条件不满足，则返回 False
# 获取二维码uuid
def get_QRuuid(self):
    url = '%s/jslogin' % config.BASE_URL # 构造获取二维码 UUID 的请求 URL
    params = {
        'appid': 'wx782c26e4c19acffb',  # 微信登录的应用 ID
        'fun': 'new', # 指定功能为新登录
        'redirect_uri': 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/webwxnewloginpage?mod=desktop',  # 重定向 URL
        'lang': 'zh_CN'}  # 指定语言为中文
    headers = {'User-Agent': config.USER_AGENT} # 设置请求头，指定用户代理
    r = self.s.get(url, params=params, headers=headers) # 发送 GET 请求获取登录页面数据
    # 使用正则表达式提取返回数据中的 'code' 和 'uuid'
    regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)";'
    # 用于在响应文本 r.text 中通过正则表达式 regx 查找特定模式并提取出相应的数据。
    data = re.search(regx, r.text) 
    if data and data.group(1) == '200': # 如果提取成功且返回码为 200
        self.uuid = data.group(2) # 保存 'uuid' 到实例变量
        return self.uuid # 返回获取到的 'uuid'


def get_QR(self, uuid=None, enableCmdQR=False, picDir=None, qrCallback=None):
    uuid = uuid or self.uuid # 如果没有传入 uuid，则使用实例的 uuid（默认值为 self.uuid）
    picDir = picDir or config.DEFAULT_QR # 如果没有指定 picDir，则使用默认的图片保存路径
    qrStorage = io.BytesIO() # 创建一个 BytesIO 对象，用于存储二维码图像数据
    qrCode = QRCode('https://login.weixin.qq.com/l/' + uuid) # 创建一个二维码对象，二维码内容是二维码登录链接加上 uuid
    qrCode.png(qrStorage, scale=10) # 将生成的二维码图像保存到 qrStorage，scale=10 控制二维码的大小
    if hasattr(qrCallback, '__call__'): # 如果传入了 qrCallback 函数，并且它是可调用的
        qrCallback(uuid=uuid, status='0', qrcode=qrStorage.getvalue()) # 调用回调函数，传入 uuid、状态（'0'）、以及二维码数据
    else: # 如果没有传入回调函数，将二维码保存到指定的文件路径 picDir
        with open(picDir, 'wb') as f:
            f.write(qrStorage.getvalue()) # 写入二维码图像到文件
        if enableCmdQR: # 如果启用了命令行二维码显示，打印二维码文本到命令行
            utils.print_cmd_qr(qrCode.text(1), enableCmdQR=enableCmdQR)
        else: # 否则将二维码图像文件路径传递给打印函数进行显示
            utils.print_qr(picDir)
    return qrStorage  # 返回存储二维码数据的 qrStorage 对象

# 检查登录状态
def check_login(self, uuid=None):
    uuid = uuid or self.uuid # 如果没有传入 uuid，则使用实例的 uuid（默认值为 self.uuid）
    url = '%s/cgi-bin/mmwebwx-bin/login' % config.BASE_URL # 构造登录请求的 URL
    localTime = int(time.time()) # 获取当前的时间戳，用于构建请求参数中的时间部分
    # loginicon:用于告诉服务器在登录页面中显示图标。tip=1 通常意味着请求时显示提示
    params = 'loginicon=true&uuid=%s&tip=1&r=%s&_=%s' % ( 
        uuid, int(-localTime / 1579), localTime)
    headers = {'User-Agent': config.USER_AGENT} # 设置请求头，指定 User-Agent
    r = self.s.get(url, params=params, headers=headers) # 发送 GET 请求进行登录检查
    regx = r'window.code=(\d+)' # 使用正则表达式从响应中提取返回的 'code' 值
    data = re.search(regx, r.text) # 搜索并提取 'code' 的值
    if data and data.group(1) == '200': # 如果返回码是 200，说明登录成功
        if process_login_info(self, r.text): # 处理登录信息并返回 '200'
            return '200'
        else:
            return '400'  # 登录信息处理失败
    elif data: # 如果返回的 code 不是 200，则返回提取到的 'code' 值
        return data.group(1)
    else: # 如果没有匹配到返回的 code，则返回 400
        return '400'

# 处理登录信息、获取必需的 URL 和凭证。
def process_login_info(core, loginContent):
    '''当扫码登录完成后：
     * 获取 syncUrl 和 fileUploadingUrl (用于消息同步和文件上传的 URL）
     * 生成 deviceid 和 msgid （设备标识符和消息 ID）
     * 获取 skey, wxsid, wxuin, pass_ticket （用于验证和保持登录状态的关键凭证）
    '''
    # 使用正则表达式从 loginContent 中提取 redirect_uri，这是微信登录流程中的一个跳转 URL，通常会指向用户登录后的页面。
    regx = r'window.redirect_uri="(\S+)";' 
    core.loginInfo['url'] = re.search(regx, loginContent).group(1) 
    # extspam 字段是一个自定义的请求头字段，看起来是一个反垃圾信息或验证码相关的标识，通常用来增强服务器对请求的验证或检查
    headers = {'User-Agent': config.USER_AGENT, # 设置请求头信息
               'client-version': config.UOS_PATCH_CLIENT_VERSION,
               'extspam': config.UOS_PATCH_EXTSPAM,
               'referer': 'https://wx.qq.com/?&lang=zh_CN&target=t'
               }
    # 通过 core.s.get 发送 GET 请求，访问提取到的 redirect_uri。allow_redirects=False 禁止自动重定向，允许我们手动处理重定向结果。
    r = core.s.get(core.loginInfo['url'],
                   headers=headers, allow_redirects=False)
    # 切片操作会截取到最后一个/的部分
    core.loginInfo['url'] = core.loginInfo['url'][:core.loginInfo['url'].rfind(
        '/')]
    # 对每个 indexUrl 和其对应的 detailedUrl（包含文件上传和消息同步 URL）进行匹配。
    # 使用 core.loginInfo['url'] 中的域名部分（即 indexUrl）来选择匹配的 URL。
    for indexUrl, detailedUrl in (
            ("wx2.qq.com", ("file.wx2.qq.com", "webpush.wx2.qq.com")),
            ("wx8.qq.com", ("file.wx8.qq.com", "webpush.wx8.qq.com")),
            ("qq.com", ("file.wx.qq.com", "webpush.wx.qq.com")),
            ("web2.wechat.com", ("file.web2.wechat.com", "webpush.web2.wechat.com")),
            ("wechat.com", ("file.web.wechat.com", "webpush.web.wechat.com"))):
        # 每个detailedUrl都是个元组
        fileUrl, syncUrl = ['https://%s/cgi-bin/mmwebwx-bin' %
                            url for url in detailedUrl]
        # 如果当前 core.loginInfo['url'] 中包含某个 indexUrl(字符串的包含)，就把对应的 fileUrl 和 syncUrl 保存到 core.loginInfo 字典中。
        if indexUrl in core.loginInfo['url']:
            core.loginInfo['fileUrl'], core.loginInfo['syncUrl'] = \
                fileUrl, syncUrl
            break
    else: # 如果在 core.loginInfo['url'] 中没有找到匹配的 indexUrl，就将 fileUrl 和 syncUrl 设置为 core.loginInfo['url']，即使用当前 URL。
        core.loginInfo['fileUrl'] = core.loginInfo['syncUrl'] = core.loginInfo['url']
    # 生成一个随机的 deviceid。这个设备 ID 是由随机数生成的，它的格式通常为一个以 'e' 开头的字符串，后面跟着 15 位随机数字。
    core.loginInfo['deviceid'] = 'e' + repr(random.random())[2:17]
    # 记录登录的时间（精确到毫秒）。time.time() 返回当前时间的 Unix 时间戳（秒），乘以 1e3 转换为毫秒单位。
    core.loginInfo['logintime'] = int(time.time() * 1e3)
    core.loginInfo['BaseRequest'] = {} # 初始化一个空字典 BaseRequest，稍后将用于存储与请求相关的其他信息。
    cookies = core.s.cookies.get_dict() # 获取当前会话中的 cookies，并将其转换为字典形式。
    # 使用正则表达式从响应文本 r.text 中提取 <skey> 和 </skey> 标签之间的内容，即微信的 skey（会话标识符）。
    res = re.findall('<skey>(.*?)</skey>', r.text, re.S) # re.S 让 . 匹配 所有字符，包括换行符
    skey = res[0] if res else None
    res = re.findall(
        '<pass_ticket>(.*?)</pass_ticket>', r.text, re.S)
    # 提取 pass_ticket（登录验证票据），它用于后续请求验证身份。
    pass_ticket = res[0] if res else None
    # 如果成功提取到 skey，则将其保存到 core.loginInfo 和 core.loginInfo['BaseRequest'] 中。
    if skey is not None:
        core.loginInfo['skey'] = core.loginInfo['BaseRequest']['Skey'] = skey
    # 从 cookies 中提取 wxsid 和 wxuin（微信会话 ID 和用户 ID），并将它们分别保存到 core.loginInfo 和 core.loginInfo['BaseRequest'] 中。
    core.loginInfo['wxsid'] = core.loginInfo['BaseRequest']['Sid'] = cookies["wxsid"]
    core.loginInfo['wxuin'] = core.loginInfo['BaseRequest']['Uin'] = cookies["wxuin"]
    # 如果提取到 pass_ticket，则将其保存到 core.loginInfo 中。
    if pass_ticket is not None:
        core.loginInfo['pass_ticket'] = pass_ticket
    # 代码中有个注释提到 pass_ticket 和 deviceid 之间的关系，提出 deviceid 是一个随机生成的值，而 pass_ticket 则是登录验证的一部分。
    # A question : why pass_ticket == DeviceID ?
    #               deviceID is only a randomly generated number

    # UOS PATCH By luvletter2333, Sun Feb 28 10:00 PM
    # for node in xml.dom.minidom.parseString(r.text).documentElement.childNodes:
    #     if node.nodeName == 'skey':
    #         core.loginInfo['skey'] = core.loginInfo['BaseRequest']['Skey'] = node.childNodes[0].data
    #     elif node.nodeName == 'wxsid':
    #         core.loginInfo['wxsid'] = core.loginInfo['BaseRequest']['Sid'] = node.childNodes[0].data
    #     elif node.nodeName == 'wxuin':
    #         core.loginInfo['wxuin'] = core.loginInfo['BaseRequest']['Uin'] = node.childNodes[0].data
    #     elif node.nodeName == 'pass_ticket':
    #         core.loginInfo['pass_ticket'] = core.loginInfo['BaseRequest']['DeviceID'] = node.childNodes[0].data
    # 检查 core.loginInfo 中是否包含所有必需的登录信息（skey、wxsid、wxuin、pass_ticket）。如果缺少任何一个，记录错误日志并返
    # 回 False，表示登录失败。
    if not all([key in core.loginInfo for key in ('skey', 'wxsid', 'wxuin', 'pass_ticket')]):
        logger.error(
            'Your wechat account may be LIMITED to log in WEB wechat, error info:\n%s' % r.text)
        core.isLogging = False
        return False
    return True # 如果所有必需的登录信息都已提取并保存，返回 True，表示登录成功，信息处理完成。

def web_init(self):
    # 构建发送请求的 URL，'%s/webwxinit' 是通过 base URL 和 '/webwxinit' 拼接得到的完整 URL
    url = '%s/webwxinit' % self.loginInfo['url']
    # 设置请求的参数，包括当前时间戳的一个变换（r）和 pass_ticket，用于身份验证
    params = {
        'r': int(-time.time() / 1579),  # 计算当前的时间戳，避免服务器缓存
        'pass_ticket': self.loginInfo['pass_ticket'], }  # 传递从登录过程中获得的 pass_ticket
    # 设置请求的数据，包括 BaseRequest 信息（包含用户会话信息）
    data = {'BaseRequest': self.loginInfo['BaseRequest'], }
    # 设置 HTTP 请求头，表明请求的内容类型为 JSON 格式，并指定 User-Agent（模拟客户端）
    headers = {
        'ContentType': 'application/json; charset=UTF-8', # 请求的数据类型是 JSON 格式
        'User-Agent': config.USER_AGENT, } # 请求头中的 User-Agent 用于模拟客户端（如浏览器等）
    # 发送 POST 请求到微信的初始化接口（/webwxinit），带上 params、data 和 headers
    r = self.s.post(url, params=params, data=json.dumps(data), headers=headers)
    # 将响应内容从字节串转换为 JSON 对象（字典格式），并解码为 UTF-8 字符串
    dic = json.loads(r.content.decode('utf-8', 'replace'))
    # 处理登录信息中的用户昵称（包括表情符号的处理）
    utils.emoji_formatter(dic['User'], 'NickName')
    # 将从响应中获得的 'InviteStartCount' 转换为整数并保存到 loginInfo 中
    self.loginInfo['InviteStartCount'] = int(dic['InviteStartCount'])
    # 处理用户信息，包装成结构化的字典并保存
    self.loginInfo['User'] = wrap_user_dict(
        utils.struct_friend_info(dic['User'])) # 包装用户的详细信息
    self.memberList.append(self.loginInfo['User']) # 将用户添加到 memberList 中，作为好友列表的一部分
    # 获取并保存 SyncKey，这是微信会话同步的关键，后续用于同步消息
    self.loginInfo['SyncKey'] = dic['SyncKey']
    # 将 SyncKey 转换为字符串的形式，格式为 "key_value|key_value"
    self.loginInfo['synckey'] = '|'.join(['%s_%s' % (item['Key'], item['Val'])
                                          for item in dic['SyncKey']['List']])
    # 将登录用户的 UserName 和 NickName 保存到 storageClass 中，便于后续使用
    self.storageClass.userName = dic['User']['UserName']
    self.storageClass.nickName = dic['User']['NickName']
    # 获取并处理返回的联系人列表（ContactList）
    contactList = dic.get('ContactList', []) # 获取联系人列表，如果没有则返回空列表
    # 分离出群聊和其他联系人
    chatroomList, otherList = [], []
    for m in contactList: # 遍历联系人列表
        if m['Sex'] != 0:  # 过滤掉性别为 0（未知性别）的联系人
            otherList.append(m) # 将其加入到其他联系人列表
        elif '@@' in m['UserName']: # 判断是否是群聊（群聊用户名通常包含 '@@'）
            m['MemberList'] = [] # 清除群聊成员列表的脏数据（防止污染）
            chatroomList.append(m)  # 将群聊联系人添加到群聊列表
        elif '@' in m['UserName']: # 判断是否是公众号（用户名包含 '@'）
             # 将公众号加入到其他联系人列表
            otherList.append(m)
    if chatroomList: # 如果存在群聊，将其更新到本地存储
        update_local_chatrooms(self, chatroomList)
    if otherList: # 如果存在其他联系人（包括朋友和公众号），将其更新到本地存储
        update_local_friends(self, otherList)
    return dic # 返回初始化的响应数据，供后续处理

# 这段代码的目的是让微信服务器确认手机端已允许扫码登录的请求，因此通过 Code = 3 提交一个确认请求，手机端会基于此
# 确认并继续执行登录。
def show_mobile_login(self):
     # 构建请求的 URL，将登录时的 URL 和 pass_ticket 结合在一起，用于发送登录状态通知
    url = '%s/webwxstatusnotify?lang=zh_CN&pass_ticket=%s' % (
        self.loginInfo['url'], self.loginInfo['pass_ticket'])
    # 准备请求的数据，包括 BaseRequest（用户会话信息），以及登录请求的其他字段：
    # 'Code' 是状态码（3 代表从手机登录确认）
    # 'FromUserName' 和 'ToUserName' 是当前用户的用户名，表示通知的发送和接收对象
    # 'ClientMsgId' 是客户端消息 ID，通常是一个时间戳，用于唯一标识每条消息
    data = {
        'BaseRequest': self.loginInfo['BaseRequest'], # 用户的会话信息
        'Code': 3, # 微信用来通知手机端确认登录的请求。
        'FromUserName': self.storageClass.userName, # 当前用户的 UserName
        'ToUserName': self.storageClass.userName, # 目标用户是当前用户自己，表示通知自己
        'ClientMsgId': int(time.time()), } # 使用当前时间戳作为消息 ID，确保唯一性
    # 设置请求头，表明请求体为 JSON 格式，并指定 User-Agent 用于模拟客户端环境
    headers = {
        'ContentType': 'application/json; charset=UTF-8',  # 请求内容类型为 JSON 格式
        'User-Agent': config.USER_AGENT, }
    # 发送 POST 请求到微信的状态通知接口，传递 URL、数据和请求头
    r = self.s.post(url, data=json.dumps(data), headers=headers)
    # 返回一个包含原始响应的对象（可以用于后续的处理或调试）
    return ReturnValue(rawResponse=r)

# 启动一个后台线程，以持续接收来自微信服务器的消息，并处理同步检查和更新。
def start_receiving(self, exitCallback=None, getReceivingFnOnly=False):
    # 设置 self.alive 为 True，表示接收线程处于活动状态，程序将不断运行，直到 self.alive 被设置为 False
    self.alive = True
    # 定义一个内部函数 maintain_loop，该函数会持续循环接收并处理消息，直到 self.alive 被设置为 False
    def maintain_loop():
        retryCount = 0 # 初始化重试次数为 0，记录在发生异常时重试的次数
        # 循环，直到 self.alive 为 False，表示接收线程应该终止
        while self.alive: 
            try:
                # 调用 sync_check(self) 来检查是否有新消息。返回值表示当前是否有需要处理的消息。
                i = sync_check(self)
                # 如果返回值是 None，说明请求出现问题或没有消息要处理，停止接收
                if i is None:
                    self.alive = False # 设置 self.alive 为 False，退出循环
                # 如果返回值是 '0'，说明没有新消息，继续等待
                elif i == '0':
                    pass
                # 如果 i 不是 '0'，表示有新的消息，需要进行处理
                else:
                    # 调用 self.get_msg() 获取所有的消息和联系人信息，msgList 是消息列表，contactList 是联系人列表
                    msgList, contactList = self.get_msg()
                    # 如果 msgList 中有新消息，处理这些消息
                    if msgList:
                        # 调用 produce_msg(self, msgList) 函数处理消息，返回一个已处理的消息列表
                        msgList = produce_msg(self, msgList)
                        # 将处理后的每条消息放入消息队列 self.msgList 中
                        for msg in msgList:
                            self.msgList.put(msg)
                    # 如果 contactList 中有联系人信息，更新本地联系人数据
                    if contactList:
                        # 初始化两个列表，一个存储聊天室，一个存储其他联系人
                        chatroomList, otherList = [], []
                        # 遍历所有联系人，按类型分类
                        for contact in contactList:
                            if '@@' in contact['UserName']:  # 如果用户名包含 '@@'，表示是一个聊天室
                                chatroomList.append(contact) # 将聊天室添加到 chatroomList
                            else: # 否则是普通联系人
                                otherList.append(contact) # 将联系人添加到 otherList
                        # 调用 update_local_chatrooms 更新本地的聊天室信息
                        chatroomMsg = update_local_chatrooms( # 更新本地聊天室
                            self, chatroomList)
                        # 将当前登录用户信息添加到聊天室消息中
                        chatroomMsg['User'] = self.loginInfo['User']
                        # 将聊天室消息放入消息队列 self.msgList
                        self.msgList.put(chatroomMsg)
                        # 调用 update_local_friends 更新本地的好友信息
                        update_local_friends(self, otherList) 
                retryCount = 0 # 每次循环结束时重置重试计数器
            except requests.exceptions.ReadTimeout: # 如果捕获到 ReadTimeout 错误，什么都不做，继续下一次尝试
                pass
            except: # 捕获其他异常
                retryCount += 1 # 增加重试计数器
                logger.error(traceback.format_exc()) # 打印异常堆栈信息
                # 如果重试次数超过设定的最大值，停止尝试，退出接收
                if self.receivingRetryCount < retryCount:
                    logger.error("Having tried %s times, but still failed. " % (
                        retryCount) + "Stop trying...")
                    self.alive = False  # 设置 self.alive 为 False，退出循环
                else: # 否则等待 1 秒后再重试
                    time.sleep(1)
        self.logout() # 在接收停止后执行注销操作
        if hasattr(exitCallback, '__call__'): # 如果 exitCallback 是可调用的，则执行 exitCallback
            exitCallback()
        else: # 如果没有传入 exitCallback，打印退出日志
            logger.info('LOG OUT!')
    # 如果 getReceivingFnOnly 参数为 True，则只返回 maintain_loop 函数，而不启动线程
    if getReceivingFnOnly:
        return maintain_loop
    else: # 否则，启动一个新的线程来执行 maintain_loop 函数，处理消息接收
        maintainThread = threading.Thread(target=maintain_loop)
        maintainThread.setDaemon(True) # 设置线程为守护线程，意味着当主程序退出时，线程会被强制终止
        maintainThread.start() # 启动线程

# 负责与微信服务器进行同步检查，确认是否有新的消息。它通过发送带有认证信息和同步密钥的请求来检查服务器的响应，并解析返
# 回的 retcode 和 selector。如果服务器返回的状态不正常，函数会记录错误并返回 None，否则返回 selector，该值用于指示消息的状态。
def sync_check(self):
     # 构造 synccheck 请求的 URL，使用 self.loginInfo 中的 syncUrl 或默认 url
    url = '%s/synccheck' % self.loginInfo.get('syncUrl', self.loginInfo['url'])
    params = { # 定义请求的参数，包含时间戳、登录相关的凭证、同步密钥等
        'r': int(time.time() * 1000), # 请求的时间戳，单位是毫秒
        'skey': self.loginInfo['skey'], # skey，用于验证登录状态
        'sid': self.loginInfo['wxsid'], # wxsid，会话 ID
        'uin': self.loginInfo['wxuin'], # wxuin，用户 ID
        'deviceid': self.loginInfo['deviceid'], # deviceid，设备标识符
        'synckey': self.loginInfo['synckey'],  # synckey，同步密钥，用于同步消息
        '_': self.loginInfo['logintime'], }  # 防止缓存的时间戳，避免请求被缓存
    headers = {'User-Agent': config.USER_AGENT} # 设置请求头部，指定 User-Agent 用于请求
    self.loginInfo['logintime'] += 1 # 每次发送请求后，将登录时间增加 1，保持请求时间的变化
    try:
        # 使用 GET 方法发送请求，并等待响应，设置超时时间为 config.TIMEOUT
        r = self.s.get(url, params=params, headers=headers,
                       timeout=config.TIMEOUT)
    except requests.exceptions.ConnectionError as e: # 捕获网络连接错误
        try:
            if not isinstance(e.args[0].args[1], BadStatusLine): # 检查是否是 BadStatusLine 错误，如果不是，则抛出异常
                raise
            # will return a package with status '0 -'
            # and value like:
            # 6f:00:8a:9c:09:74:e4:d8:e0:14:bf:96:3a:56:a0:64:1b:a4:25:5d:12:f4:31:a5:30:f1:c6:48:5f:c3:75:6a:99:93
            # seems like status of typing, but before I make further achievement code will remain like this
             # 如果遇到特殊的连接错误，返回一个假定的状态值 '2'（这个是一个占位符，用于处理类似输入状态等情况）
            return '2'
        except:
            raise # 如果在处理错误时发生其他异常，重新抛出
    # 如果请求失败（如超时或服务器返回 4xx/5xx 错误），会抛出 HTTPError
    r.raise_for_status()
    # 使用正则表达式提取同步检查结果中的 retcode 和 selector
    regx = r'window.synccheck={retcode:"(\d+)",selector:"(\d+)"}'
    pm = re.search(regx, r.text)  # 匹配响应的内容
    # 如果没有匹配到同步检查结果，或者 retcode 不为 '0'，表示有问题
    if pm is None or pm.group(1) != '0':
        logger.error('Unexpected sync check result: %s' % r.text) # 记录错误日志，显示异常的同步检查结果
        return None # 返回 None，表示同步检查失败
    # 如果同步检查成功，返回 selector 值，表示当前消息的状态
    return pm.group(2) # 返回 selector，表示消息的类型或状态

# get_msg 函数负责从微信服务器获取同步的消息列表和联系人列表。它通过构造请求，发送到服务器并解析响应，
# 更新会话的同步状态，然后返回获取到的新增消息和修改过的联系人。
def get_msg(self):
    # 为每次请求生成一个新的 deviceid，deviceid 是一个唯一的设备标识符，通常用于标识请求来源
    self.loginInfo['deviceid'] = 'e' + repr(random.random())[2:17]
     # 构造获取消息的 URL，包含了会话 SID、Skey 和 Pass Ticket
    url = '%s/webwxsync?sid=%s&skey=%s&pass_ticket=%s' % (
        self.loginInfo['url'], self.loginInfo['wxsid'],
        self.loginInfo['skey'], self.loginInfo['pass_ticket'])
    data = { # 定义请求的内容，包括 BaseRequest（登录请求信息），SyncKey（同步信息）以及 rr（时间戳）
        'BaseRequest': self.loginInfo['BaseRequest'], # 包含登录后的请求信息
        'SyncKey': self.loginInfo['SyncKey'], # 当前的同步密钥，用于同步消息
        'rr': ~int(time.time()), } # 反转时间戳，作为请求的时间参数，确保每次请求的唯一性
    headers = { # 设置请求头，包括内容类型和 User-Agent
        'ContentType': 'application/json; charset=UTF-8', # 请求体的格式是 JSON
        'User-Agent': config.USER_AGENT}
    # 发送 POST 请求，获取消息和联系人信息
    r = self.s.post(url, data=json.dumps(data),
                    headers=headers, timeout=config.TIMEOUT)
    dic = json.loads(r.content.decode('utf-8', 'replace')) # 将响应的 JSON 数据解析成字典对象
     # 如果响应的 BaseResponse 中的 Ret 值不为 0，表示请求失败，返回 None
    if dic['BaseResponse']['Ret'] != 0:
        return None, None
    # 更新 SyncKey 和 synckey 信息，保持同步状态
    self.loginInfo['SyncKey'] = dic['SyncKey']  # 更新当前的 SyncKey
    self.loginInfo['synckey'] = '|'.join(['%s_%s' % (item['Key'], item['Val'])
                                          for item in dic['SyncCheckKey']['List']]) # 将 SyncKey 转换成特定格式的字符串
    return dic['AddMsgList'], dic['ModContactList'] # 返回新增消息列表（AddMsgList）和修改过的联系人列表（ModContactList）

def logout(self):
    # 检查当前是否处于活动状态 (self.alive 表示当前会话是否还在进行)
    if self.alive:
        url = '%s/webwxlogout' % self.loginInfo['url'] # 构造登出请求的 URL，URL 用于通知微信服务器退出当前会话
        # 构建登出的参数：
        # 'redirect': 1：表示登出后需要进行重定向，通常是重定向到登录页。
        # 'type': 1：表示登出类型，1 表示客户端登出。
        # 'skey': self.loginInfo['skey']：会话的 Skey，用于身份验证。
        params = {
            'redirect': 1,
            'type': 1,
            'skey': self.loginInfo['skey'], }
        headers = {'User-Agent': config.USER_AGENT} # 设置请求头，模拟浏览器的 User-Agent，防止请求被拦截
        self.s.get(url, params=params, headers=headers) # 发送 GET 请求通知服务器退出登录
        self.alive = False # 标记为已退出登录，关闭会话
    self.isLogging = False # 标记正在退出的状态
    self.s.cookies.clear() # 清除当前会话的所有 cookies，注销当前会话的状态
    # 清空会话相关的聊天群、成员、公众号列表
    del self.chatroomList[:] # 删除所有聊天室信息
    del self.memberList[:]  # 删除所有成员信息
    del self.mpList[:] # 删除所有公众号信息
    # 返回一个 JSON 格式的响应，表示退出成功
    return ReturnValue({'BaseResponse': {
        'ErrMsg': 'logout successfully.', # 消息，表示成功退出
        'Ret': 0, }}) # 返回码 0 表示成功
