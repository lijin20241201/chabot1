# -*- coding:utf-8 -*-
#
#  Author: njnuko 
#  Email: njnuko@163.com 
#
#  这个文档是基于官方的demo来改的，固体官方demo文档请参考官网
#
#  语音听写流式 WebAPI 接口调用示例 接口文档（必看）：https://doc.xfyun.cn/rest_api/语音听写（流式版）.html
#  webapi 听写服务参考帖子（必看）：http://bbs.xfyun.cn/forum.php?mod=viewthread&tid=38947&extra=
#  语音听写流式WebAPI 服务，热词使用方式：登陆开放平台https://www.xfyun.cn/后，找到控制台--我的应用---语音听写（流式）---服务管理--个性化热词，
#  设置热词
#  注意：热词只能在识别的时候会增加热词的识别权重，需要注意的是增加相应词条的识别率，但并不是绝对的，具体效果以您测试为准。
#  语音听写流式WebAPI 服务，方言试用方法：登陆开放平台https://www.xfyun.cn/后，找到控制台--我的应用---语音听写（流式）---服务管理--识别语种列表
#  可添加语种或方言，添加后会显示该方言的参数值
#  错误码链接：https://www.xfyun.cn/document/error-code （code返回错误码时必看）
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import time
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
import os
import wave


STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识

#############
# whole_dict 用来存储音频识别的返回值，随着音频帧的处理，会不断更新
global whole_dict
# wsParam 是用来保存 WebSocket 连接参数的全局变量
global wsParam
##############


class Ws_Param(object):
    # 初始化 WebSocket 参数
    def __init__(self, APPID, APIKey, APISecret,BusinessArgs, AudioFile):
        self.APPID = APPID # 应用 ID
        self.APIKey = APIKey # API 密钥
        self.APISecret = APISecret # API 秘钥
        self.AudioFile = AudioFile # 音频文件路径
        self.BusinessArgs = BusinessArgs # 业务参数
        # 公共参数
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数（可以根据需要调整）
        #self.BusinessArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo":1,"vad_eos":10000}

    # 生成 WebSocket 连接 URL，包含鉴权信息
    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat' # WebSocket URL
        # 获取当前时间并格式化为 RFC1123 格式
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接签名字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"
        # 使用 HMAC-SHA256 加密算法生成签名
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')
        # 生成授权信息
        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        # 拼接完整的鉴权参数
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        # 拼接 URL 和鉴权参数
        url = url + '?' + urlencode(v)
        #print("date: ",date)
        #print("v: ",v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        #print('websocket url :', url)
        return url


# 收到 WebSocket 消息的处理函数
def on_message(ws, message):
    global whole_dict
    try:
        code = json.loads(message)["code"] # 解析返回的 JSON 消息
        sid = json.loads(message)["sid"]
        if code != 0: # 如果返回的 code 不为 0，表示出错
            errMsg = json.loads(message)["message"]
            print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))
        else:
            temp1 = json.loads(message)["data"]["result"]
            data = json.loads(message)["data"]["result"]["ws"]
            sn = temp1["sn"]
            if "rg" in temp1.keys(): # 如果有“rg”字段，说明是需要拼接的结果
                rep = temp1["rg"]
                rep_start = rep[0]
                rep_end = rep[1]
                for sn in range(rep_start,rep_end+1):
                    #print("before pop",whole_dict)
                    #print("sn",sn)
                    whole_dict.pop(sn,None) # 删除之前存储的识别结果，避免重复
                    #print("after pop",whole_dict)
                results = ""
                for i in data:
                    for w in i["cw"]:
                        results += w["w"]
                whole_dict[sn]=results # 更新识别结果
                #print("after add",whole_dict)
            else:
                results = ""
                for i in data:
                    for w in i["cw"]:
                        results += w["w"]
                whole_dict[sn]=results
            #print("sid:%s call success!,data is:%s" % (sid, json.dumps(data, ensure_ascii=False)))
    except Exception as e:
        print("receive msg,but parse exception:", e)



# WebSocket 错误处理函数
def on_error(ws, error):
    print("### error:", error)


# WebSocket 连接关闭时的处理函数
def on_close(ws,a,b):
    print("### closed ###")


# WebSocket 连接建立时的处理函数
def on_open(ws):
    global wsParam
    def run(*args):
        frameSize = 8000  # 每帧音频的大小
        intervel = 0.04  # 每帧音频发送的间隔（单位：秒）
        status = STATUS_FIRST_FRAME  # 设置音频状态为第一帧
        # fp.readframes(frameSize) 会把音频文件中的数据分成一个个大小为 frameSize 的数据块来读取，因此 frameSize
        # 实际上表示每次从音频文件中读取的音频帧的大小。
        with wave.open(wsParam.AudioFile, "rb") as fp: # 读取音频文件
            while True:
                buf = fp.readframes(frameSize)
                # 文件结束
                # 这个判断是用于标识整个音频文件是否已经读取完毕，表示 文件的结束。
                if not buf:   # 如果读取到文件末尾，设置为最后一帧
                    status = STATUS_LAST_FRAME
                # 第一帧处理
                # 发送第一帧音频，带business 参数
                # appid 必须带上，只需第一帧发送
                if status == STATUS_FIRST_FRAME:  # 处理第一帧
                    d = {"common": wsParam.CommonArgs,
                         "business": wsParam.BusinessArgs,
                         "data": {"status": 0, "format": "audio/L16;rate=16000","audio": str(base64.b64encode(buf), 'utf-8'), "encoding": "raw"}} 
                    d = json.dumps(d)
                    ws.send(d)  # 发送第一帧
                    status = STATUS_CONTINUE_FRAME
                 # 处理中间帧
                elif status == STATUS_CONTINUE_FRAME:
                    d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                                  "audio": str(base64.b64encode(buf), 'utf-8'),
                                  "encoding": "raw"}}
                    ws.send(json.dumps(d))
                 # 处理最后一帧
                elif status == STATUS_LAST_FRAME:
                    d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                                  "audio": str(base64.b64encode(buf), 'utf-8'),
                                  "encoding": "raw"}}
                    ws.send(json.dumps(d)) # 发送最后一帧
                    time.sleep(1) # 等待一秒，确保最后一帧被处理完
                    break # 退出while循环
                 # 模拟音频采样间隔
                time.sleep(intervel)
        ws.close() # 关闭 WebSocket 连接
    # 启动一个新的线程，执行音频数据发送
    thread.start_new_thread(run, ())

# 提供给外部调用的函数，进行语音识别
def xunfei_asr(APPID,APISecret,APIKey,BusinessArgsASR,AudioFile):
    global whole_dict
    global wsParam
    whole_dict = {} # 初始化存储识别结果的字典
    wsParam1 = Ws_Param(APPID=APPID, APISecret=APISecret,
                       APIKey=APIKey,BusinessArgs=BusinessArgsASR,
                       AudioFile=AudioFile)
    # 将 Ws_Param 对象赋值给全局变量，供 on_open 使用
    wsParam = wsParam1
    websocket.enableTrace(False) # 禁用调试信息
    wsUrl = wsParam.create_url() # 生成 WebSocket URL
    ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close) # 创建 WebSocket 连接
    ws.on_open = on_open # 设置连接建立时的处理函数
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}) # 开始 WebSocket 连接并接收消息
    # 合并识别结果，返回最终的识别文本
    whole_words = ""
    for i in sorted(whole_dict.keys()):
        whole_words += whole_dict[i]
    return whole_words
    