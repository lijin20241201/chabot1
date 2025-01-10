import os
import re
import threading
import time
from asyncio import CancelledError
from concurrent.futures import Future, ThreadPoolExecutor
from bridge.context import *
from bridge.reply import *
from channel.channel import Channel
from common.dequeue import Dequeue
from common import memory
from plugins import *
try:
    from voice.audio_convert import any_to_wav
except Exception as e:
    pass
# handler_pool 是在模块级别定义的一个变量，这意味着它 只在当前模块中是全局的。在当前模块内，任何函数、类或者方法都可以访问它
# ，前提是它们在 handler_pool 被定义之后调用。
# 但它并没有被声明为 全局变量，因此在模块外部无法直接访问。
handler_pool = ThreadPoolExecutor(max_workers=8)  # 处理消息的线程池
# 抽象类, 它包含了与具体的子类消息通道无关的通用处理逻辑
# 一个 ChatChannel 实例 ：表示一个消息通道的实例，它负责处理消息的接收和发送。
# 多个 session_id ：表示多个会话的标识，每个会话可能对应一个用户或一个群聊。
# 一个 ChatChannel 实例可能会处理多个会话，每个会话都有自己的 session_id。通过使用字典来存储 session_id 和 
# futures 对象，ChatChannel 可以管理多个会话的并发处理。
# ChatChannel 类中的方法和处理逻辑是所有特定消息通道（如微信、Telegram、Slack等）可以共用的逻辑。ChatChannel 
# 提供了与具体消息通道无关的通用处理功能，而具体的消息通道类（如 WeChatChannel、TelegramChannel 等）可以继承 
# ChatChannel 并实现各自特定的逻辑。
class ChatChannel(Channel):
    # 这些信息用于标识机器人的身份，以便它能正确地接收消息、发送消息和与用户交互
    name = None  # 机器人的用户名
    user_id = None  # 机器人的用户ID
    futures = {} # futures 用来存储与每个会话相关联的 future 对象，可以用于检查线程池中任务的执行状态，以及在需要时取消任务。
    sessions = {} # sessions 用来存储与每个 session_id 相关的消息队列和信号量。这是为了确保同一个会话中的消息按顺序处理 
    lock = threading.Lock() # lock 是一个线程锁，确保对 sessions 和 futures 的访问是线程安全的，以避免多线程并发操作时发生数据竞争。
    # 每个 ChatChannel 实例 只有一个后台线程执行 consume 方法，而 不是为每个 ChatChannel 实例创建多个线程。
    # 该线程在后台不断地检查消息队列是否有待处理的消息，并将其提交到线程池中处理。
    def __init__(self):
        _thread = threading.Thread(target=self.consume) # 初始化一个后台线程，执行 consume 方法。
        _thread.setDaemon(True) # 将线程设置为守护线程（daemon thread）。
        _thread.start() # 启动线程后，线程进入 就绪状态，等待 CPU 调度

    # 根据消息构造context，消息内容相关的触发项写在这里
    def _compose_context(self, ctype: ContextType, content, **kwargs):
        context = Context(ctype, content) # 创建一个新的 Context 对象，类型为 ctype，内容为 content
        context.kwargs = kwargs  # 将其他参数存储到 context 的 kwargs 属性中
        # 在第一次进入这个方法时，会在上下文中设置消息的原始类型
        if "origin_ctype" not in context:
            context["origin_ctype"] = ctype 
        # 根据是否有receiver判断是否是首次传入(如果没有接收者说明是首次传入)
        first_in = "receiver" not in context
        # 单聊：如果是单聊消息，那么 cmsg.from_user_id 和 cmsg.actual_user_id 是相同的，因为只有一个发送者。
        # 群聊：在群聊中，cmsg.from_user_id 可能是群聊的 ID（因为消息是发到群的），而 cmsg.actual_user_id 是发送消息的具体群成员的 ID。
        if first_in:  # 如果是首次传入
            config = conf() # 获取配置
            cmsg = context["msg"] # 获取上下文中的ChatMessage实例
            # 这是消息的发送者 ID。在单聊中，它通常指的是发送消息的用户；在群聊中，它可能是群聊消息中的用户 ID。
            # 场景：用于标识消息的发起者，通常是消息发送者的 ID。
            user_data = conf().get_user_data(cmsg.from_user_id) # 获取用户数据
            context["openai_api_key"] = user_data.get("openai_api_key")  # 设置消息发送者的API 密钥
            context["gpt_model"] = user_data.get("gpt_model")  # 设置消息发送者的GPT 模型
            if context.get("isgroup", False): # 如果是群聊
                group_name = cmsg.other_user_nickname # 获取群名称
                group_id = cmsg.other_user_id # 获取群 ID
                # 群名称白名单列表：是一个配置项，包含了允许机器人回复的群聊名称（或者说群组的昵称）。这个列表中的群聊，机器人才
                # 会处理其发来的消息。
                group_name_white_list = config.get("group_name_white_list", [])  
                # 群名称关键字白名单列表：这个列表包含了一些关键字，只要群名称中包含这些关键字，该群的消息就会被机器人回复。它提供了
                # 比直接匹配群名称白名单更灵活的方式。群聊的名称只要包含关键字，就会被认为是有效的群组。
                group_name_keyword_white_list = config.get("group_name_keyword_white_list", []) 
                # any() 函数接受一个可迭代对象（如列表、元组等），如果可迭代对象中的任何一个元素为 True，则 any() 返回 True；否则返回 False。
                # 这里传入的列表包含了 三个条件：
                # group_name in group_name_white_list：判断群名称是否在群名称白名单列表中。
                # "ALL_GROUP" in group_name_white_list：判断是否存在一个特殊的白名单项 "ALL_GROUP"，这个值表示所有群组都可以被允许。
                # 最后一个条件：检查群名称是否包含在群名称关键字白名单列表中的某个关键字。
                if any(
                    [
                        group_name in group_name_white_list,
                        "ALL_GROUP" in group_name_white_list,
                        check_contain(group_name, group_name_keyword_white_list),
                    ]
                ):
                    # group_chat_in_one_session 是一个配置项，用来定义哪些群聊应该在同一个会话中进行处理。这个配置通常用于限制
                    # 在特定群组内，所有的消息都可以使用相同的会话 ID。
                    # 这个配置项是一个包含群组名称的列表，表示这些群组的消息会被视为属于同一个会话进行处理
                    group_chat_in_one_session = conf().get("group_chat_in_one_session", [])
                    # 这一行设置 session_id 为 cmsg.actual_user_id，即群消息中的实际发送者ID
                    # 这里的 session_id 可能用于跟踪与该用户相关的所有消息，确保机器人能够在多轮对话中维持会话上下文。
                    # 在一个时刻多个用户发送消息时，每个用户的 session_id 都是独立的，即每个用户会有一个自己的 session_id。在这种情
                    # 况下，系统不会将不同用户的消息合并为一个会话 ID，而是会根据每个用户的 实际用户 ID（cmsg.actual_user_id） 来为每个
                    # 用户创建不同的会话 ID
                    # 这是消息中实际发出消息的用户 ID，通常在群聊中与 from_user_id 不同。actual_user_id 用于表示在群聊中，消息是由哪位群成员发出的。
                    # 场景：在群聊中，from_user_id 可能是群聊的 ID，而 actual_user_id 是发消息的具体群成员的 ID。对于群聊来说，这两个 ID 可能不同。
                    session_id = cmsg.actual_user_id
                    # 检查当前群名称是否在配置项group_chat_in_one_session 列表中。也就是说，如果这个群被列入该配置项中，表示所有在
                    # 这个群里的消息应该被视为属于同一个会话。
                    # "ALL_GROUP" in group_chat_in_one_session：这是一个特殊的条件，检查 group_chat_in_one_session 中是否
                    # 包含 "ALL_GROUP"。如果包含，意味着所有群聊中的消息都应该共享同一个会话 ID。也就是说，无论是哪一个群的消息，都会使
                    # 用相同的 session_id。
                    if any(
                        [
                            group_name in group_chat_in_one_session,
                            "ALL_GROUP" in group_chat_in_one_session,
                        ]
                    ):
                        # session_id = group_id 将 会话 ID 设置为群组 ID，也就是说，在该群中的所有消息都会共享同一个 session_id，
                        # 而不是基于发送者的用户 ID。这样做的目的是让同一个群聊中的所有消息被视为同一个会话，方便机器人进行群体回复。
                        # 同一个群聊内的消息共享 session_id：这样做的好处是，群内所有人的消息都会被视为同一个会话，机器人可以根据群组 ID 
                        # 来统一管理对话状态，并做出一致的回应。特别是在群聊中，机器人能够基于 群组 ID 进行群体对话管理，而不是对每个用户进
                        # 行单独的会话管理。
                        # 群聊中的会话是以 群组 ID 作为会话标识符来管理的，因此每个群的消息会共享一个会话 ID，而不同的群之间会有独立的会话 ID。
                        session_id = group_id
                else: # 不需要回复，groupName不在白名单中，这种情况不需要机器人回复
                    logger.debug(f"No need reply, groupName not in whitelist, group_name={group_name}")
                    return None
                context["session_id"] = session_id # 设置session_id(如果一个群共用一个会话,就是群id,否则是发送消息者)
                context["receiver"] = group_id # 设置接收者为群 ID
            else: # 如果是单聊(这种情况只有机器人和别的用户)
                context["session_id"] = cmsg.other_user_id # 设置 session_id 为用户 ID
                context["receiver"] = cmsg.other_user_id # 设置接收者为用户 ID
            # 所有监听接收到消息事件的插件会按优先级处理这个e_context,并可以根据需要修改它。
            e_context = PluginManager().emit_event(EventContext(Event.ON_RECEIVE_MESSAGE, {"channel": self, "context": context}))
            context = e_context["context"] 
            # 如果事件传播行为是 BREAK_PASS(事件结束) 或者 context 是 None，返回 context
            if e_context.is_pass() or context is None:
                return context
            # 如果消息是机器人自己发送的且配置中不允许处理自己发送的消息，返回None
            if cmsg.from_user_id == self.user_id and not config.get("trigger_by_self", True):
                logger.debug("[chat_channel]self message skipped")
                return None
        # 处理文本消息内容,群聊和私聊时处理@
        if ctype == ContextType.TEXT:
            # 如果是第一次进入此方法并且内容中包含引用消息(对之前消息的引用)的标志
            if first_in and "」\n- - - - - - -" in content:  
                logger.debug(content) # 输出当前内容到日志
                logger.debug("[chat_channel]reference query skipped") # 输出跳过处理的日志
                return None  # 跳过此次处理，返回 None
            # 获取黑名单中的昵称列表
            nick_name_black_list = conf().get("nick_name_black_list", [])
            if context.get("isgroup", False):  # 如果是群聊消息，处理群聊相关的逻辑
                # match_prefix检查content是否包含@bot这样的前缀,match_contain检查是否包含这些关键字
                match_prefix = check_prefix(content, conf().get("group_chat_prefix"))
                match_contain = check_contain(content, conf().get("group_chat_keyword"))
                flag = False # 标志位，是否触发了机器人的回复
                # 如果消息接收者不是实际发送者
                # 在群聊中 机器人自己发送的消息，to_user_id 和 actual_user_id 是相同的，因为发送者和接收者都是机器人。(过滤的是这种情况)
                if context["msg"].to_user_id != context["msg"].actual_user_id:
                    # 如果匹配到前缀或关键字，说明触发了机器人回复
                    # 在这个条件判断下，通常表示 群聊中的用户与机器人之间的互动，即用户希望机器人进行回复。消息的发送者（
                    # actual_user_id）是群聊中的一个用户，接收者（to_user_id）是机器人，或者群聊的机器人会被触发响应。
                    if match_prefix is not None or match_contain is not None:
                        flag = True
                        # 1 是 replace() 方法的 替换次数参数，表示只替换第一个匹配的部分。这样做的目的是 去掉消息中的前缀，
                        # 比如 @bot，但只去掉 第一个 出现的前缀，以免误删消息中的其他 @bot（如果存在的话）。
                        if match_prefix:
                            content = content.replace(match_prefix, "", 1).strip()
                    # 判断ChatMessage中是否有 @ 标记。如果消息中包含了 @，is_at 会为 True，表示这条消息可能是在提到某个人或者机器人。
                    if context["msg"].is_at: 
                        nick_name = context["msg"].actual_user_nickname # 实际发送者的昵称
                        # 这是一个过滤机制，用于屏蔽来自特定用户的消息（通过昵称判断）。如果一个用户的昵称在黑名单中，机器人会无视该用户的消息，避免对其进行任何回应。
                        if nick_name and nick_name in nick_name_black_list:
                            logger.warning(f"[chat_channel] Nickname {nick_name} in In BlackList, ignore") 
                            return None
                        # 记录收到群聊 @ 的日志
                        logger.info("[chat_channel]receive group at")
                        # group_at_off 控制机器人是否响应群聊中的 @ 提及。
                        # 如果 group_at_off 为 False（或未设置），意味着机器人会响应群聊中的 @ 消息，无论是 @bot 还是 @其他用户。
                        # 如果 group_at_off 为 True，则机器人不会响应任何群聊中的 @ 消息。
                        if not conf().get("group_at_off", False):
                            flag = True # 如果在群聊中机器人被@,机器人会处理回复
                         # 确保 self.name 已经赋值
                        self.name = self.name if self.name is not None else "" 
                        # 匹配@self.name(一般是bot),后面跟空格或四分之一空格的模式
                        # 如果 self.name = "chatbot\u2005"（四分之一空格），re.escape(self.name) 会返回 chatbot\u2005，
                        # 而不是将它转化为 \u2005 形式。
                        pattern = f"@{re.escape(self.name)}(\u2005|\u0020)"
                        # re.sub 会扫描 content 中的文本，找到所有符合 pattern 的部分，并用空字符串 r"" 将它们替换掉，
                        # 最终返回替换后的结果 subtract_res。
                        subtract_res = re.sub(pattern, r"", content)
                        # at_list 通常是指被@的用户的昵称列表，也就是说，at_list 中保存了所有在当前消息中提到（@）的群成员的昵称。
                        # 如果消息中有@群内其他人的情况，它会删除所有类似 @user 后跟空格的提及部分。
                        if isinstance(context["msg"].at_list, list):
                            for at in context["msg"].at_list:
                                pattern = f"@{re.escape(at)}(\u2005|\u0020)"
                                subtract_res = re.sub(pattern, r"", subtract_res)
                        # context["msg"](ChatMessage实例).self_display_name 指的是 机器人在当前群聊中的显示昵称。
                        # 这里移除content中@机器人昵称的部分
                        if subtract_res == content and context["msg"].self_display_name:
                            pattern = f"@{re.escape(context['msg'].self_display_name)}(\u2005|\u0020)"
                            subtract_res = re.sub(pattern, r"", content)
                        content = subtract_res # 更新content会去除@后的部分
                # 虽然接收到的origin_ctype是语音，但由于没有触发机器人回复(flag=Faslse)，机器人不会回复，并且通过日志提示这一点。
                if not flag:
                    if context["origin_ctype"] == ContextType.VOICE:
                        logger.info("[chat_channel]receive group voice, but checkprefix didn't match")
                    return None
            else:  # 私聊的情况
                nick_name = context["msg"].from_user_nickname # 发送者昵称
                if nick_name and nick_name in nick_name_black_list:  # 如果发送消息的用户在黑名单里,会被忽略
                    logger.warning(f"[chat_channel] Nickname '{nick_name}' in In BlackList, ignore")
                    return None
                # 检查私聊消息是否匹配前缀
                match_prefix = check_prefix(content, conf().get("single_chat_prefix", [""]))
                if match_prefix is not None:  # 判断如果匹配到自定义前缀，则返回过滤掉前缀+空格后的内容
                    content = content.replace(match_prefix, "", 1).strip()  # 去掉匹配到的前缀
                elif context["origin_ctype"] == ContextType.VOICE:  # 如果源消息是私聊的语音消息，允许不匹配前缀，放宽条件
                    pass
                else:
                    return None # 如果没有匹配到前缀，且不是语音消息,返回None
            content = content.strip() # 去除内容前后的空白字符
            img_match_prefix = check_prefix(content, conf().get("image_create_prefix",[""])) # 检查消息是否包含图像生成的前缀(画)
            if img_match_prefix:
                content = content.replace(img_match_prefix, "", 1)  # 移除图像生成命令前缀
                context.type = ContextType.IMAGE_CREATE # 设置消息类型为图像生成
            else:
                context.type = ContextType.TEXT # 否则保持为文本消息
            context.content = content.strip()  # 更新消息内容，去除空格
            # 回复类型的设置：如果消息上下文中没有设置 desire_rtype（期望的回复类型），并且配置总是回复语音（always_reply_voice）
            # ，则将期望的回复类型设置为语音（ReplyType.VOICE）。
            if "desire_rtype" not in context and conf().get("always_reply_voice") and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                context["desire_rtype"] = ReplyType.VOICE  # 设置期望的回复类型为语音
        # 处理语音消息的回复类型：对于语音消息，如果没有设置期望的回复类型，并且配置语音回复，则将 desire_rtype 设置为语音
        elif context.type == ContextType.VOICE:
            if "desire_rtype" not in context and conf().get("voice_reply_voice") and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                context["desire_rtype"] = ReplyType.VOICE # 设置期望的语音回复类型
        return context
    # 处理消息
    def _handle(self, context: Context):
        if context is None or not context.content: # 判断context是否为空或其内容为空，如果为空则返回
            return
        # 打印调试信息，表示准备处理context
        logger.debug("[chat_channel] ready to handle context: {}".format(context))
        # 生成回复的步骤
        reply = self._generate_reply(context)
        # 打印调试信息，表示准备包装回复
        logger.debug("[chat_channel] ready to decorate reply: {}".format(reply))
        # 如果回复不为空且有内容，进行回复的包装
        if reply and reply.content:
            reply = self._decorate_reply(context, reply)
            # 发送包装后的回复
            self._send_reply(context, reply)

    def _generate_reply(self, context: Context, reply: Reply = Reply()) -> Reply:
        # 调用插件管理实例的触发事件逻辑,内部会依照优先级调用事件对应的一系列插件对消息做处理,直到
        # 返回的e_context的事件传播行为不是CONTINUE为止
        e_context = PluginManager().emit_event(
            EventContext(
                Event.ON_HANDLE_CONTEXT,
                {"channel": self, "context": context, "reply": reply},
            )
        )
        reply = e_context["reply"] # 更新reply为插件事件处理后的回复内容
        # 如果e_context的事件传播行为不是BREAK_PASS,调用默认的事件处理逻辑
        if not e_context.is_pass():
            # 打印调试信息，显示当前context类型和内容
            logger.debug("[chat_channel] ready to handle context: type={}, content={}".format(context.type, context.content))
            # 处理文字消息和图片创建消息
            if context.type == ContextType.TEXT or context.type == ContextType.IMAGE_CREATE:  
                context["channel"] = e_context["channel"] # 设置消息上下文通道为e_context的通道
                # 底层实际调用聊天机器人的回复方法(传入用户发送消息,消息上下文)
                reply = super().build_reply_content(context.content, context)
            # context.type 表示的是用户发送的消息类型是语音类型。
            elif context.type == ContextType.VOICE:  
                cmsg = context["msg"]  # 获取上下文中的ChatMessage实例
                cmsg.prepare()
                file_path = context.content # 上下文中的内容是语音文件的路径
                wav_path = os.path.splitext(file_path)[0] + ".wav" # 构建wav文件路径
                try:
                    any_to_wav(file_path, wav_path) # 尝试将语音文件转换为wav格式
                except Exception as e:  # 转换失败，直接使用mp3，对于某些api，mp3也可以识别
                    logger.warning("[chat_channel]any to wav error, use raw path. " + str(e))
                    wav_path = file_path
                # 语音识别，将语音转为文字
                reply = super().build_voice_to_text(wav_path)
                # 删除临时文件
                try:
                    os.remove(file_path)
                    if wav_path != file_path:
                        os.remove(wav_path)
                except Exception as e: # 出异常时,忽略,会继续向下执行代码
                    pass
                    # logger.warning("[chat_channel]delete temp file error: " + str(e))
                # 如果语音识别返回的回复的回复类型是文本类型
                if reply.type == ReplyType.TEXT:
                    # 这时用来对识别出的用户指令进行再处理(是文本类型)
                    new_context = self._compose_context(ContextType.TEXT, reply.content, **context.kwargs)
                    if new_context: # 如果new_context存在,根据生成的文本消息,递归调用_generate_reply
                        reply = self._generate_reply(new_context)
                    else: # 否则返回None
                        return
            elif context.type == ContextType.IMAGE:  # 处理图片消息（暂时只将图片路径和消息存入缓存）
                memory.USER_IMAGE_CACHE[context["session_id"]] = {
                    "path": context.content,
                    "msg": context.get("msg") # ChatMessage对象
                }
            elif context.type == ContextType.SHARING: # 处理分享信息（当前没有默认逻辑）
                pass # 当程序执行到 pass 语句时，什么都不会发生，程序会继续执行后面的代码。
            elif context.type == ContextType.FUNCTION or context.type == ContextType.FILE: # 处理文件消息或函数调用等（当前没有默认逻辑）
                pass
            else: # 处理未知类型的消息
                logger.warning("[chat_channel] unknown context type: {}".format(context.type))
                return
        return reply # 返回最终生成的回复

    def _decorate_reply(self, context: Context, reply: Reply) -> Reply:
        # 如果回复对象存在且其类型有效
        if reply and reply.type:
            e_context = PluginManager().emit_event( # 触发插件事件，处理回复装饰操作
                EventContext(
                    Event.ON_DECORATE_REPLY, # 得到回复后准备装饰事件
                    {"channel": self, "context": context, "reply": reply},
                )
            )
            reply = e_context["reply"] # 更新回复为插件事件处理后的回复
            desire_rtype = context.get("desire_rtype") # 获取期望的回复类型
            # 如果事件上下文的事件传播行为不是BREAK_PASS类型,并且有回复,做默认的装饰逻辑
            if not e_context.is_pass() and reply and reply.type: 
                if reply.type in self.NOT_SUPPORT_REPLYTYPE: # 如果回复类型不支持，则修改为错误类型并添加提示信息
                    logger.error("[chat_channel]reply type not support: " + str(reply.type))
                    reply.type = ReplyType.ERROR
                    reply.content = "不支持发送的消息类型: " + str(reply.type)
                # 如果回复类型是文本
                if reply.type == ReplyType.TEXT:
                    reply_text = reply.content
                    # 如果期望的是语音类型的回复，且语音回复类型支持
                    if desire_rtype == ReplyType.VOICE and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                        reply = super().build_text_to_voice(reply.content) # 将文本转换为语音，并递归调用装饰方法
                        return self._decorate_reply(context, reply)
                    if context.get("isgroup", False): # 如果是群组消息，处理@操作和群聊前后缀
                        if not context.get("no_need_at", False): # 需要@的情况
                            reply_text = "@" + context["msg"].actual_user_nickname + "\n" + reply_text.strip()
                        reply_text = conf().get("group_chat_reply_prefix", "") + reply_text + conf().get("group_chat_reply_suffix", "")
                    else: # 如果是私聊，处理私聊前后缀(私聊不需要加@)
                        reply_text = conf().get("single_chat_reply_prefix", "") + reply_text + conf().get("single_chat_reply_suffix", "")
                    reply.content = reply_text # 更新回复内容为处理后的回复
               # 如果回复类型是错误或信息类型，添加前缀标记
                elif reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO:
                    reply.content = "[" + str(reply.type) + "]\n" + reply.content
                # 如果回复类型是图片、语音、文件、视频等媒体类型，暂时不做处理
                elif reply.type == ReplyType.IMAGE_URL or reply.type == ReplyType.VOICE or reply.type == ReplyType.IMAGE or reply.type == ReplyType.FILE or reply.type == ReplyType.VIDEO or reply.type == ReplyType.VIDEO_URL:
                    pass
                else: # 如果回复类型不支持，则记录日志并返回
                    logger.error("[chat_channel] unknown reply type: {}".format(reply.type))
                    return
            # 如果期望的回复类型和实际的回复类型不同，并且不是错误或信息类型，则记录警告
            if desire_rtype and desire_rtype != reply.type and reply.type not in [ReplyType.ERROR, ReplyType.INFO]:
                logger.warning("[chat_channel] desire_rtype: {}, but reply type: {}".format(context.get("desire_rtype"), reply.type))
            return reply # 返回最终装饰后的回复

    def _send_reply(self, context: Context, reply: Reply):
        if reply and reply.type: # 如果回复对象存在且其类型有效
            e_context = PluginManager().emit_event( # 触发插件事件，处理发送回复的逻辑
                EventContext(
                    Event.ON_SEND_REPLY,  # 发送回复事件
                    {"channel": self, "context": context, "reply": reply},
                )
            )
            reply = e_context["reply"] # 更新回复为插件事件处理后的回复
            # 如果e_context的事件传播行为不是BREAK_PASS,且回复类型有效,发送回复
            if not e_context.is_pass() and reply and reply.type:
                logger.debug("[chat_channel] ready to send reply: {}, context: {}".format(reply, context))
                self._send(reply, context) # 调用发送方法将回复发送出去

    def _send(self, reply: Reply, context: Context, retry_cnt=0):
        try:
            self.send(reply, context) # 调用具体子类的send 方法实际发送消息
        except Exception as e: # 如果出现异常
            logger.error("[chat_channel] sendMsg error: {}".format(str(e))) # 记录发送消息时的错误
            if isinstance(e, NotImplementedError): # 如果是 NotImplementedError 异常，则不做处理，直接返回
                return
            logger.exception(e) # 记录异常详细信息
            if retry_cnt < 2: # 如果重试次数小于 2，则进行重试
                time.sleep(3 + 3 * retry_cnt) # 等待 3 秒后进行重试，重试次数越多，等待时间越长
                self._send(reply, context, retry_cnt + 1) # 递归调用 _send 方法进行重试

    def _success_callback(self, session_id, **kwargs):  # 线程正常结束时的回调函数
        # 打印调试日志，记录成功的线程结束，输出 session_id
        logger.debug("Worker return success, session_id = {}".format(session_id))

    def _fail_callback(self, session_id, exception, **kwargs):  # 线程异常结束时的回调函数
        # 记录异常信息到日志，输出线程抛出的异常
        logger.exception("Worker return exception: {}".format(exception))
    # 定义并返回一个实际的回调函数，在任务执行完毕后调用
    def _thread_pool_callback(self, session_id, **kwargs):
        def func(worker: Future):
            try:
                # worker.exception(),如果任务有异常，它返回的是异常对象；如果没有异常，则返回 None。
                worker_exception = worker.exception() # 检查任务是否抛出了异常
                if worker_exception:
                    # 如果任务执行中抛出异常，调用失败的回调函数
                    self._fail_callback(session_id, exception=worker_exception, **kwargs)
                else:
                    self._success_callback(session_id, **kwargs) # 如果任务执行成功，调用成功的回调函数
            except CancelledError as e:
                logger.info("Worker cancelled, session_id = {}".format(session_id)) # 如果任务被取消，打印相关日志
            except Exception as e: # 其他异常，记录异常日志
                logger.exception("Worker raise exception: {}".format(e))
            # 在此释放信号量，标志着该任务的处理完毕,1指信号量对应的索引
            with self.lock:
                self.sessions[session_id][1].release()

        return func
    # 这是生产者方法，负责将消息（context）放入指定会话的消息队列中。
    def produce(self, context: Context):
        session_id = context["session_id"] # 获取当前消息的 session_id
        with self.lock: # 使用锁确保访问 sessions 字典时的线程安全
            if session_id not in self.sessions: # 如果该 session_id 没有对应的会话记录
                # 初始化一个新的会话，包含一个消息队列和一个信号量
                self.sessions[session_id] = [
                    Dequeue(), # 消息队列（用于存储待处理的消息）
                    threading.BoundedSemaphore(conf().get("concurrency_in_session", 4)),  # 信号量，控制每个会话的最大并发数
                ]
            # 如果消息类型是文本且内容以 "#" 开头，则认为是管理命令，优先处理
            if context.type == ContextType.TEXT and context.content.startswith("#"):
                self.sessions[session_id][0].putleft(context)  # 将该管理命令放入队列的左侧，优先处理
            else:
                self.sessions[session_id][0].put(context) # 将常规消息放入队列的右侧

    # 消费者函数，单独线程，用于从消息队列中取出消息并处理
    # 锁的作用：它的目的是保证同一时间 只有一个线程 可以进入 with self.lock 代码块。这样，多个线程就不会在同一时间修改共享资源，从而避免了竞争条件
    def consume(self):
        while True: # 无限循环，持续消费消息
            with self.lock: # 确保在访问 sessions 时线程安全
                session_ids = list(self.sessions.keys()) # 获取当前所有 session_id
            for session_id in session_ids: # 遍历所有的 session_id
                with self.lock: # 确保在访问 sessions[session_id] 时线程安全
                    context_queue, semaphore = self.sessions[session_id] # 获取当前 session 的消息队列和信号量
                # 尝试获取信号量，如果没有剩余信号量，则 acquire 返回 False，并不会阻塞当前线程。进入会消耗一个信号量
                if semaphore.acquire(blocking=False): 
                    if not context_queue.empty(): # 如果队列中有消息待处理
                        context = context_queue.get() # 获取队列中的一个消息
                        logger.debug("[chat_channel] consume context: {}".format(context)) # 打印日志，调试时查看消息内容
                        # 将 context 提交到线程池中进行处理，_handle 方法将会在其他线程中执行。
                        # 任务 提交之后，不管任务是否已经开始或完成，回调函数 self._thread_pool_callback 会被立即注册。即使当前任务还
                        # 没有执行，回调函数已经挂载到 Future 对象上。
                        # 当任务执行完毕时，线程池会在后台自动执行回调函数。此时，future 对象的 done() 方法会返回 True，然后会触发回调函数的执行。
                        future: Future = handler_pool.submit(self._handle, context) 
                        # 给 future 添加回调函数，当任务完成时执行回调，回调函数会根据 session_id 和 context 处理后续操作。
                        future.add_done_callback(self._thread_pool_callback(session_id, context=context))
                        with self.lock: # 确保对 futures 的修改线程安全
                            if session_id not in self.futures: # 如果该 session_id 尚未在 futures 中
                                self.futures[session_id] = []  # 初始化 futures 对应的列表
                            self.futures[session_id].append(future) # 将 future 对象加入 futures 字典中，用于追踪该会话中的任务。
                    # 这种情况是消息队列为空,当前没有任务在占有信号量,除了当前占有的信号量,没其他占有的情况
                    elif semaphore._initial_value == semaphore._value + 1: 
                        with self.lock:  # 确保对 sessions 和 futures 的修改线程安全
                            self.futures[session_id] = [t for t in self.futures[session_id] if not t.done()] # 过滤掉已完成的任务
                            # assert 失败时会抛出异常 (AssertionError)，并且带有你提供的错误消息（如果有的话）
                            assert len(self.futures[session_id]) == 0, "thread pool error" # 如果有未完成的任务，则抛出异常
                            del self.sessions[session_id] # 删除该 session 的记录，表示该 session 已处理完所有任务
                    else: # 这种情况是消息队列为空,但是还有未完成任务在占用信号量,这时会释放信号量
                        semaphore.release()
            time.sleep(0.2) # 暂停 0.2 秒，避免频繁占用 CPU，减轻负担

    # 取消session_id对应的所有任务，只能取消排队的消息和已提交线程池但未执行的任务
    def cancel_session(self, session_id):
        with self.lock: # 使用锁确保对 sessions 和 futures 的访问是线程安全的
            if session_id in self.sessions: # 检查 session_id 是否存在于 sessions 中
                for future in self.futures[session_id]:  # 遍历该 session_id 对应的所有 future 对象
                    future.cancel() # 取消该 future 对象，即停止其执行
                cnt = self.sessions[session_id][0].qsize() # 获取该 session 对应消息队列中的消息数量
                if cnt > 0: # 如果队列中有消息
                    logger.info("Cancel {} messages in session {}".format(cnt, session_id)) # 记录取消的消息数
                self.sessions[session_id][0] = Dequeue() # 清空该 session 对应的消息队列，重置为新的空队列
    # 取消所有会话对应的所有任务
    def cancel_all_session(self):
        with self.lock:  # 使用锁确保对 sessions 和 futures 的访问是线程安全的
            for session_id in self.sessions: # 遍历所有 session_id
                for future in self.futures[session_id]:  # 遍历该 session_id 对应的所有 future 对象
                    future.cancel() # 取消该 future 对象，即停止其执行
                cnt = self.sessions[session_id][0].qsize()  # 获取该 session 对应消息队列中的消息数量
                if cnt > 0: # 如果队列中有消息
                    logger.info("Cancel {} messages in session {}".format(cnt, session_id)) # 记录取消的消息数
                self.sessions[session_id][0] = Dequeue() # 清空该 session 对应的消息队列，重置为新的空队列

# 检查前缀
def check_prefix(content, prefix_list):
    if not prefix_list: # 如果前缀列表为空，则返回 None
        return None
    for prefix in prefix_list: # 遍历前缀列表
        if content.startswith(prefix):  # 如果 content 以某个 prefix 开头
            return prefix # 返回匹配的前缀
    return None # 如果没有找到任何匹配的前缀，返回 None
# 检查是否包含某些keyword
def check_contain(content, keyword_list):
    if not keyword_list: # 如果关键词列表为空，则返回 None
        return None
    for ky in keyword_list: # 遍历关键词列表
        if content.find(ky) != -1: # 如果 content 包含某个关键词（find 方法返回非 -1 值表示找到关键词）
            return True # 返回 True 表示找到匹配的关键词
    return None # 如果没有找到任何匹配的关键词，返回 None
