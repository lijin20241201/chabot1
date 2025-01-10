# -*- coding: utf-8 -*-
import random
from hashlib import md5

import requests

from config import conf
from translate.translator import Translator

# 调用百度翻译 API 来进行语言翻译。
class BaiduTranslator(Translator):
    def __init__(self) -> None:
        super().__init__()
        # 百度翻译 API 的基础地址和路径
        endpoint = "http://api.fanyi.baidu.com"
        path = "/api/trans/vip/translate"
        self.url = endpoint + path  # 完整的 API URL
        # 从配置文件中获取 Baidu API 的 appid 和 appkey
        self.appid = conf().get("baidu_translate_app_id")
        self.appkey = conf().get("baidu_translate_app_key")
        # 如果没有配置 appid 或 appkey，抛出异常
        if not self.appid or not self.appkey:
            raise Exception("baidu translate appid or appkey not set")

    # For list of language codes, please refer to `https://api.fanyi.baidu.com/doc/21`, need to convert to ISO 639-1 codes
     # translate 方法用于执行翻译
    def translate(self, query: str, from_lang: str = "", to_lang: str = "en") -> str:
        if not from_lang:
            from_lang = "auto"  # 如果没有指定源语言，使用自动检测
        salt = random.randint(32768, 65536) # 生成一个随机的盐值（用于 MD5 签名）
        # 计算 MD5 签名
        sign = self.make_md5("{}{}{}{}".format(self.appid, query, salt, self.appkey))
        # 请求头信息，指定内容类型
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        # 请求的参数，包括 appid、查询文本、源语言、目标语言、盐值和签名
        payload = {"appid": self.appid, "q": query, "from": from_lang, "to": to_lang, "salt": salt, "sign": sign}
        # 重试机制，最多重试 3 次
        retry_cnt = 3
        # 52000：请求成功,52001：服务器繁忙（通常是临时性问题),52002：请求超时（也可能是临时问题）,
        # 因为连续3次超时时,会退出循环,但是其实没有返回翻译结果,所以后面要判断一下
        while retry_cnt:
            # 发送 POST 请求到百度翻译 API
            r = requests.post(self.url, params=payload, headers=headers)
            result = r.json() # 解析 JSON 响应
            # 获取返回的错误码（默认为 "52000"）
            errcode = result.get("error_code", "52000")
            if errcode != "52000":
                # 如果是服务器忙或请求超时，减少重试次数并继续
                if errcode == "52001" or errcode == "52002":
                    retry_cnt -= 1
                    continue #退出本次循环,继续下一次
                else:  # 其他错误码：例如无效的 appid 或 appkey，输入参数错误等。
                    raise Exception(result["error_msg"])
            else:
                break # 请求成功，跳出循环
        if retry_cnt == 0:  # 重试次数耗尽时抛出异常
            raise Exception("多次重试后翻译失败.")
        # 从返回的翻译结果中提取文本并拼接
        # trans_result 字段包含一个列表，每个元素对应一次翻译操作的结果。每个元素（即 item）通常是一个字典
        # item["dst"] 是百度翻译 API 返回的翻译结果中的每一句翻译文本。
        text = "\n".join([item["dst"] for item in result["trans_result"]])
        return text
     # 生成 MD5 签名的方法
    def make_md5(self, s, encoding="utf-8"):
        return md5(s.encode(encoding)).hexdigest()  # 将字符串编码为字节，并计算其 MD5 哈希值