# -*- coding=utf-8 -*-
import uuid # 导入uuid模块，用于生成唯一标识符
import requests
import web # 导入web模块，用于Web应用的开发
from channel.feishu.feishu_message import FeishuMessage # 从feishu_message模块导入FeishuMessage类
from bridge.context import Context
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.singleton import singleton
from config import conf
from common.expired_dict import ExpiredDict
from bridge.context import ContextType
from channel.chat_channel import ChatChannel, check_prefix
from common import utils
import json
import os
URL_VERIFICATION = "url_verification"  # 网址验证
@singleton # 使用singleton装饰器，确保类只有一个实例
class FeiShuChanel(ChatChannel):
    feishu_app_id = conf().get('feishu_app_id')  # 从配置中获取FeiShu应用的ID
    feishu_app_secret = conf().get('feishu_app_secret')  # 从配置中获取FeiShu应用的密钥
    feishu_token = conf().get('feishu_token') # 从配置中获取FeiShu的token
    def __init__(self): # 初始化方法
        super().__init__()  # 调用父类的初始化方法
        # 创建一个有效期为7.1小时的字典，用于存储收到的消息id
        self.receivedMsgs = ExpiredDict(60 * 60 * 7.1)
        logger.info("[FeiShu] app_id={}, app_secret={} verification_token={}".format(
            self.feishu_app_id, self.feishu_app_secret, self.feishu_token)) # 记录FeiShu应用的配置信息
        # 设置任何群都会被机器人应用处理和单聊前缀
        conf()["group_name_white_list"] = ["ALL_GROUP"]
        conf()["single_chat_prefix"] = [""]

    def startup(self): # 启动方法
        # 这行代码定义了 URL 路由映射将 URL / 映射到 channel.feishu.feishu_channel.FeishuController 这个类。
        # 也就是说，所有请求到达 / 路径时，会由 FeishuController 类来处理。
        # FeishuController 是一个自定义的类，它负责处理来自飞书应用的推送消息，比如事件或请求。
        urls = (
            '/', 'channel.feishu.feishu_channel.FeishuController'
        ) 
        # web.application 是 Web.py 框架中创建应用的核心方法，它会生成一个 Web 应用实例。这个实例会根据你定义的路由（urls）来处理 HTTP 请求。
        # globals() 用于传递当前脚本的全局命名空间给应用。这意味着在 Web.py 应用中，你可以使用全局变量和方法来处理请求，确保不同部分的代码能够互相访问。
        # autoreload=False 意味着在生产环境下，Web.py 不会自动重新加载代码（提升性能），而在开发模式下，通常会设置为 True，以便代码更改后自动重新加载。
        # globals() 是 Python 内置的函数，它会返回当前模块的全局命名空间（一个字典）
        app = web.application(urls, globals(), autoreload=False) 
        # 这个端口是你的应用监听的端口，用来接收飞书应用的消息推送（例如消息事件、用户互动等）。这与飞书服务器的端口不同，飞书会向这个端口发送事件数据。
        port = conf().get("feishu_port", 9891) 
        # 这行代码启动了 Web.py 应用，并通过 web.httpserver.runsimple 启动一个简单的 HTTP 服务器。
        # app.wsgifunc() 是 Web.py 应用的 WSGI 函数，它告知 HTTP 服务器如何处理每一个 HTTP 请求。
        # ("0.0.0.0", port) 表示服务器绑定在所有网络接口（0.0.0.0）和指定的端口（port，通常为 9891）上，使得应用能够接收来自外部的请求。
        # 路由 是 Web 应用中根据请求的 URL 和请求方法（如 GET、POST）来确定应该执行哪段代码的机制。
        # 路由的作用就是 把用户访问的 URL 和实际处理请求的代码（如函数或类）对应起来
        web.httpserver.runsimple(app.wsgifunc(), ("0.0.0.0", port))
     # 发送消息方法
    def send(self, reply: Reply, context: Context):
        msg = context.get("msg") # 获取消息上下文中的FeishuMessage实例
        is_group = context["isgroup"] # 是否是群聊
        if msg:  # 如果消息上下文中有消息实例，则直接获取其 access_token
            access_token = msg.access_token 
        else: # 如果没有消息实例，调用方法获取新的 access_token,这个 access_token 用于在发送
              # API 请求时进行身份验证和授权。
            access_token = self.fetch_access_token()
        headers = { # 设置请求头，包含授权信息和内容类型
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
        }
        msg_type = "text" # 默认消息类型为文本
        # 打印日志，记录发送消息的类型和回复的内容
        logger.info(f"[FeiShu] start send reply message, type={context.type}, content={reply.content}")
        reply_content = reply.content # 回复消息的内容
        content_key = "text"  # 指定消息内容的键名是 "text"。
        if reply.type == ReplyType.IMAGE_URL: # 如果回复类型为图片URL
            # 调用图片上传方法，并返回上传后的图片key,这时reply.content是机器人生成的图片的url
            reply_content = self._upload_image_url(reply.content, access_token)
            if not reply_content: # 如果图片上传失败，打印警告日志并终止
                logger.warning("[FeiShu] upload file failed")
                return
            msg_type = "image" # 设置消息类型为图片，内容键名为 "image_key"
            content_key = "image_key"
        if is_group: # 如果是群聊
            # 构造群聊消息回复的URL，消息ID用作目标
            url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg.msg_id}/reply"
            data = { # 构造消息数据，包含消息类型和内容
                "msg_type": msg_type,
                "content": json.dumps({content_key: reply_content})
            }
            # 发送HTTP POST请求
            res = requests.post(url=url, headers=headers, json=data, timeout=(5, 10))
        else: # 如果是私聊
            url = "https://open.feishu.cn/open-apis/im/v1/messages" # 构造私聊消息发送的URL
            # 设置接收者ID类型，默认为 open_id
            params = {"receive_id_type": context.get("receive_id_type") or "open_id"}
            data = { # 构造消息数据，包含接收者ID、消息类型和内容
                "receive_id": context.get("receiver"),
                "msg_type": msg_type,
                "content": json.dumps({content_key: reply_content})
            }
            # 发送HTTP POST请求
            res = requests.post(url=url, headers=headers, params=params, json=data, timeout=(5, 10))
        res = res.json() # 将返回的响应数据解析为JSON
        if res.get("code") == 0: # 如果返回码为0，表示消息发送成功
            logger.info(f"[FeiShu] send message success")
        else: # 如果返回码非0，记录错误日志，包含错误码和信息
            logger.error(f"[FeiShu] send message failed, code={res.get('code')}, msg={res.get('msg')}")


    def fetch_access_token(self) -> str:
        # 飞书获取租户级访问令牌的URL
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        headers = { # 请求头，指定内容类型为JSON
            "Content-Type": "application/json"
        }
        req_body = { # 请求体，包含飞书应用的 app_id 和 app_secret
            "app_id": self.feishu_app_id,
            "app_secret": self.feishu_app_secret
        }
        data = bytes(json.dumps(req_body), encoding='utf8') # 将请求体转换为字节流
        # 发送POST请求获取access_token
        response = requests.post(url=url, data=data, headers=headers)
        if response.status_code == 200: # 如果响应状态为200，解析返回的JSON数据
            res = response.json()
            if res.get("code") != 0: # 如果返回的code不为0，表示获取失败，记录错误日志
                logger.error(f"[FeiShu] get tenant_access_token error, code={res.get('code')}, msg={res.get('msg')}")
                return ""
            else: # 返回成功获取到的tenant_access_token
                return res.get("tenant_access_token")
        else: # 如果响应状态不是200，记录错误日志
            logger.error(f"[FeiShu] fetch token error, res={response}")

    # 为啥要先下载,再上传,因为模型生成的图片，返回的是个url,这时这里要先下载下来,之后在传到飞书的服务器
    def _upload_image_url(self, img_url, access_token):
         # 打印调试日志，开始下载图片
        logger.debug(f"[WX] start download image, img_url={img_url}")
        response = requests.get(img_url) # 发送GET请求下载图片
        suffix = utils.get_path_suffix(img_url) # 获取图片的文件后缀名
        temp_name = str(uuid.uuid4()) + "." + suffix # 生成一个唯一的临时文件名
        if response.status_code == 200:
            # 如果图片下载成功，将其内容保存到本地临时文件
            with open(temp_name, "wb") as file:
                file.write(response.content)
        # 设置飞书图片上传的URL
        upload_url = "https://open.feishu.cn/open-apis/im/v1/images"
        data = { # 构造请求体，指定图片类型为消息用图
            'image_type': 'message'
        }
        headers = { # 设置请求头，包含授权令牌
            'Authorization': f'Bearer {access_token}',
        }
        with open(temp_name, "rb") as file: # 以二进制形式打开临时文件
            # 发送POST请求上传图片
            upload_response = requests.post(upload_url, files={"image": file}, data=data, headers=headers)
            logger.info(f"[FeiShu] upload file, res={upload_response.content}") # 打印上传结果的日志
            os.remove(temp_name) # 上传完成后删除临时文件
            return upload_response.json().get("data").get("image_key") # 返回上传后获得的图片key
# 用于处理来自飞书的消息事件，并根据事件类型和内容进行适当的处理。代码包括飞书消息接收、验证以及消息响应的处理逻辑。
class FeishuController:
    # 类常量
    FAILED_MSG = '{"success": false}'   # 请求失败时返回的消息，表示操作未成功
    SUCCESS_MSG = '{"success": true}'  # 请求成功时返回的消息，表示操作成功
    # 定义了一个字符串常量，表示飞书的消息接收事件类型，后续会用来判断收到的事件是否为消息接收事件。
    MESSAGE_RECEIVE_TYPE = "im.message.receive_v1"
    # GET 方法：这是一个简单的 HTTP GET 请求处理方法，用于检查服务是否启动成功。
    def GET(self):
        return "Feishu service start success!"
    # 用于处理飞书发送的消息事件。
    # 用户发送消息：用户在飞书客户端（可以是群聊或私聊）发送消息。飞书的服务器接收到消息后，会根据您在飞书开发者后台配
    # 置的事件订阅，决定是否将消息事件发送到您的聊天机器人应用。
    # 飞书将消息转发给聊天机器人应用：飞书会根据您的配置，向您的机器人应用的指定接收端点发送 HTTP 请求。请求的内容是一个包含
    # 飞书消息事件的 JSON 格式数据
    # 聊天机器人应用解析数据：在您的聊天机器人应用中，web.data() 用于获取 HTTP 请求中的原始数据，也就是飞书转发过来的消息事件数据。
    # json.loads(web.data().decode("utf-8")) 会将原始的 JSON 数据解析为 Python 对象，以便后续的处理。这个解析过程是将
    # 飞书发送的 JSON 格式的消息事件内容转换为 Python 数据结构（如字典、列表等）
    def POST(self):
        try:
            channel = FeiShuChanel() # 创建飞书通道实例，用于管理消息和访问令牌
            request = json.loads(web.data().decode("utf-8")) # 获取并解析请求中的 JSON 数据（即飞书发送的事件数据）。
            logger.debug(f"[FeiShu] receive request: {request}")  # 记录收到的请求日志
            # URL验证是飞书为了确保你的服务器能够正确接收事件推送而进行的一种验证机制。
            # 你需要在飞书的开发者后台配置事件订阅的回调地址（URL），然后飞书会向这个地址发送一个验证请求。
            # 这个请求包含 type=url_verification 和一个 challenge 字段，你的服务器必须按照要求返回相同的 challenge，
            # 这样飞书才能确认回调地址有效。
            # 完成这个验证后，飞书就会开始向该URL推送实际的事件数据，如消息接收、用户加入群聊等。
            # 什么时候会触发该验证请求？当你在飞书的开发者后台设置并启用事件订阅时，飞书平台会向你提供的回调地址发送一个 URL 验证请求。
            # 该请求需要通过你的服务器响应并返回相同的 challenge 值，表示验证通过。
            if request.get("type") == URL_VERIFICATION:
                # 如果是URL验证请求，返回挑战参数
                varify_res = {"challenge": request.get("challenge")}
                return json.dumps(varify_res)
            # 2.消息接收处理
            # token 校验
            header = request.get("header")
            # 如果没有header或token不匹配，返回失败消息
            if not header or header.get("token") != channel.feishu_token:
                return self.FAILED_MSG
            # 处理消息事件
            event = request.get("event")
            if header.get("event_type") == self.MESSAGE_RECEIVE_TYPE and event:
                # 处理消息接收事件
                # 如果消息内容或发送者信息为空，记录警告日志并返回失败消息
                if not event.get("message") or not event.get("sender"):
                    logger.warning(f"[FeiShu] invalid message, msg={request}")
                    return self.FAILED_MSG
                msg = event.get("message")
                # 假设飞书发送了一条消息通知给机器人，但由于网络延迟或其他原因，这条消息可能被发送两次。如果没有幂等判断，
                # 机器人就可能会对同一条消息发送两次回复。通过检查 message_id，程序可以确保对同一条消息只进行一次处理。
                if channel.receivedMsgs.get(msg.get("message_id")):
                    # 如果消息已处理过，记录警告日志并返回成功消息
                    logger.warning(f"[FeiShu] repeat msg filtered, event_id={header.get('event_id')}")
                    return self.SUCCESS_MSG
                channel.receivedMsgs[msg.get("message_id")] = True # 记录消息ID防止重复处理
                is_group = False # 默认不是群聊
                chat_type = msg.get("chat_type")  # 获取聊天类型
                if chat_type == "group": # 如果是群聊
                    # 如果消息中没有 mentions 字段，说明没有人被 @。在群聊中，如果没有提及机器人，则机器人可以选择不响应这条消息。
                    # 仅针对文本消息进行判断。非文本消息（如图片、文件等）可能不需要提及机器人即可触发响应。
                    if not msg.get("mentions") and msg.get("message_type") == "text":
                        return self.SUCCESS_MSG
                    # 如果@的不是机器人本身且是文本消息，不响应
                    # 这里的 飞书机器人 指的是您在 机器人应用 中配置和运行的机器人，而不是飞书平台本身的机器人。这个逻辑用于判断当前群
                    # 聊消息是否明确 @提到 您的机器人。
                    if msg.get("mentions")[0].get("name") != conf().get("feishu_bot_name") and msg.get("message_type") == "text":
                        return self.SUCCESS_MSG
                    is_group = True  # 标记为群聊
                    # 在飞书的消息体系中，每个群聊都有一个唯一的 chat_id，用于标识该群聊。
                    # 这是飞书用于管理群聊的内部 ID，与用户 ID (open_id) 类似，但专门用于群聊。
                    receive_id_type = "chat_id" 
                # "p2p" 表示 私聊（peer-to-peer） 消息，即用户单独与机器人直接对话的消息。
                elif chat_type == "p2p":  
                    # 在飞书中，用户有一个唯一的 open_id（开放平台 ID），用于标识单个用户。
                    # 如果机器人需要回复私聊消息，就需要依赖用户的 open_id 来发送消息。
                    receive_id_type = "open_id"
                else: # 如果 chat_type 不是 "group"（群聊）或者 "p2p"（私聊），即出现了其他类型的消息，机器人将 忽略 该消息。
                    logger.warning("[FeiShu] message ignore")
                    return self.SUCCESS_MSG
                # 构造飞书消息对象FeishuMessage
                feishu_msg = FeishuMessage(event, is_group=is_group, access_token=channel.fetch_access_token())
                if not feishu_msg: # 如果不存在这个对象,直接返回
                    return self.SUCCESS_MSG
                context = self._compose_context( # 传给chatchannel的对接收到的消息进行处理的函数
                    feishu_msg.ctype,
                    feishu_msg.content,
                    isgroup=is_group,
                    msg=feishu_msg,
                    receive_id_type=receive_id_type,
                    no_need_at=True
                )
                if context: # 如果有返回,交给chatchannel的生产者,用来绑定会话和消息队列等
                    channel.produce(context)
                logger.info(f"[FeiShu] query={feishu_msg.content}, type={feishu_msg.ctype}")
            return self.SUCCESS_MSG
        except Exception as e:
            logger.error(e)
            return self.FAILED_MSG

    def _compose_context(self, ctype: ContextType, content, **kwargs):
        context = Context(ctype, content) # 创建消息上下文对象，包含请求类型和内容
        context.kwargs = kwargs  # 将其他参数存入上下文的 kwargs 属性
        # 如果上下文中没有 "origin_ctype"，将其设置为原始的上下文类型
        if "origin_ctype" not in context:
            context["origin_ctype"] = ctype
        # 获取消息对象 (从 kwargs 中传入的 msg)
        cmsg = context["msg"]
        # 将消息的发送者 ID 设置为会话 ID，用于标识会话来源
        context["session_id"] = cmsg.from_user_id
        # 将other_user_id(群聊时是群id,私聊时是发送者的id)设置成消息的接收者
        context["receiver"] = cmsg.other_user_id
        if ctype == ContextType.TEXT:
            # 1.文本请求
            # 检查文本消息中是否包含创建图片的前缀(画)
            img_match_prefix = check_prefix(content, conf().get("image_create_prefix"))
            if img_match_prefix: # 如果包含前缀
                content = content.replace(img_match_prefix, "", 1) # 替换(只替换一次),替换后是图片的描述
                context.type = ContextType.IMAGE_CREATE # 设为创建图片类型
            else: # 如果不包含前缀
                context.type = ContextType.TEXT # 设为文本类型
            context.content = content.strip()
        # 如果是语音类型
        elif context.type == ContextType.VOICE:
            # 2.语音请求,条件是上下文中没有desire_rtype这个键,并且设置了允许对语音请求提供语音回复。
            if "desire_rtype" not in context and conf().get("voice_reply_voice"):
                context["desire_rtype"] = ReplyType.VOICE # 会把desire_rtype的类型设置为语音并放入上下文
        return context
