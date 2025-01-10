import re, os, sys, subprocess, copy, traceback, logging
# 处理HTML标签的解析，兼容Python2和3
# 尝试导入HTMLParser用于处理HTML标签解析。HTMLParser用于解码HTML实体字符。
try:
    from HTMLParser import HTMLParser # Python2 中的模块
except ImportError:
    from html.parser import HTMLParser # Python3 中的模块
# 引入URL编码方法
# 根据Python版本选择导入不同的quote方法来进行URL编码。
try:
    from urllib import quote as _quote  # Python2中的URL编码方法
    quote = lambda n: _quote(n.encode('utf8', 'replace')) # 使用UTF-8编码进行URL编码
except ImportError:
    from urllib.parse import quote # Python3中的URL编码方法
# 导入requests库，用于发送HTTP请求
import requests
from . import config # 导入自定义的config配置模块
# 日志记录器
# 初始化一个名为'itchat'的日志记录器，用于日志记录
logger = logging.getLogger('itchat')
# 处理表情符号的正则表达式
# 使用正则表达式来匹配HTML中的表情符号<span class="emoji emoji..."></span>
emojiRegex = re.compile(r'<span class="emoji emoji(.{1,10})"></span>')
htmlParser = HTMLParser() # 创建HTMLParser对象，用于解析HTML实体字符
# 对于Python 3.9及以上版本，HTMLParser不再支持unescape方法，所以使用html模块的unescape方法
if not hasattr(htmlParser, 'unescape'):
    import html
    htmlParser.unescape = html.unescape  # 如果没有unescape方法，则使用html模块提供的unescape方法
    # FIX Python 3.9 HTMLParser.unescape is removed. See https://docs.python.org/3.9/whatsnew/3.9.html
# 尝试输出方块字符，处理不同操作系统的字符编码问题
# 该段代码尝试输出一个Unicode方块字符，并根据不同操作系统处理字符编码问题
try:
    b = u'\u2588' # 定义一个Unicode方块字符
    sys.stdout.write(b + '\r')  # 将方块字符输出到标准输出
    sys.stdout.flush() # 刷新输出
except UnicodeEncodeError:
    BLOCK = 'MM'  # 如果输出失败，使用'MM'作为替代
else:  # 如果成功，使用方块字符
    BLOCK = b
# 定义好友信息模板，包含用户基本信息和其他字段,创建一个字典，模板包含好友信息的各个字段
friendInfoTemplate = {}
# 为好友信息字段初始化默认值，部分字段为字符串类型，部分为整型
for k in ('UserName', 'City', 'DisplayName', 'PYQuanPin', 'RemarkPYInitial', 'Province',
        'KeyWord', 'RemarkName', 'PYInitial', 'EncryChatRoomId', 'Alias', 'Signature', 
        'NickName', 'RemarkPYQuanPin', 'HeadImgUrl'):
    friendInfoTemplate[k] = '' # 字符串类型的字段默认为空字符串
for k in ('UniFriend', 'Sex', 'AppAccountFlag', 'VerifyFlag', 'ChatRoomId', 'HideInputBarFlag',
        'AttrStatus', 'SnsFlag', 'MemberCount', 'OwnerUin', 'ContactFlag', 'Uin',
        'StarFriend', 'Statues'):
    friendInfoTemplate[k] = 0 # 整型字段默认为0
friendInfoTemplate['MemberList'] = [] # 会员列表，默认为空列表
# 清空终端屏幕,根据不同操作系统执行清屏操作
def clear_screen():
    os.system('cls' if config.OS == 'Windows' else 'clear') # 如果是Windows系统使用'cls'命令，其他系统使用'clear'
# 格式化表情符号的函数,该函数用于将表情符号的HTML标签转换为实际可显示的表情符号
def emoji_formatter(d, k):
    # _emoji_deebugger 用于处理一些微信后台可能导致的表情符号匹配问题
    def _emoji_debugger(d, k):
         # 处理一些表情符号显示问题，修复有时可能缺少闭合标签的表情符号
        s = d[k].replace('<span class="emoji emoji1f450"></span',
            '<span class="emoji emoji1f450"></span>') # 修复表情符号显示错误
        # 修复不匹配的表情符号，将错误的表情符号替换为正确的
        def __fix_miss_match(m):
            return '<span class="emoji emoji%s"></span>' % ({
                '1f63c': '1f601', '1f639': '1f602', '1f63a': '1f603',
                '1f4ab': '1f616', '1f64d': '1f614', '1f63b': '1f60d',
                '1f63d': '1f618', '1f64e': '1f621', '1f63f': '1f622',
                }.get(m.group(1), m.group(1)))  # 用正确的表情符号代码替换错误的
        return emojiRegex.sub(__fix_miss_match, s) # 应用修复表情符号的正则替换
    def _emoji_formatter(m):
        s = m.group(1) # 将表情符号的Unicode编码转换为实际的表情符号字符
        # 将表情符号的Unicode转换为可显示的格式
        if len(s) == 6:
            return ('\\U%s\\U%s'%(s[:2].rjust(8, '0'), s[2:].rjust(8, '0'))
                ).encode('utf8').decode('unicode-escape', 'replace') # 转换为Unicode格式并显示
        elif len(s) == 10:
            return ('\\U%s\\U%s'%(s[:5].rjust(8, '0'), s[5:].rjust(8, '0'))
                ).encode('utf8').decode('unicode-escape', 'replace')
        else:
            return ('\\U%s'%m.group(1).rjust(8, '0')
                ).encode('utf8').decode('unicode-escape', 'replace')
    d[k] = _emoji_debugger(d, k) # 先修复表情符号
    d[k] = emojiRegex.sub(_emoji_formatter, d[k])  # 然后格式化表情符号
# 格式化消息内容，处理表情符号和HTML标签
# 该函数用于格式化消息内容，将HTML标签和表情符号转换为实际显示的内容
def msg_formatter(d, k):
    emoji_formatter(d, k) # 处理表情符号
    d[k] = d[k].replace('<br/>', '\n') # 将HTML的换行标签<br/>替换为实际的换行符
    d[k] = htmlParser.unescape(d[k])   # 解码HTML实体字符（如&lt;转为<）
# 检查文件是否存在,该函数用于检查指定路径的文件是否存在
def check_file(fileDir):
    try:
        with open(fileDir): # 尝试打开文件
            pass
        return True # 如果文件存在，返回True
    except:
        return False # 如果发生异常（如文件不存在），返回False
# 该函数根据操作系统类型调用不同的命令来打开二维码图片,根据操作系统类型（macOS、Linux、Windows）使用不同的命令打开二维码文件
def print_qr(fileDir):
    # 它使用了 subprocess 模块的 call() 方法来执行系统命令 open，并传递文件路径 fileDir 作为参数。
    if config.OS == 'Darwin':  # 表示当前操作系统是 macOS（苹果的操作系统）
        subprocess.call(['open', fileDir]) # MacOS：使用 open 命令打开文件。
    elif config.OS == 'Linux':
        subprocess.call(['xdg-open', fileDir])   # Linux：使用 xdg-open 命令打开文件。
    else: # Windows 使用 `startfile` 命令打开文件
        os.startfile(fileDir) 
# 打印命令行二维码
def print_cmd_qr(qrText, white=BLOCK, black='  ', enableCmdQR=True):
    blockCount = int(enableCmdQR)  # 控制是否启用命令行二维码，1表示启用，0表示不启用
    if abs(blockCount) == 0:
        blockCount = 1 # 如果 blockCount 为 0（即二维码未启用），则 blockCount 被重新设置为 1，确保至少绘制一个块（默认行为）。
    white *= abs(blockCount) # 根据 blockCount 调整白色块的大小
    if blockCount < 0:
        white, black = black, white  # 如果 blockCount 为负，交换黑白块颜色
    sys.stdout.write(' '*50 + '\r')  # 清除当前行内容
    sys.stdout.flush() # 刷新输出缓冲区
    qr = qrText.replace('0', white).replace('1', black)  # 根据 qrText 替换 '0' 和 '1' 为相应的块字符
    sys.stdout.write(qr) # 打印生成的二维码文本
    sys.stdout.flush()  # 刷新输出缓冲区
# 构建好友信息字典
def struct_friend_info(knownInfo):
    member = copy.deepcopy(friendInfoTemplate) # 复制模板，避免直接修改原始模板
    for k, v in copy.deepcopy(knownInfo).items(): member[k] = v # 将 knownInfo 中的键值对更新到 member 字典
    return member  # 返回更新后的字典
# 在字典列表中查找特定键值对
def search_dict_list(l, key, value):
    for i in l:  # 遍历字典列表
        if i.get(key) == value: 
            return i  # 返回匹配的项
# 打印一行消息
def print_line(msg, oneLine = False):
    if oneLine:
        # ' '*40：表示生成一个包含40个空格的字符串。
        # + '\r'：这是将 '\r'（回车符）追加到空格字符串的末尾。回车符 \r 会将光标移动到当前行的开头，但不会换行。它的作用是将
        # 光标放回行首，使后续输出的内容覆盖当前行的内容。
        sys.stdout.write(' '*40 + '\r')
        sys.stdout.flush()
    else:  # 如果不在一行,打印换行
        sys.stdout.write('\n')
    sys.stdout.write(msg.encode(sys.stdin.encoding or 'utf8', 'replace'
        ).decode(sys.stdin.encoding or 'utf8', 'replace')) # 打印消息，并确保字符编码兼容
    sys.stdout.flush() # 刷新输出缓冲区
# 测试网络连接
def test_connect(retryTime=5):
    for i in range(retryTime):  # 尝试连接指定次数
        try:
            r = requests.get(config.BASE_URL)  # 发起 GET 请求
            return True  # 成功则返回 True
        except:  # 如果尝试达到最大次数，记录异常
            if i == retryTime - 1: # 达到一定次数,会是0
                logger.error(traceback.format_exc()) # 打印异常信息
                return False # 返回 False 表示连接失败
# 深拷贝 contact 对象，并确保线程安全
def contact_deep_copy(core, contact):
    with core.storageClass.updateLock: # 锁定共享资源，确保线程安全
        return copy.deepcopy(contact)  # 深拷贝 contact 对象
# 根据图像数据的前几个字节识别图像格式
def get_image_postfix(data): 
    data = data[:20]  # 获取前20个字节
    if b'GIF' in data:  # 检测到 GIF 格式
        return 'gif'
    elif b'PNG' in data: # 检测到 PNG 格式
        return 'png'
    elif b'JFIF' in data:  # 检测到 JPG 格式
        return 'jpg'
    return '' # 如果不匹配任何已知格式，则返回空字符串
# 更新字典，只更新有效值，避免空值或无效值更新
def update_info_dict(oldInfoDict, newInfoDict):
    # 更新信息字典，只允许有效的、非空的值进行更新。
    for k, v in newInfoDict.items():  # 遍历新字典中的每个键值对
        if any((isinstance(v, t) for t in (tuple, list, dict))):  # 如果新值是列表、元组或字典，跳过更新
            pass 
        elif oldInfoDict.get(k) is None or v not in (None, '', '0', 0): # 如果旧字典中该键值为 None 或无效值，则更新
            oldInfoDict[k] = v # 更新字典中的值