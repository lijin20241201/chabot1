import pickle, os
import logging

import requests

from ..config import VERSION # 导入版本号常量 VERSION
from ..returnvalues import ReturnValue # 导入 ReturnValue 类，用于统一返回格式
from ..storage import templates # 导入 storage 模块中的 templates
from .contact import update_local_chatrooms, update_local_friends  # 导入更新聊天房间和朋友的函数
from .messages import produce_msg  # 导入生成消息的函数
# 获取名为 'itchat' 的日志记录器，用于输出日志
logger = logging.getLogger('itchat')
# 为core类动态绑定
def load_hotreload(core):
    core.dump_login_status = dump_login_status # 为 core 对象绑定 dump_login_status 方法
    core.load_login_status = load_login_status  # 为 core 对象绑定 load_login_status 方法
# 序列化登录状态到本地文件
def dump_login_status(self, fileDir=None):
     # 设置文件路径，若未提供路径，则使用默认的热重载目录
    fileDir = fileDir or self.hotReloadDir
    # 这里try块之内的实际上是为了 确保文件路径存在且没有其他残留文件，并为后续的文件操作（即保存状态）做准备。这一系列操作的目的是确
    # 保文件路径可用，并且如果有任何不当的临时文件残留（例如已经存在的热重载文件），就会先删除它们，避免冲突。
    try: # 打开指定路径的文件并写入 'itchat - DELETE THIS'
        with open(fileDir, 'w') as f:
            f.write('itchat - DELETE THIS')
        os.remove(fileDir) # 删除该文件
    except: # 如果发生异常，抛出错误
        raise Exception('Incorrect fileDir')
    # self.storageClass 是一个负责存储和管理用户数据（如好友列表、聊天记录等）的对象。
    status = { # 创建一个字典，保存登录信息、cookies 和存储的内容
        'version'   : VERSION, # 当前版本
        'loginInfo' : self.loginInfo,  # 登录信息
        'cookies'   : self.s.cookies.get_dict(), # 获取 cookies 字典
        'storage'   : self.storageClass.dumps()} # 获取本地存储类的序列化字典
    # 以二进制写入方式保存状态信息
    with open(fileDir, 'wb') as f:
        pickle.dump(status, f)  # 使用 pickle 序列化并写入文件
    logger.debug('Dump login status for hot reload successfully.')  # 记录日志：成功保存登录状态
# 从文件加载登录状态
def load_login_status(self, fileDir,
        loginCallback=None, exitCallback=None):
    try:
        with open(fileDir, 'rb') as f: # 尝试打开指定文件并反序列化状态数据
            j = pickle.load(f)
    except Exception as e: # 如果文件不存在或加载失败，记录日志并返回错误信息
        logger.debug('No such file, loading login status failed.')  # 日志：未找到文件，加载登录状态失败
        return ReturnValue({'BaseResponse': {
            'ErrMsg': 'No such file, loading login status failed.',
            'Ret': -1002, }}) # 返回错误代码 -1002
    # 检查缓存的版本号如果和当前不匹配
    if j.get('version', '') != VERSION:
        logger.debug(('you have updated itchat from %s to %s, ' +  # 如果版本不匹配，记录日志并返回错误信息
            'so cached status is ignored') % (
            j.get('version', 'old version'), VERSION))
        return ReturnValue({'BaseResponse': {
            'ErrMsg': 'cached status ignored because of version',
            'Ret': -1005, }})  # 返回错误代码 -1002
    self.loginInfo = j['loginInfo'] # 为core设置登录信息,用从文件加载的登录信息
    # 根据 登录信息中的用户数据，创建一个 新的User 对象
    self.loginInfo['User'] = templates.User(self.loginInfo['User']) 
    self.loginInfo['User'].core = self  # 将 core 绑定到User对象
    # 会话 cookies 是指与特定会话相关的 cookies，通常用于维持用户在一个特定会话中的身份验证、状态等信息
    self.s.cookies = requests.utils.cookiejar_from_dict(j['cookies']) 
    self.storageClass.loads(j['storage'])  # 根据文件中的来反序列化storage实例
    try:   # 尝试获取消息列表和联系人列表
        msgList, contactList = self.get_msg()
    except: # 如果获取失败，则设为 None
        msgList = contactList = None
    # 如果 msgList 或者 contactList 中有 一个是 None，那么条件就会为 True。
    if (msgList or contactList) is None:
        self.logout() # 调用 logout 方法退出登录
        load_last_login_status(self.s, j['cookies']) # 重新加载上次的登录状态
        logger.debug('server refused, loading login status failed.') # 日志：服务器拒绝，加载登录状态失败
        return ReturnValue({'BaseResponse': {
            'ErrMsg': 'server refused, loading login status failed.',
            'Ret': -1003, }})  # 返回错误代码 -1003
    else:  # 如果联系人列表存在，更新本地联系人信息
        if contactList:
            for contact in contactList:
                if '@@' in contact['UserName']:
                    update_local_chatrooms(self, [contact]) # 更新群聊信息
                else:
                    update_local_friends(self, [contact]) # 更新好友信息
        if msgList: # 如果消息列表存在，生成消息并加入消息队列
            msgList = produce_msg(self, msgList)  # 生成消息对象
            for msg in msgList: self.msgList.put(msg)   # 将消息加入消息队列
        self.start_receiving(exitCallback) # 开始接收消息并调用回调函数
        logger.debug('loading login status succeeded.')  # 日志：加载登录状态成功
        if hasattr(loginCallback, '__call__'): # 如果传入了 loginCallback 回调函数，则执行
            loginCallback()
        return ReturnValue({'BaseResponse': { # 返回成功的登录状态
            'ErrMsg': 'loading login status succeeded.',
            'Ret': 0, }}) # 返回成功代码 0
# 根据传入的 cookies 字典来恢复用户的登录状态，并且将这些 cookies 应用到 session 中
def load_last_login_status(session, cookiesDict): # 传入的是self.s,直接设置
    try:
        # 将一个普通的字典（cookiesDict）转换为 requests 可以识别的 CookieJar 对象。
        session.cookies = requests.utils.cookiejar_from_dict({
            'webwxuvid': cookiesDict['webwxuvid'], # 用于标识当前微信 Web 客户端实例
            'webwx_auth_ticket': cookiesDict['webwx_auth_ticket'], # 微信 Web 认证的 授权票据。它通常用于验证当前客户端的身份
            'login_frequency': '2', # 表示已经登录的状态。
            'last_wxuin': cookiesDict['wxuin'], # 上次登录的微信账号
            'wxloadtime': cookiesDict['wxloadtime'] + '_expired', # 用于验证客户端是否处于一个有效的会话状态
            'wxpluginkey': cookiesDict['wxloadtime'], # 微信 Web 客户端的插件密钥
            'wxuin': cookiesDict['wxuin'], # 微信用户的唯一标识符
            'mm_lang': 'zh_CN', # 设置了客户端的语言环境
            'MM_WX_NOTIFY_STATE': '1', # 微信 Web 客户端的 通知状态
            'MM_WX_SOUND_STATE': '1', }) # 微信 Web 客户端的 声音状态
    except:
        logger.info('Load status for push login failed, we may have experienced a cookies change.')
        logger.info('If you are using the newest version of itchat, you may report a bug.')
