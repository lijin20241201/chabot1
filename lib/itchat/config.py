import os, platform

VERSION = '1.5.0.dev' # 表示当前应用的版本号为 1.5.0.dev
# 这通常用于控制是否启用异步功能。
ASYNC_COMPONENTS = os.environ.get('ITCHAT_UOS_ASYNC', False)
# 定义一个常量 BASE_URL，表示微信登录相关的基础 URL
BASE_URL = 'https://login.weixin.qq.com'
OS = platform.system() # 使用 platform.system() 获取当前操作系统的名称。
# 使用 os.getcwd() 获取当前工作目录的路径（即程序执行时的当前文件夹路径）。
DIR = os.getcwd()
# 表示默认的二维码文件名 QR.png。这是用来保存微信登录二维码的文件。
DEFAULT_QR = 'QR.png'
# 定义一个常量 TIMEOUT，表示请求的超时时间设置。该元组包含两个值,10 秒是连接超时时间,60 秒是读取超时时间。
TIMEOUT = (10, 60)
# 定义一个常量 USER_AGENT，表示请求头中的 User-Agent 字段的值，模拟一个浏览器请求。这通常用来避免请求被识别为非浏览器请求，模拟正常的浏览器访问。
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.71 Safari/537.36'
# 定义一个常量 UOS_PATCH_CLIENT_VERSION，表示某个补丁版本的客户端版本为 2.0.0。这个版本号可能用于标识特定版本的补丁。
UOS_PATCH_CLIENT_VERSION = '2.0.0'
UOS_PATCH_EXTSPAM = 'Go8FCIkFEokFCggwMDAwMDAwMRAGGvAESySibk50w5Wb3uTl2c2h64jVVrV7gNs06GFlWplHQbY/5FfiO++1yH4ykCyNPWKXmco+wfQzK5R98D3so7rJ5LmGFvBLjGceleySrc3SOf2Pc1gVehzJgODeS0lDL3/I/0S2SSE98YgKleq6Uqx6ndTy9yaL9qFxJL7eiA/R3SEfTaW1SBoSITIu+EEkXff+Pv8NHOk7N57rcGk1w0ZzRrQDkXTOXFN2iHYIzAAZPIOY45Lsh+A4slpgnDiaOvRtlQYCt97nmPLuTipOJ8Qc5pM7ZsOsAPPrCQL7nK0I7aPrFDF0q4ziUUKettzW8MrAaiVfmbD1/VkmLNVqqZVvBCtRblXb5FHmtS8FxnqCzYP4WFvz3T0TcrOqwLX1M/DQvcHaGGw0B0y4bZMs7lVScGBFxMj3vbFi2SRKbKhaitxHfYHAOAa0X7/MSS0RNAjdwoyGHeOepXOKY+h3iHeqCvgOH6LOifdHf/1aaZNwSkGotYnYScW8Yx63LnSwba7+hESrtPa/huRmB9KWvMCKbDThL/nne14hnL277EDCSocPu3rOSYjuB9gKSOdVmWsj9Dxb/iZIe+S6AiG29Esm+/eUacSba0k8wn5HhHg9d4tIcixrxveflc8vi2/wNQGVFNsGO6tB5WF0xf/plngOvQ1/ivGV/C1Qpdhzznh0ExAVJ6dwzNg7qIEBaw+BzTJTUuRcPk92Sn6QDn2Pu3mpONaEumacjW4w6ipPnPw+g2TfywJjeEcpSZaP4Q3YV5HG8D6UjWA4GSkBKculWpdCMadx0usMomsSS/74QgpYqcPkmamB4nVv1JxczYITIqItIKjD35IGKAUwAA=='
