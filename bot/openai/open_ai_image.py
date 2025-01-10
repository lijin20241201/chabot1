import time

import openai # 导入 OpenAI SDK，用于调用 OpenAI 提供的接口
import openai.error # 导入 OpenAI 的错误模块，用于处理可能的异常

from common.log import logger
from common.token_bucket import TokenBucket # 导入令牌桶模块，用于速率限制
from config import conf


# OPENAI提供的画图接口
class OpenAIImage(object):
     # 初始化会话对象，传入会话 ID 和可选的系统提示和模型
    def __init__(self):
        openai.api_key = conf().get("open_ai_api_key") # 从配置中获取 OpenAI 的 API 密钥
        if conf().get("rate_limit_dalle"): # 如果配置中启用了 DALL-E 的速率限制
            self.tb4dalle = TokenBucket(conf().get("rate_limit_dalle", 50)) # 初始化令牌桶，默认速率为 50
    # 定义生成图片的方法
    def create_img(self, query, retry_count=0, api_key=None, api_base=None):
        try:
            # 如果启用了速率限制并且没有获取到令牌，则返回错误提示
            if conf().get("rate_limit_dalle") and not self.tb4dalle.get_token():
                return False, "请求太快了，请休息一下再问我吧"
            logger.info("[OPEN_AI] image_query={}".format(query)) # 记录查询日志
            # 调用 OpenAI 的 Image.create 接口生成图片
            response = openai.Image.create(
                api_key=api_key, # 使用传入的 API 密钥
                prompt=query, # 图片的描述
                n=1,  # 每次生成图片的数量
                model=conf().get("text_to_image") or "dall-e-2", # 指定使用的模型，默认为 "dall-e-2"
                # size=conf().get("image_create_size", "256x256"),  # 图片大小,可选有 256x256, 512x512, 1024x1024
            )
            image_url = response["data"][0]["url"]  # 从响应中获取生成图片的 URL
            logger.info("[OPEN_AI] image_url={}".format(image_url))  # 记录生成图片的 URL
            return True, image_url # 返回成功状态和图片 URL
        except openai.error.RateLimitError as e:  # 捕获速率限制错误
            logger.warn(e) # 记录警告日志
            if retry_count < 1:  # 如果重试次数小于 1(因为初始是0,可以重试两次)
                time.sleep(5)  # 等待 5 秒后重试
                logger.warn("[OPEN_AI] ImgCreate RateLimit exceed, 第{}次重试".format(retry_count + 1))  # 记录重试日志
                return self.create_img(query, retry_count + 1) # 递归调用自己，增加重试次数
            else:  # 超过重试次数后返回错误提示
                return False, "画图出现问题，请休息一下再问我吧"
        except Exception as e: # 捕获其他异常
            logger.exception(e)  # 记录异常日志
            return False, "画图出现问题，请休息一下再问我吧" # 返回错误提示
