#coding=utf8
TRANSLATE = 'Chinese'
# ReturnValue类继承自dict，用于封装服务器返回的数据，并且提供了布尔值转换和错误信息的本地化功能。
class ReturnValue(dict):
    '''将itchat的返回值转化为布尔值
        对于requests库的请求：
            ..code::python
                import requests
                r = requests.get('http://httpbin.org/get')
                print(ReturnValue(rawResponse=r))
        对于普通字典：
            ..code::python
                returnDict = {
                    'BaseResponse': {
                        'Ret': 0,
                        'ErrMsg': 'My error msg', }, }
                print(ReturnValue(returnDict))
    '''
     # 如果提供了rawResponse（如requests库的返回值），则尝试解析其为字典格式
    def __init__(self, returnValueDict={}, rawResponse=None):
        if rawResponse:
            try:
                returnValueDict = rawResponse.json() # 尝试从rawResponse中解析JSON数据
            except ValueError:  # 如果解析失败，构建一个默认的字典，表示错误
                returnValueDict = {
                    'BaseResponse': {
                        'Ret': -1004,
                        'ErrMsg': 'Unexpected return value', },
                    'Data': rawResponse.content, }
        # 将返回值字典中的所有项赋值到当前实例（继承自dict）
        for k, v in returnValueDict.items():
            self[k] = v
        # 如果字典中没有'BaseResponse'，则为其设置默认值
        if not 'BaseResponse' in self:
            self['BaseResponse'] = {
                'ErrMsg': 'no BaseResponse in raw response',
                'Ret': -1000, }
        # 如果设置了TRANSLATE，进行错误消息的本地化翻译
        if TRANSLATE:
            # 保存原始错误信息，以备后用
            self['BaseResponse']['RawMsg'] = self['BaseResponse'].get('ErrMsg', '')
            # 将错误码翻译为相应的本地化错误信息
            self['BaseResponse']['ErrMsg'] = \
                TRANSLATION[TRANSLATE].get(
                self['BaseResponse'].get('Ret', '')) \
                or self['BaseResponse'].get('ErrMsg', u'No ErrMsg')
             # 如果原始错误信息为空，使用翻译后的错误信息填充
            self['BaseResponse']['RawMsg'] = \
                self['BaseResponse']['RawMsg'] or self['BaseResponse']['ErrMsg']
    # 定义了__nonzero__方法，这样可以将返回值直接作为布尔值判断
    def __nonzero__(self):
        # 判断'BaseResponse'中的'Ret'值是否为0，0表示请求成功
        return self['BaseResponse'].get('Ret') == 0
    # Python 3中使用__bool__代替__nonzero__，实现相同功能
    def __bool__(self):
        return self.__nonzero__()
    # __str__方法返回一个字符串表示，显示字典中每个键值对
    def __str__(self):
        return '{%s}' % ', '.join(
            ['%s: %s' % (repr(k),repr(v)) for k,v in self.items()])
    # __repr__方法返回对象的字符串表示，便于调试
    def __repr__(self):
        return '<ItchatReturnValue: %s>' % self.__str__()
# TRANSLATION字典用于存储错误码到中文错误信息的映射
TRANSLATION = {
    'Chinese': {
        -1000: u'返回值不带BaseResponse',  # 错误码-1000，表示缺少BaseResponse
        -1001: u'无法找到对应的成员',  # 错误码-1001，表示找不到指定成员
        -1002: u'文件位置错误', # 错误码-1002，表示文件位置错误
        -1003: u'服务器拒绝连接',  # 错误码-1003，表示服务器拒绝连接
        -1004: u'服务器返回异常值',  # 错误码-1004，表示服务器返回异常值
        -1005: u'参数错误',  # 错误码-1005，表示参数错误
        -1006: u'无效操作',  # 错误码-1006，表示无效操作
        0: u'请求成功',  # 错误码0，表示请求成功
    },
}
