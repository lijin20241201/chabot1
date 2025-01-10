# 从不同模块导入必要的类和函数
from .core import Core # 导入核心功能类 Core
from .config import VERSION, ASYNC_COMPONENTS  # 从配置文件中导入版本号和是否使用异步组件的标志
from .log import set_logging  # 导入设置日志功能的函数
# 根据是否使用异步组件来选择导入异步或同步的组件
if ASYNC_COMPONENTS:
    from .async_components import load_components  # 如果启用异步组件，导入异步组件的加载函数
else:
    from .components import load_components # 否则，导入同步组件的加载函数

# 设置模块的版本号
__version__ = VERSION
# 定义一个空的实例列表
instanceList = []

# 定义一个加载异步版 itchat 实例的函数
def load_async_itchat() -> Core:
    from .async_components import load_components  # 动态导入异步组件的加载函数
    load_components(Core)  # 加载异步组件
    return Core() # 返回一个 Core 实例
# 定义一个加载同步版 itchat 实例的函数
def load_sync_itchat() -> Core:
    
    from .components import load_components # 动态导入同步组件的加载函数
    load_components(Core) # 加载同步组件
    return Core() # 返回一个 Core 实例

# 根据是否启用异步组件来选择加载异步或同步的 itchat 实例
if ASYNC_COMPONENTS:
    instance = load_async_itchat()  # 加载异步版实例
else:
    instance = load_sync_itchat() # 加载同步版实例

# 将加载的 itchat 实例添加到实例列表中
instanceList = [instance]
# 以下代码是为了方便引用 instance 中的各个方法和属性,这段代码的目的是将实例对象的不同方法和属性赋值给顶级变量，
# 这样用户可以直接通过这些顶级变量访问实例方法，减少冗长的引用。
# 这段代码注释里提到作者原本想使用 `sys.modules[__name__] = originInstance` 进行模块覆盖，
# 但由于这种做法会影响自动补全功能（auto-fill），因此选择了通过直接赋值的方式来进行映射。

# 登录相关的功能方法
login                       = instance.login # 登录
get_QRuuid                  = instance.get_QRuuid # 获取二维码的 UUID
get_QR                      = instance.get_QR # 获取二维码
check_login                 = instance.check_login # 检查登录状态
web_init                    = instance.web_init # 初始化 Web 接口
show_mobile_login           = instance.show_mobile_login  # 显示手机扫码登录界面
start_receiving             = instance.start_receiving  # 开始接收消息
get_msg                     = instance.get_msg # 获取消息
logout                      = instance.logout # 注销
# 联系人相关功能方法
update_chatroom             = instance.update_chatroom # 更新聊天室
update_friend               = instance.update_friend  # 更新朋友信息
get_contact                 = instance.get_contact # 获取联系人
get_friends                 = instance.get_friends # 获取好友列表
get_chatrooms               = instance.get_chatrooms # 获取聊天室列表
get_mps                     = instance.get_mps # 获取公众号列表
set_alias                   = instance.set_alias # 设置好友备注
set_pinned                  = instance.set_pinned  # 设置好友置顶
accept_friend               = instance.accept_friend # 接受好友请求
get_head_img                = instance.get_head_img # 获取头像
create_chatroom             = instance.create_chatroom # 创建聊天室
set_chatroom_name           = instance.set_chatroom_name  # 设置聊天室名称
delete_member_from_chatroom = instance.delete_member_from_chatroom # 从聊天室删除成员
add_member_into_chatroom    = instance.add_member_into_chatroom # 向聊天室添加成员
# 消息发送和处理相关功能方法
send_raw_msg                = instance.send_raw_msg # 发送原始消息
send_msg                    = instance.send_msg # 发送消息
upload_file                 = instance.upload_file # 上传文件
send_file                   = instance.send_file # 发送文件
send_image                  = instance.send_image # 发送图片
send_video                  = instance.send_video # 发送视频
send                        = instance.send # 发送文本或其他内容
revoke                      = instance.revoke # 撤回消息
# 热重载相关功能方法
dump_login_status           = instance.dump_login_status # 转储登录状态
load_login_status           = instance.load_login_status # 加载登录状态
# 注册相关功能方法
auto_login                  = instance.auto_login  # 自动登录
configured_reply            = instance.configured_reply # 配置自动回复
msg_register                = instance.msg_register # 注册消息处理器
run                         = instance.run # 启动运行
# 其他功能
search_friends              = instance.search_friends # 搜索好友
search_chatrooms            = instance.search_chatrooms # 搜索聊天室
search_mps                  = instance.search_mps # 搜索公众号
set_logging                 = set_logging  # 设置日志
