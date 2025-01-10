# coding=utf-8

import http.client
import json
import time
import requests
import datetime
import hashlib
import hmac
import base64
import urllib.parse
import uuid
from common.log import logger
from common.tmp_dir import TmpDir

# 使用阿里云的文本转语音服务将文本转换为语音。
# url (str): 阿里云文本转语音服务的端点URL。text (str): 要转换为语音的文本。
# appkey (str): 您的阿里云appkey。token (str): 阿里云API的认证令牌。
def text_to_speech_aliyun(url, text, appkey, token):
    # 设置 Content-Type 为 application/json
    # 这样服务器就知道发送的是 JSON 数据，而不是普通的表单数据。
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "text": text,
        "appkey": appkey,
        "token": token,
        "format": "wav"
    }
    # json.dumps(data) 会将一个 Python 字典（如 data）转换为 JSON 字符串。requests.post 方法将这个 JSON 字符串
    # 作为请求的主体 (data) 发送到服务器。
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200 and response.headers['Content-Type'] == 'audio/mpeg':
        # 要保存的声音文件临时路径
        output_file = TmpDir().path() + "reply-" + str(int(time.time())) + "-" + str(hash(text) & 0x7FFFFFFF) + ".wav"
        with open(output_file, 'wb') as file:
            file.write(response.content)
        logger.debug(f"音频文件保存成功，文件名：{output_file}")
    else:
        logger.debug("响应状态码: {}".format(response.status_code))
        logger.debug("响应内容: {}".format(response.text))
        output_file = None
    # 成功时输出音频文件的路径，否则为None。
    return output_file
# 这个函数的作用是调用阿里云的语音识别服务，将 PCM 格式的音频文件转换成文本。
# url (str): 阿里云语音识别服务的端点URL。audioContent (byte): pcm音频数据。
# PCM（Pulse Code Modulation，脉冲编码调制） 是一种常见的音频数据格式，它是数字音频的一种基本表示方法，广泛应用于音频存储、传输和处理。
# PCM 格式的语音是未压缩的原始音频数据，以连续的采样值（通常是量化后的数字值）表示声音波形。
def speech_to_text_aliyun(url, audioContent, appkey, token):
    format = 'pcm' # 音频格式，阿里云要求是 PCM 格式
    sample_rate = 16000 # 音频采样率，通常是 16000 Hz。
    enablePunctuationPrediction  = True # 是否启用标点符号预测。设置为 True 表示在识别结果中加入标点。
    enableInverseTextNormalization = True # 是否启用文本反标准化。该选项将对识别的文本进行反向标准化（比如将阿拉伯数字转换为中文数字）。
    enableVoiceDetection  = False # 是否启用语音检测。语音检测可以在音频中自动识别并排除沉默段。
    # 构造 RESTful 请求 URL:这个 URL 包含了所有的查询参数，如应用程序密钥、音频格式、采样率以及其他设置选项。
    request = url + '?appkey=' + appkey
    request = request + '&format=' + format
    request = request + '&sample_rate=' + str(sample_rate)
    if enablePunctuationPrediction :
        request = request + '&enable_punctuation_prediction=' + 'true'
    if enableInverseTextNormalization :
        request = request + '&enable_inverse_text_normalization=' + 'true'
    if enableVoiceDetection :
        request = request + '&enable_voice_detection=' + 'true'
    host = 'nls-gateway-cn-shanghai.aliyuncs.com'
    # 请求头部设置了：
    # 'X-NLS-Token'：身份验证令牌，token 作为身份认证的凭证。
    # 'Content-type'：设置请求体的内容类型为 application/octet-stream，表示音频数据的二进制流。
    # 'Content-Length'：音频内容的字节数，即请求体的大小。
    httpHeaders = {
        'X-NLS-Token': token,
        'Content-type': 'application/octet-stream',
        'Content-Length': len(audioContent)
        }
    # 使用 http.client.HTTPSConnection 创建与阿里云服务的 HTTPS 连接。
    conn = http.client.HTTPSConnection(host)
    # 使用 conn.request 方法发送一个 POST 请求，传递音频数据 (audioContent) 和构造的请求头。
    conn.request(method='POST', url=request, body=audioContent, headers=httpHeaders)
    # getresponse() 获取服务器的响应。response.read() 读取响应的内容，通常是一个包含识别结果的
    # JSON 格式的字符串。
    response = conn.getresponse()
    body = response.read()
    # 成功时输出识别到的文本，否则为None
    # 无论是成功还是失败，都会关闭与服务器的连接。
    try:
        body = json.loads(body) # json.loads(body) 将响应的 JSON 字符串解析为 Python 字典。
        status = body['status']
        # status 字段表示 API 请求的状态码，20000000 表示请求成功。如果成功，返回识别的文本（body['result']）。
        if status == 20000000 :
            result = body['result']
            if result :
                logger.info(f"阿里云语音识别到了：{result}")
            conn.close()
            return result
        else :
            logger.error(f"语音识别失败，状态码: {status}") # 如果请求失败，会根据状态码记录错误日志。
    except ValueError:
        logger.error(f"语音识别失败，收到非JSON格式的数据: {body}")
    conn.close()
    return None
# 用于生成阿里云服务认证令牌的类。
class AliyunTokenGenerator:
    # access_key_id (str): 您的阿里云访问密钥ID。access_key_secret (str): 您的阿里云访问密钥秘密。
    # 初始化时传入阿里云的 access_key_id 和 access_key_secret，并将它们存储在实例变量中。
    def __init__(self, access_key_id, access_key_secret):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
    # sign_request 方法负责根据阿里云的签名规范，为请求参数生成签名（即签章），以确保请求的合法性和安全性。
    def sign_request(self, parameters):
        # 将传入的 parameters 字典按字典顺序（键的字母顺序）排序，返回一个 sorted_params 列表，列表中的每
        # 个元素是一个元组 (key, value)。
        sorted_params = sorted(parameters.items())
        # 构造待签名的查询字符串
        canonicalized_query_string = ''
        # 遍历排序后的参数列表，将每个键值对进行百分比编码，并按 key=value 的格式拼接成一个查询字符串。
        # self.percent_encode(k) 和 self.percent_encode(v) 是调用下面定义的 percent_encode 方法，对键和值进行URL编码，确保在URL中合法。
        for (k, v) in sorted_params:
            canonicalized_query_string += '&' + self.percent_encode(k) + '=' + self.percent_encode(v)
        # 构造用于签名的字符串,阿里云的签名规范要求使用 GET 方法和 / 根路径。
        # canonicalized_query_string[1:] 从字符串的第二个字符开始（去除前面的 &），然后对其进行编码。
        string_to_sign = 'GET&%2F&' + self.percent_encode(canonicalized_query_string[1:])  # 使用GET方法
        # 使用 HMAC 算法和 SHA1 散列算法生成签名。HMAC 算法使用 access_key_secret 与待签名的字符串 string_to_sign 进行签名。
        # key 参数是用于 HMAC 运算的密钥。在这个例子中，密钥是你从阿里云账户获得的 access_key_secret（访问密钥的秘密部分），加上一个 & 符号。
        # msg 参数,string_to_sign.encode('utf-8') 将该字符串转换为字节串，因为 HMAC 运算要求输入的消息也必须是字节串。
        # digestmod 是用于哈希计算的算法。这个参数指定了使用什么哈希算法来生成签名。在阿里云的签名规范中，要求使用 SHA-1（
        # hashlib.sha1）算法对消息和密钥进行哈希计算，生成签名。
        # 非对称加密中的密钥：有一对密钥，公钥和私钥，公钥用于加密，私钥用于解密。
        # 常见算法：RSA、ECC（椭圆曲线加密）、DSA（数字签名算法）。
        # HMAC 使用的密钥是对称密钥，即加密和解密过程中使用相同的密钥。它与非对称加密（如 RSA）不同，非对称加密中有一对密钥：公钥和私钥，
        # 而 HMAC 只依赖于一个共享的密钥。
        # HMAC 密钥通常是固定的，并且会在一段时间内保持不变，用于生成消息的认证码。
        # 密钥轮换是提高安全性的常见做法，定期更换密钥可以降低密钥泄露的风险。
        h = hmac.new((self.access_key_secret + "&").encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
        # base64.encodebytes(h.digest()).strip() 对生成的签名进行 Base64 编码，并去掉末尾的换行符。
        signature = base64.encodebytes(h.digest()).strip()
        return signature
    # percent_encode 方法对输入的字符串 encode_str 进行百分比编码。阿里云的签名规则要求对某些字符进行特定的编码
    def percent_encode(self, encode_str):
        encode_str = str(encode_str)
        res = urllib.parse.quote(encode_str, '') # 使用 urllib.parse.quote 对字符串进行基本的 URL 编码。
        res = res.replace('+', '%20') # 将 + 替换为 %20，表示空格；
        res = res.replace('*', '%2A') # 将 * 替换为 %2A；
        res = res.replace('%7E', '~') # 将 %7E 替换为 ~；
        return res
    # get_token 方法负责构造请求参数并获取阿里云服务的令牌。
    def get_token(self):
        # 这部分构造了请求参数字典。阿里云的API需要这些固定的参数，此外，还包括：
        # 这个随机数的作用是防止重复请求，从而保证请求的唯一性，避免被阿里云服务器判定为重放攻击（replay attack）
       # 使用**一次性令牌（Nonce）**来防止重放攻击。Nonce 是一个在每次请求中唯一的、不可重复的随机数或计数器。每次客户端发出的请求
       #  都会带上一个新的 nonce，服务器会验证该 nonce 是否已经使用过。如果发现已经使用过的 nonce，服务器将拒绝请求。
        # 服务器接收到请求时验证 nonce
        # 查找已使用的 nonce：服务器会检查该请求中携带的 nonce 是否已经在之前的请求中使用过。
        # 如果 nonce 已存在：这表示该请求可能是一个重放攻击，服务器会拒绝该请求，避免重复操作（如重复的支付或认证请求）。
        # 如果 nonce 不存在：服务器将该 nonce 标记为已使用，并继续处理请求
        params = {
            'Format': 'JSON', # 返回的结果格式，通常为 JSON；
            'Version': '2019-02-28', # API 的版本；
            'AccessKeyId': self.access_key_id, # 用户的阿里云 access_key_id
            'SignatureMethod': 'HMAC-SHA1', # 签名方法，这里使用 HMAC-SHA1；
            'Timestamp': datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),# 当前 UTC 时间；
            'SignatureVersion': '1.0',  # 签名版本
            'SignatureNonce': str(uuid.uuid4()),  # 使用uuid生成唯一的随机数,防止重放攻击；
            'Action': 'CreateToken', # 指定调用的API动作，这里是 CreateToken；
            'RegionId': 'cn-shanghai' # 指定区域，这里使用的是上海 cn-shanghai。
        }

        # 计算请求的签名，并将签名加入到 params 字典中。
        signature = self.sign_request(params)
        params['Signature'] = signature
        # 将请求参数字典转换为URL查询字符串，并构造完整的请求URL。
        url = 'http://nls-meta.cn-shanghai.aliyuncs.com/?' + urllib.parse.urlencode(params)
        # 使用 requests.get 发送HTTP GET请求。
        response = requests.get(url)
        # 返回请求的响应内容，即阿里云返回的认证令牌信息。
        return response.text