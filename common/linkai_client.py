from bridge.context import Context, ContextType # 引入上下文相关的类
from bridge.reply import Reply, ReplyType # 引入回复相关的类
from common.log import logger # 引入日志记录器
from linkai import LinkAIClient, PushMsg # 引入LinkAI客户端及推送消息相关类
from config import conf, pconf, plugin_config, available_setting, write_plugin_config # 引入配置相关的方法
from plugins import PluginManager # 引入插件管理器
import time # 引入时间模块

chat_client: LinkAIClient # 定义全局变量chat_client，类型为LinkAIClient
# 定义ChatClient类，继承自LinkAIClient
# on_message 和 on_config 方法并不是直接由用户调用，而是由 LinkAIClient 或 ChatClient 的内部机制触发的，通常是在以下几种情况下：
# 消息到达时：当服务器推送消息时，LinkAIClient 或 ChatClient 会自动调用 on_message 方法，传入消息数据作为参数。
# 配置更新时：当服务器推送新的配置时，LinkAIClient 或 ChatClient 会自动调用 on_config 方法，传入配置数据作为参数。
class ChatClient(LinkAIClient):
    def __init__(self, api_key, host, channel):
        super().__init__(api_key, host) # 调用父类的初始化方法，传入api_key和host
        self.channel = channel # 设置channel属性
        self.client_type = channel.channel_type # 设置client_type为channel的类型
    
    # 处理接收到的消息
    def on_message(self, push_msg: PushMsg):
        session_id = push_msg.session_id # 获取会话ID
        msg_content = push_msg.msg_content # 获取回复消息内容
        logger.info(f"receive msg push, session_id={session_id}, msg_content={msg_content}") # 记录日志
        context = Context() # 创建上下文对象
        context.type = ContextType.TEXT # 设置消息类型为文本
        # 将接收者ID存储在消息上下文的kwargs里
        context["receiver"] = session_id 
        context["isgroup"] = push_msg.is_group # 设置是否为群组消息
        self.channel.send(Reply(ReplyType.TEXT, content=msg_content), context)  # 发送回复
    # config 是远程加载的配置，它可能通过某个客户端系统（可能是通过 API 调用）从外部平台获取，并传递给 on_config 方法。
    # local_config 是在内存中进行修改的，并且这些更改不会自动持久化，除非有额外的代码来处理保存操作。
    def on_config(self, config: dict):
        if not self.client_id: # 如果没有client_id，直接返回
            return
        logger.info(f"[LinkAI] 从客户端管理加载远程配置: {config}") # 记录配置加载的日志
        if config.get("enabled") != "Y":  # 如果不准备启用config配置,直接返回
            return
        local_config = conf() # 获取本地配置
        for key in config.keys():
            if key in available_setting and config.get(key) is not None: # 如果是可用配置并且配置项不为空
                local_config[key] = config.get(key) # 设置配置到本地配置中(重名覆盖)
        # 处理语音相关的配置
        reply_voice_mode = config.get("reply_voice_mode")
        if reply_voice_mode:
            if reply_voice_mode == "voice_reply_voice": # 设置语音消息模式(临时)
                local_config["voice_reply_voice"] = True
                local_config["always_reply_voice"] = False
            elif reply_voice_mode == "always_reply_voice": # 设置永久回复语音模式
                local_config["always_reply_voice"] = True
                local_config["voice_reply_voice"] = True
            elif reply_voice_mode == "no_reply_voice":  # 设置不回复语音模式
                local_config["always_reply_voice"] = False
                local_config["voice_reply_voice"] = False
        # 处理管理员密码配置
        if config.get("admin_password"):
            # 如果没有Godcmd插件配置
            if not pconf("Godcmd"): 
                write_plugin_config({"Godcmd": {"password": config.get("admin_password"), "admin_users": []} }) # 写入插件配置
            else: # 有Godcmd插件配置
                pconf("Godcmd")["password"] = config.get("admin_password") # 更新Godcmd插件的密码配置
            PluginManager().instances["GODCMD"].reload() # 重新加载Godcmd插件
        # 处理群组映射配置,config.get("group_app_map") 是一个列表
        if config.get("group_app_map") and pconf("linkai"): 
            local_group_map = {} 
            for mapping in config.get("group_app_map"): # 遍历群组映射
                local_group_map[mapping.get("group_name")] = mapping.get("app_code") # 添加群组和app的映射
            pconf("linkai")["group_app_map"] = local_group_map # 更新linkai插件配置中的群组映射为上面获取的映射
            PluginManager().instances["LINKAI"].reload() # 重新加载LinkAI插件
        # 这部分的配置处理了与文本图像生成相关的功能，主要涉及清晰图像生成方式：midjourney、dall-e-2、`dalldall-e-3。
        # 这表示如果配置中指定的text_to_image是midjourney，则启用与midjourney相关的配置
        if config.get("text_to_image") and config.get("text_to_image") == "midjourney" and pconf("linkai"):
            if pconf("linkai")["midjourney"]:
                pconf("linkai")["midjourney"]["enabled"] = True # 启用midjourney生成图像
                pconf("linkai")["midjourney"]["use_image_create_prefix"] = True # 使用图像生成前缀
        # 如果在使用 DALL·E 时关闭 MidJourney，应该确保将 midjourney["enabled"] 设置为 False，这样 MidJourney 就不会干扰 DALL·E 的生成过程。
        elif config.get("text_to_image") and config.get("text_to_image") in ["dall-e-2", "dall-e-3"]:
            if pconf("linkai")["midjourney"]:
                pconf("linkai")["midjourney"]["use_image_create_prefix"] = False 

# 启动聊天客户端
def start(channel):
    global chat_client # 使用全局变量chat_client
    chat_client = ChatClient(api_key=conf().get("linkai_api_key"), host="", channel=channel) # 创建ChatClient实例
    chat_client.config = _build_config()  # 设置配置
    chat_client.start()  # 启动客户端
    time.sleep(1.5) # 等待1.5秒
    if chat_client.client_id: # 如果client_id存在
        logger.info("[LinkAI] 可前往控制台进行线上登录和配置：https://link-ai.tech/console/clients") # 记录控制台登录提示信息

# 构建配置字典
def _build_config():
    local_conf = conf() # 获取本地配置
    config = {
        # 这个字段通常是由 LinkAI 系统分配的应用标识符，客户端需要通过这个 app_code 与服务器进行通信。
        "linkai_app_code": local_conf.get("linkai_app_code"), 
        "single_chat_prefix": local_conf.get("single_chat_prefix"), # 获取单聊消息的前缀。
        "single_chat_reply_prefix": local_conf.get("single_chat_reply_prefix"), # 获取单人聊天回复的前缀。
        "single_chat_reply_suffix": local_conf.get("single_chat_reply_suffix"), # 获取单人聊天回复的后缀。
        "group_chat_prefix": local_conf.get("group_chat_prefix"), # 获取群聊消息的前缀。
        "group_chat_reply_prefix": local_conf.get("group_chat_reply_prefix"), # 获取群聊回复的前缀。
        "group_chat_reply_suffix": local_conf.get("group_chat_reply_suffix"), # 获取群聊回复的后缀。
        "group_name_white_list": local_conf.get("group_name_white_list"),#  用于限制哪些群组可以使用此功能，只有在白名单中的群组才会启用某些特性。
        "nick_name_black_list": local_conf.get("nick_name_black_list"), # 用于排除某些用户（基于昵称），这些用户的消息或请求可能不会被处理。
        "speech_recognition": "Y" if local_conf.get("speech_recognition") else "N", # 设置语音识别配置
        "text_to_image": local_conf.get("text_to_image"), # 指定是否启用文本转图片功能，可能会用到像 MidJourney、DALL·E 之类的服务。
        "image_create_prefix": local_conf.get("image_create_prefix") # 获取图片生成的前缀。
    }
    if local_conf.get("always_reply_voice"):
        config["reply_voice_mode"] = "always_reply_voice"
    elif local_conf.get("voice_reply_voice"):
        config["reply_voice_mode"] = "voice_reply_voice"
    if pconf("linkai"):
        config["group_app_map"] = pconf("linkai").get("group_app_map")  # 设置group_app_map配置
    if plugin_config.get("Godcmd"):
        config["admin_password"] = plugin_config.get("Godcmd").get("password") # 设置admin_password配置
    return config # 返回构建的配置字典
