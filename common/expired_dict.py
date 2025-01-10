from datetime import datetime, timedelta
# 一个设置有缓存有效期的字典
class ExpiredDict(dict):
    def __init__(self, expires_in_seconds):  # 初始化方法，接受过期时间（秒）
        super().__init__() # 调用父类字典的初始化方法
        self.expires_in_seconds = expires_in_seconds # 设置过期时间（秒）
     # 获取字典中的元素，如果元素已过期则抛出异常
    def __getitem__(self, key):
        value, expiry_time = super().__getitem__(key)  # 获取值和过期时间
        if datetime.now() > expiry_time: # 如果当前时间大于过期时间
            del self[key] # 删除该键值对
            raise KeyError("expired {}".format(key))  # 抛出过期异常
        self.__setitem__(key, value) # 更新过期时间
        return value # 返回值
     # 设置字典中的元素，保存值和过期时间
    def __setitem__(self, key, value):
        expiry_time = datetime.now() + timedelta(seconds=self.expires_in_seconds)
        super().__setitem__(key, (value, expiry_time))  # 存储值和过期时间
    # 获取字典中的元素，若不存在或已过期则返回默认值
    def get(self, key, default=None):
        try:
            return self[key] # 尝试获取元素
        except KeyError:
            return default  # 如果元素不存在或已过期，返回默认值
    # 检查字典中是否存在某个键，并且未过期
    def __contains__(self, key):
        try:
            self[key]  # 尝试获取元素
            return True  # 如果能获取，表示存在
        except KeyError:
            return False  # 如果抛出异常，表示不存在或已过期
     # 获取字典中所有存在且未过期的键
    def keys(self):
        keys = list(super().keys()) # 获取所有的键
        return [key for key in keys if key in self] # 只返回未过期的键
    # 获取字典中所有存在且未过期的键值对
    def items(self):
        return [(key, self[key]) for key in self.keys()]  # 返回未过期的键值对
    # 获取字典中所有未过期的键的迭代器
    def __iter__(self):
        return self.keys().__iter__()  # 返回未过期的键的迭代器
