# encoding:utf-8

import requests

from bot.bot import Bot # 从bot模块导入Bot基类
from bridge.reply import Reply, ReplyType


# Baidu Unit对话接口 (可用, 但能力较弱)
class BaiduUnitBot(Bot):
    def reply(self, query, context=None):
        token = self.get_token() # 获取百度API的访问令牌
        # 构造请求URL，包含访问令牌
        url = "https://aip.baidubce.com/rpc/2.0/unit/service/v3/chat?access_token=" + token
        # 构造POST请求的数据，包含查询的文本信息以及一些参数
        post_data = (
            '{"version":"3.0","service_id":"S73177","session_id":"","log_id":"7758521","skill_ids":["1221886"],"request":{"terminal_id":"88888","query":"'
            + query
            + '", "hyper_params": {"chat_custom_bot_profile": 1}}}'
        )
        print(post_data) # 打印POST数据，便于调试
        # 设置请求头，指定内容类型为"application/x-www-form-urlencoded"
        headers = {"content-type": "application/x-www-form-urlencoded"}
        response = requests.post(url, data=post_data.encode(), headers=headers) # 发送POST请求到百度Unit对话接口
        if response: # 如果请求成功，处理响应并生成Reply对象
            # 从响应中提取返回的内容，并创建一个文本回复对象
            reply = Reply(
                ReplyType.TEXT,
                response.json()["result"]["context"]["SYS_PRESUMED_HIST"][1],
            )
            return reply

    def get_token(self):
        # 设置百度API的Access Key和Secret Key，这些是认证请求的必要信息
        access_key = "YOUR_ACCESS_KEY"
        secret_key = "YOUR_SECRET_KEY"
        # 构造获取访问令牌的请求URL，使用client_credentials授权模式
        host = "https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=" + access_key + "&client_secret=" + secret_key
        response = requests.get(host) # 发送GET请求获取访问令牌
        if response:# 如果响应成功，返回响应中的access_token
            print(response.json())  # 打印返回的JSON响应，方便调试
            return response.json()["access_token"] # 返回从响应中提取的访问令牌
