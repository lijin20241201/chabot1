# Translator是抽象类，用于表示翻译服务的接口。它提供了一个 translate 方法的模板，该方法应该由具体的翻译服务实现来完成实际的文本翻译工作。
class Translator(object):
    # 使用 ISO 639-1 语言代码规范指定源语言和目标语言
    # query: 需要被翻译的文本字符串。from_lang: 源语言的 ISO 639-1 代码，默认为空字符串（意味着自动检测源语言）
    # to_lang: 目标语言的 ISO 639-1 代码，默认为 "en"，即英语。zh-CN指简体中文
    def translate(self, query: str, from_lang: str = "", to_lang: str = "zh-CN") -> str:
       
        raise NotImplementedError