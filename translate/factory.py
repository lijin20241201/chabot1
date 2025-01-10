# 根据给定的翻译服务类型创建对应的翻译服务实例。
# translator_type: 指定要创建的翻译服务类型
def create_translator(translator_type):
    # translator_type: 指定要创建的翻译服务类型
    if translator_type == "baidu":
        from translate.baidu.baidu_translate import BaiduTranslator
        return BaiduTranslator() # 创建百度翻译服务实例
    # 如果不是已知的类型, 抛出运行时错误
    raise RuntimeError