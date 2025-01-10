# 根据voice_type参数创建不同类型的语音合成服务实例
def create_voice(voice_type):
    if voice_type == "baidu":
        from voice.baidu.baidu_voice import BaiduVoice # 创建百度语音合成服务实例
        return BaiduVoice()
    elif voice_type == "google":
        from voice.google.google_voice import GoogleVoice
        return GoogleVoice() # 创建Google语音合成服务实例
    elif voice_type == "openai":
        from voice.openai.openai_voice import OpenaiVoice
        return OpenaiVoice() # 创建OpenAI语音合成服务实例
    elif voice_type == "pytts":
        from voice.pytts.pytts_voice import PyttsVoice
        return PyttsVoice() # 创建基于pyttsx3库的本地语音合成服务实例
    elif voice_type == "azure":
        from voice.azure.azure_voice import AzureVoice
        return AzureVoice()# 创建Azure语音合成服务实例
    elif voice_type == "elevenlabs":
        from voice.elevent.elevent_voice import ElevenLabsVoice
        return ElevenLabsVoice() # 创建ElevenLabs语音合成服务实例
    elif voice_type == "linkai":
        from voice.linkai.linkai_voice import LinkAIVoice
        return LinkAIVoice() # 创建LinkAI语音合成服务实例
    elif voice_type == "ali":
        from voice.ali.ali_voice import AliVoice
        return AliVoice() # 创建阿里云语音合成服务实例
    elif voice_type == "edge":
        from voice.edge.edge_voice import EdgeVoice
        return EdgeVoice() # 创建Edge TTS语音合成服务实例
    elif voice_type == "xunfei":
        from voice.xunfei.xunfei_voice import XunfeiVoice
        return XunfeiVoice() # 创建讯飞语音合成服务实例
    # 如果voice_type不匹配任何已知类型，则抛出运行时错误
    raise RuntimeError 