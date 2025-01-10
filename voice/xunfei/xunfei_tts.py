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
import websocket  # 导入websocket模块，用于WebSocket通信
import datetime # 导入datetime模块，用于日期和时间相关操作
import hashlib # 导入hashlib模块，用于加密操作（如hmac-sha256）
import base64 # 导入base64模块，用于编码和解码操作
import hmac # 导入hmac模块，用于HMAC（哈希消息认证码）操作
import json # 导入json模块，用于JSON数据的解析和生成
from urllib.parse import urlencode # 导入urlencode函数，用于将字典转换为URL参数
import time # 导入time模块，用于时间相关操作
import ssl # 导入ssl模块，用于SSL连接（加密）
from wsgiref.handlers import format_date_time # 导入WSGI处理模块中的时间格式化函数
from datetime import datetime  # 导入datetime模块，用于获取当前日期时间
from time import mktime # 导入mktime函数，将时间元组转换为时间戳
import _thread as thread  # 导入_thread模块用于多线程操作
import os # 导入os模块，用于文件和操作系统相关操作

# 定义常量，标识不同状态的帧
STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识
# 这两个全局变量用来设置输出文件路径和wsParam对象
global outfile
global wsParam

class Ws_Param(object): # 定义Ws_Param类，存储API请求的参数
    # 初始化方法，接受必需的API信息和文本数据
    def __init__(self, APPID, APIKey, APISecret,BusinessArgs,Text):
        self.APPID = APPID  # 设置应用ID
        self.APIKey = APIKey # 设置API Key
        self.APISecret = APISecret # 设置API Secret
        self.BusinessArgs = BusinessArgs # 设置业务参数
        self.Text = Text # 设置要转换为语音的文本
        # 公共参数，用于请求时传递应用ID
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数，包含了具体的业务设置
        #self.BusinessArgs = {"aue": "raw", "auf": "audio/L16;rate=16000", "vcn": "xiaoyan", "tte": "utf8"}
        # 对文本进行Base64编码
        self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-8')), "UTF8")}
        #使用小语种须使用以下方式，此处的unicode指的是 utf16小端的编码方式，即"UTF-16LE"”
        #self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-16')), "UTF8")}

    # 创建请求URL的方法
    def create_url(self):
        url = 'wss://tts-api.xfyun.cn/v2/tts' # 设置WebSocket连接的URL
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 构造签名字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/tts " + "HTTP/1.1"
        # 使用hmac-sha256算法对签名进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')
        # 创建授权字符串
        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        # 将鉴权参数组成字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        # 拼接鉴权参数到URL中
        url = url + '?' + urlencode(v)
        # print("date: ",date)
        # print("v: ",v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        # print('websocket url :', url)
        return url  # 返回生成的URL

# WebSocket收到消息后的回调函数
def on_message(ws, message):
    #输出文件
    global outfile # 使用全局变量outfile来保存语音文件
    try:
        message =json.loads(message)  # 将接收到的消息解析为JSON
        code = message["code"] # 获取返回的状态码
        sid = message["sid"] # 获取会话ID
        audio = message["data"]["audio"] # 获取音频数据
        audio = base64.b64decode(audio)  # 将音频数据从Base64解码
        status = message["data"]["status"]  # 获取消息状态
        if status == 2: # 如果状态为2，表示WebSocket已关闭
            print("ws is closed")
            ws.close() # 关闭WebSocket连接
        if code != 0:  # 如果返回的状态码不是0，表示发生错误
            errMsg = message["message"]
            print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))
        else: # 将音频数据写入到指定的输出文件
            with open(outfile, 'ab') as f:
                f.write(audio)
    except Exception as e:
        print("receive msg,but parse exception:", e) # 捕获并打印异常

# 收到websocket连接建立的处理
def on_open(ws):
    global outfile
    global wsParam
    def run(*args):
        # 准备发送的消息数据，包含公共参数、业务参数和数据
        d = {"common": wsParam.CommonArgs,
             "business": wsParam.BusinessArgs,
             "data": wsParam.Data,
             }
        d = json.dumps(d) # 将数据转换为JSON字符串
        # print("------>开始发送文本数据")
        ws.send(d)  # 发送数据
        if os.path.exists(outfile):  # 如果输出文件已存在，则删除
            os.remove(outfile)
    # 启动一个新线程来发送请求数据
    thread.start_new_thread(run, ())

# 收到websocket错误的处理
def on_error(ws, error):
    print("### error:", error)  # 打印错误信息

# 收到websocket关闭的处理
def on_close(ws):
    print("### closed ###") # 打印关闭信息

# 主函数，用于启动WebSocket连接并开始语音合成
def xunfei_tts(APPID, APIKey, APISecret,BusinessArgsTTS, Text, OutFile):
    global outfile
    global wsParam 
    outfile = OutFile # 设置输出文件路径
    wsParam1 = Ws_Param(APPID,APIKey,APISecret,BusinessArgsTTS,Text) # 创建Ws_Param对象
    wsParam = wsParam1 # 设置全局变量wsParam
    websocket.enableTrace(False) # 禁用WebSocket调试输出
    wsUrl = wsParam.create_url() # 生成WebSocket连接的URL
    # 创建WebSocket连接对象
    ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.on_open = on_open # 设置连接打开时的回调函数
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}) # 启动WebSocket连接，忽略SSL证书验证
    return outfile  # 返回输出文件路径
     