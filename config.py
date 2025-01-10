# encoding:utf-8
import json
import logging
import os
import pickle # 用于序列化和反序列化 Python 对象
import copy
import ast
from common.log import logger

# 将所有可用的配置项写在字典里,此处的配置值无实际意义，程序不会读取此处的配置，仅用于提示格式(有哪些键)，请将配置加入到config.json中
available_setting = {
    # openai api配置
    "open_ai_api_key": "",  # openai api key
    # openai apibase，当use_azure_chatgpt为true时，需要设置对应的api base
    "open_ai_api_base": "https://api.openai.com/v1",
    "proxy": "",  # openai使用的代理
    # chatgpt模型， 当use_azure_chatgpt为true时，其名称为Azure上model deployment名称
    "model": "gpt-3.5-turbo",  # 可选择: gpt-4o, pt-4o-mini, gpt-4-turbo, claude-3-sonnet, wenxin, moonshot, qwen-turbo, xunfei, glm-4, minimax, gemini等模型，全部可选模型详见common/const.py文件
    "bot_type": "",  # 可选配置，使用兼容openai格式的三方服务时候，需填"chatGPT"。bot具体名称详见common/const.py文件列出的bot_type，如不填根据model名称判断，
    "use_azure_chatgpt": False,  # 是否使用azure的chatgpt
    "azure_deployment_id": "",  # azure 模型部署名称
    "azure_api_version": "",  # azure api版本
    # Bot触发配置
    "single_chat_prefix": ["bot", "@bot"],  # 私聊时文本需要包含该前缀才能触发机器人回复
    "single_chat_reply_prefix": "[bot] ",  # 私聊时自动回复的前缀，用于区分真人
    "single_chat_reply_suffix": "",  # 私聊时自动回复的后缀，\n 可以换行
    "group_chat_prefix": ["@bot"],  # 群聊时包含该前缀则会触发机器人回复
    "no_need_at": False,  # 群聊回复时是否不需要艾特
    "group_chat_reply_prefix": "",  # 群聊时自动回复的前缀
    "group_chat_reply_suffix": "",  # 群聊时自动回复的后缀，\n 可以换行
    "group_chat_keyword": [],  # 群聊时包含该关键词则会触发机器人回复
    "group_at_off": False,  # 是否关闭群聊时@bot的触发
    "group_name_white_list": ["ChatGPT测试群", "ChatGPT测试群2"],  # 开启自动回复的群名称列表
    "group_name_keyword_white_list": [],  # 开启自动回复的群名称关键词列表
    "group_chat_in_one_session": ["ChatGPT测试群"],  # 支持会话上下文共享的群名称
    "nick_name_black_list": [],  # 用户昵称黑名单
    "group_welcome_msg": "",  # 配置新人进群固定欢迎语，不配置则使用随机风格欢迎
    "trigger_by_self": False,  # 是否允许机器人触发
    "text_to_image": "dall-e-2",  # 图片生成模型，可选 dall-e-2, dall-e-3
    # Azure OpenAI dall-e-3 配置
    "dalle3_image_style": "vivid", # 图片生成dalle3的风格，可选有 vivid, natural
    "dalle3_image_quality": "hd", # 图片生成dalle3的质量，可选有 standard, hd
    # Azure OpenAI DALL-E API 配置, 当use_azure_chatgpt为true时,用于将文字回复的资源和Dall-E的资源分开.
    "azure_openai_dalle_api_base": "", # [可选] azure openai 用于回复图片的资源 endpoint，默认使用 open_ai_api_base
    "azure_openai_dalle_api_key": "", # [可选] azure openai 用于回复图片的资源 key，默认使用 open_ai_api_key
    "azure_openai_dalle_deployment_id":"", # [可选] azure openai 用于回复图片的资源 deployment id，默认使用 text_to_image
    "image_proxy": True,  # 是否需要图片代理，国内访问LinkAI时需要
    "image_create_prefix": ["画", "看", "找"],  # 开启图片回复的前缀
    "concurrency_in_session": 1,  # 同一会话最多有多少条消息在处理中，大于1可能乱序
    "image_create_size": "256x256",  # 图片大小,可选有 256x256, 512x512, 1024x1024 (dall-e-3默认为1024x1024)
    "group_chat_exit_group": False,
    # chatgpt会话参数
    "expires_in_seconds": 3600,  # 无操作会话的过期时间
    # 人格描述
    "character_desc": "你是ChatGPT, 一个由OpenAI训练的大型语言模型, 你旨在回答并解决人们的任何问题，并且可以使用多种语言与人交流。",
    "conversation_max_tokens": 1000,  # 支持上下文记忆的最多字符数
    # chatgpt限流配置
    "rate_limit_chatgpt": 20,  # chatgpt的调用频率限制
    "rate_limit_dalle": 50,  # openai dalle的调用频率限制
    # chatgpt api参数 参考https://platform.openai.com/docs/api-reference/chat/create
    "temperature": 0.9,
    "top_p": 1,
    "frequency_penalty": 0,
    "presence_penalty": 0,
    "request_timeout": 180,  # chatgpt请求超时时间，openai接口默认设置为600，对于难问题一般需要较长时间
    "timeout": 120,  # chatgpt重试超时时间，在这个时间内，将会自动重试
    # Baidu 文心一言参数
    "baidu_wenxin_model": "eb-instant",  # 默认使用ERNIE-Bot-turbo模型
    "baidu_wenxin_api_key": "",  # Baidu api key
    "baidu_wenxin_secret_key": "",  # Baidu secret key
    "baidu_wenxin_prompt_enabled": False,  # Enable prompt if you are using ernie character model
    # 讯飞星火API
    "xunfei_app_id": "",  # 讯飞应用ID
    "xunfei_api_key": "",  # 讯飞 API key
    "xunfei_api_secret": "",  # 讯飞 API secret
    "xunfei_domain": "",  # 讯飞模型对应的domain参数，Spark4.0 Ultra为 4.0Ultra，其他模型详见: https://www.xfyun.cn/doc/spark/Web.html
    "xunfei_spark_url": "",  # 讯飞模型对应的请求地址，Spark4.0 Ultra为 wss://spark-api.xf-yun.com/v4.0/chat，其他模型参考详见: https://www.xfyun.cn/doc/spark/Web.html
    # claude 配置
    "claude_api_cookie": "",
    "claude_uuid": "",
    # claude api key
    "claude_api_key": "",
    # 通义千问API, 获取方式查看文档 https://help.aliyun.com/document_detail/2587494.html
    "qwen_access_key_id": "",
    "qwen_access_key_secret": "",
    "qwen_agent_key": "",
    "qwen_app_id": "",
    "qwen_node_id": "",  # 流程编排模型用到的id，如果没有用到qwen_node_id，请务必保持为空字符串
    # 阿里灵积(通义新版sdk)模型api key
    "dashscope_api_key": "",
    # Google Gemini Api Key
    "gemini_api_key": "",
    # wework的通用配置
    "wework_smart": True,  # 配置wework是否使用已登录的企业微信，False为多开
    # 语音设置
    "speech_recognition": True,  # 是否开启语音识别
    "group_speech_recognition": False,  # 是否开启群组语音识别
    "voice_reply_voice": False,  # 是否使用语音回复语音，需要设置对应语音合成引擎的api key
    "always_reply_voice": False,  # 是否一直使用语音回复
    "voice_to_text": "openai",  # 语音识别引擎，支持openai,baidu,google,azure,xunfei,ali
    "text_to_voice": "openai",  # 语音合成引擎，支持openai,baidu,google,azure,xunfei,ali,pytts(offline),elevenlabs,edge(online)
    "text_to_voice_model": "tts-1",
    "tts_voice_id": "alloy",
    # baidu 语音api配置， 使用百度语音识别和语音合成时需要
    "baidu_app_id": "",
    "baidu_api_key": "",
    "baidu_secret_key": "",
    # 1536普通话(支持简单的英文识别) 1737英语 1637粤语 1837四川话 1936普通话远场
    "baidu_dev_pid": 1536,
    # azure 语音api配置， 使用azure语音识别和语音合成时需要
    "azure_voice_api_key": "",
    "azure_voice_region": "japaneast",
    # elevenlabs 语音api配置
    "xi_api_key": "",  # 获取ap的方法可以参考https://docs.elevenlabs.io/api-reference/quick-start/authentication
    "xi_voice_id": "",  # ElevenLabs提供了9种英式、美式等英语发音id，分别是“Adam/Antoni/Arnold/Bella/Domi/Elli/Josh/Rachel/Sam”
    # 服务时间限制，目前支持itchat
    "chat_time_module": False,  # 是否开启服务时间限制
    "chat_start_time": "00:00",  # 服务开始时间
    "chat_stop_time": "24:00",  # 服务结束时间
    # 翻译api
    "translate": "baidu",  # 翻译api，支持baidu
    # baidu翻译api的配置
    "baidu_translate_app_id": "",  # 百度翻译api的appid
    "baidu_translate_app_key": "",  # 百度翻译api的秘钥
    # itchat的配置
    "hot_reload": False,  # 是否开启热重载
    # wechaty的配置
    "wechaty_puppet_service_token": "",  # wechaty的token
    # wechatmp的配置
    "wechatmp_token": "",  # 微信公众平台的Token
    "wechatmp_port": 8080,  # 微信公众平台的端口,需要端口转发到80或443
    "wechatmp_app_id": "",  # 微信公众平台的appID
    "wechatmp_app_secret": "",  # 微信公众平台的appsecret
    "wechatmp_aes_key": "",  # 微信公众平台的EncodingAESKey，加密模式需要
    # wechatcom的通用配置
    "wechatcom_corp_id": "",  # 企业微信公司的corpID
    # wechatcomapp的配置
    "wechatcomapp_token": "",  # 企业微信app的token
    "wechatcomapp_port": 9898,  # 企业微信app的服务端口,不需要端口转发
    "wechatcomapp_secret": "",  # 企业微信app的secret
    "wechatcomapp_agent_id": "",  # 企业微信app的agent_id
    "wechatcomapp_aes_key": "",  # 企业微信app的aes_key
    # 飞书配置
    "feishu_port": 80,  # 飞书bot监听端口
    "feishu_app_id": "",  # 飞书机器人应用APP Id
    "feishu_app_secret": "",  # 飞书机器人APP secret
    "feishu_token": "",  # 飞书 verification token
    "feishu_bot_name": "",  # 飞书机器人的名字
    # 钉钉配置
    "dingtalk_client_id": "",  # 钉钉机器人Client ID 
    "dingtalk_client_secret": "",  # 钉钉机器人Client Secret
    "dingtalk_card_enabled": False,
    
    # chatgpt指令自定义触发词
    "clear_memory_commands": ["#清除记忆"],  # 重置会话指令，必须以#开头
    # channel配置
    "channel_type": "",  # 通道类型，支持：{wx,wxy,terminal,wechatmp,wechatmp_service,wechatcom_app,dingtalk}
    "subscribe_msg": "",  # 订阅消息, 支持: wechatmp, wechatmp_service, wechatcom_app
    "debug": False,  # 是否开启debug模式，开启后会打印更多日志
    "appdata_dir": "",  # 数据目录
    # 插件配置
    "plugin_trigger_prefix": "$",  # 规范插件提供聊天相关指令的前缀，建议不要和管理员指令前缀"#"冲突
    # 是否使用全局插件配置
    "use_global_plugin_config": False,
    "max_media_send_count": 3,  # 单次最大发送媒体资源的个数
    "media_send_interval": 1,  # 发送图片的事件间隔，单位秒
    # 智谱AI 平台配置
    "zhipu_ai_api_key": "",
    "zhipu_ai_api_base": "https://open.bigmodel.cn/api/paas/v4",
    "moonshot_api_key": "",
    "moonshot_base_url": "https://api.moonshot.cn/v1/chat/completions",
    # LinkAI平台配置
    "use_linkai": False,
    "linkai_api_key": "",
    "linkai_app_code": "",
    "linkai_api_base": "https://api.link-ai.tech",  # linkAI服务地址
    "Minimax_api_key": "",
    "Minimax_group_id": "",
    "Minimax_base_url": "",
    "web_port": 9899,
}

# 用来保存config.json中配置和用户数据的配置类
class Config(dict):
    def __init__(self, d=None):
        super().__init__()
        if d is None:
            d = {}
        for k, v in d.items():
            self[k] = v
        # user_datas: 用户数据，key为用户名，value为用户数据，也是dict
        self.user_datas = {}
    # 当调用self[key]时默认访问这个魔法方法
    def __getitem__(self, key):
        if key not in available_setting:
            raise Exception("key {} not in available_setting".format(key))
        return super().__getitem__(key)
    # 当调用self[k] = v时默认访问这个魔法方法
    def __setitem__(self, key, value):
        if key not in available_setting:
            raise Exception("key {} not in available_setting".format(key))
        return super().__setitem__(key, value)
    # 返回键对应的值
    def get(self, key, default=None):
        try:
            return self[key] # 访问这个会调用魔法方法__getitem__
        except KeyError as e: # 如果 __getitem__ 方法没有找到指定的键，它就会抛出 KeyError 异常。
            return default
        except Exception as e:
            raise e

    # 确保返回一个字典以保证原子性,如果你在一个并发环境中操作共享数据，并且希望这些操作是原子性的（
    # 即要么全部完成，要么完全不执行，不会出现部分完成的状态），那么可以考虑使用特定的数据结构或机制来实现这一点。
    def get_user_data(self, user) -> dict:
        if self.user_datas.get(user) is None: # 如果从字典中没获取用户数据
            self.user_datas[user] = {} # 设置对应值是空字典
        return self.user_datas[user] # 返回用户数据
    # 加载用户数据
    def load_user_datas(self):
        try:
            with open(os.path.join(get_appdata_dir(), "user_datas.pkl"), "rb") as f:
                self.user_datas = pickle.load(f)
                logger.info("[Config] User datas loaded.")
        except FileNotFoundError as e:
            logger.info("[Config] User datas file not found, ignore.")
        except Exception as e:
            logger.info("[Config] User datas error: {}".format(e))
            self.user_datas = {}
    # 保存用户数据到文件
    def save_user_datas(self):
        try:
            with open(os.path.join(get_appdata_dir(), "user_datas.pkl"), "wb") as f:
                pickle.dump(self.user_datas, f) # 将字典对象序列化为字节流，并将其写入文件 f。
                logger.info("[Config] User datas saved.")
        except Exception as e:
            logger.info("[Config] User datas error: {}".format(e))

# 这个在应用启动时,因为会调用load_config,所以那时候已经加载config.json中的配置
config = Config()

# 对需要加密的数据进行加密
def drag_sensitive(config):
    try:
        if isinstance(config, str):  # 检查传入的 config 是否为字符串。
            conf_dict: dict = json.loads(config) # 把json字符串转换成Python字典。
            conf_dict_copy = copy.deepcopy(conf_dict) # 创建原始配置字典的深拷贝，以避免直接修改原始数据。
            # 遍历并处理敏感信息
            # 遍历字典中的所有键，并检查键名是否包含 "key" 或 "secret"。
            for key in conf_dict_copy:
                if "key" in key or "secret" in key:  # 如果是密码
                    # 对于符合条件的键，检查其值是否为字符串。如果是，则将值的部分字符替换为星号（*），仅保留前三位和后三位字符。
                    if isinstance(conf_dict_copy[key], str):
                        conf_dict_copy[key] = conf_dict_copy[key][0:3] + "*" * 5 + conf_dict_copy[key][-3:]
            return json.dumps(conf_dict_copy, indent=4) # 返回处理后的 JSON 字符串,并使用缩进格式化输出。

        elif isinstance(config, dict): # 处理字典类型的配置
            # 如果传入的 config 已经是字典类型，则直接对其进行深拷贝和敏感信息处理。
            config_copy = copy.deepcopy(config)
            for key in config:
                if "key" in key or "secret" in key:
                    if isinstance(config_copy[key], str):
                        config_copy[key] = config_copy[key][0:3] + "*" * 5 + config_copy[key][-3:]
            return config_copy # 返回字典
    except Exception as e: # 捕获任何可能发生的异常，并记录详细的错误信息到日志中。
        logger.exception(e)
        return config

def load_config(): 
    global config # 声明将使用全局变量 config
    config_path = "./config.json"
    if not os.path.exists(config_path):
        logger.info("配置文件不存在，将使用config-template.json模板")
        config_path = "./config-template.json"
    # 读取config_path下文件的配置
    config_str = read_file(config_path)
    logger.debug("[INIT] config str: {}".format(drag_sensitive(config_str))) # 输出加密的字符串
    # 将配置json字符串变成字典,之后构建Config实例
    config = Config(json.loads(config_str))
    # 使用环境变量覆盖之前的配置。
    # 一些在线部署平台（例如 Railway）直接从 GitHub 部署项目。因此，你不应该将诸如 API 密钥之类的敏感信息放在配置文件中，而是使
    # 用环境变量来覆盖默认配置。
    # 部署时使用模板并临时或动态地填充敏感信息是一种常见的做法。这种方式确保了敏感信息（如 API 密钥、数据库密码等）不会被硬编码在代码仓
    # 库中，同时允许你在不同环境中灵活配置这些信息。
    for name, value in os.environ.items():
        name = name.lower() # 转换成小写
        if name in available_setting:
            logger.info("[INIT] override config by environ args: {}={}".format(name, value))
            # try:
            #     config[name] = eval(value)
            # except:
            #     if value == "false":
            #         config[name] = False
            #     elif value == "true":
            #         config[name] = True
            #     else:
            #         config[name] = value
            try:
                config[name]=ast.literal_eval(value) # 更安全 
            except:
                if value == "false":
                    config[name] = False
                elif value == "true":
                    config[name] = True
                else:
                    config[name] = value # 设置键值对到Config实例中
                    logger.warning(f"Failed to literal_eval value for key '{name}': {value}.")
    if config.get("debug", False): # 如果设置要启用debug模式
        logger.setLevel(logging.DEBUG)
        logger.debug("[INIT] set log level to DEBUG")

    logger.info("[INIT] load config: {}".format(drag_sensitive(config)))  # 加密显示信息

    config.load_user_datas() # 从指定文件加载用户数据

# __file__ 包含了当前脚本的完整路径（绝对路径或相对路径，取决于如何启动脚本）
def get_root():
    return os.path.dirname(os.path.abspath(__file__))


def read_file(path): # 读取文件
    with open(path, mode="r", encoding="utf-8") as f:
        return f.read()


def conf():
    return config

# 获取用户数据的目录
def get_appdata_dir():
    data_path = os.path.join(get_root(), conf().get("appdata_dir", ""))
    if not os.path.exists(data_path):
        logger.info("[INIT] data path not exists, create it: {}".format(data_path))
        os.makedirs(data_path)
    return data_path

# 发送订阅或欢迎消息给新用户，介绍可用的功能并引导他们开始使用
def subscribe_msg():
    trigger_prefix = conf().get("single_chat_prefix", [""])[0]
    msg = conf().get("subscribe_msg", "") # 获取配置中的机器人介绍
    return msg.format(trigger_prefix=trigger_prefix)


# 全局的插件配置
plugin_config = {}
def write_plugin_config(pconf: dict):
    """
    写入插件全局配置
    :param pconf: 全量插件配置
    """
    global plugin_config
    for k in pconf:
        plugin_config[k.lower()] = pconf[k]

def remove_plugin_config(name: str):
    """
    移除待重新加载的插件配置
    :param name: 待重载的插件名
    """
    global plugin_config
    # None 是你希望在字典中没有该键时返回的默认值。如果不提供第二个参数，pop() 在键不存在时会引发一个 KeyError 异常。
    # 通过提供默认值 None，能够避免 KeyError 异常，并让代码更加健壮
    plugin_config.pop(name.lower(), None)


def pconf(plugin_name: str) -> dict:
    """
    根据插件名称获取配置
    :param plugin_name: 插件名称
    :return: 该插件的配置项
    """
    return plugin_config.get(plugin_name.lower())


# 全局配置，用于存放全局生效的状态
global_config = {"admin_users": []}
