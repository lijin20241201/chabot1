# 这个代码片段定义了一个名为 Voice 的抽象类，它为语音服务提供了两个方法的接口：voiceToText 和 textToVoice。
class Voice(object):
    # 该方法在基类 Voice 中并没有实际的实现，而是一个抽象方法。
    # 抽象方法通过 raise NotImplementedError 来表明，任何继承了这个 Voice 类的子类都必须提供自己的实现。
    # 语音转文本
    def voiceToText(self, voice_file):
        
        raise NotImplementedError
    # 文本转语音
    def textToVoice(self, text):
        raise NotImplementedError