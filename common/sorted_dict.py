import heapq # 导入heapq模块，用于实现堆排序功能


class SortedDict(dict): # 定义一个继承自dict的类SortedDict
    # 初始化方法，默认按键排序，参数：
    # sort_func：排序函数，默认按键排序
    # init_dict：初始化字典，默认空列表
    # reverse：是否反转排序，默认不反转
    def __init__(self, sort_func=lambda k, v: k, init_dict=None, reverse=False):
        if init_dict is None: # 如果没有提供初始化字典，设置为空列表
            init_dict = []
        if isinstance(init_dict, dict): # 如果提供的初始化字典是字典类型
            init_dict = init_dict.items() # 转换为字典的项列表（键值对）
        self.sort_func = sort_func # 排序函数
        self.sorted_keys = None # 存储排序后的键列表，默认是None
        self.reverse = reverse # 排序时是否反转
        self.heap = [] # 用一个堆（heap）来保持元素的优先级
        for k, v in init_dict: # 遍历初始化字典中的键值对
            self[k] = v # 使用__setitem__方法添加到字典中
    # 覆盖dict的__setitem__方法，用于设置字典中的元素
    def __setitem__(self, key, value):
        if key in self: # 如果键已存在
            super().__setitem__(key, value)  # 更新字典中的值
            for i, (priority, k) in enumerate(self.heap): # 遍历堆
                if k == key: # 找到对应的键
                    self.heap[i] = (self.sort_func(key, value), key)  # 更新堆中的优先级
                    heapq.heapify(self.heap) # 重新调整堆
                    break
            self.sorted_keys = None # 清空已排序的键列表，因为堆发生变化
        else: # 如果键不存在
            super().__setitem__(key, value)  # 添加新的键值对到字典
            heapq.heappush(self.heap, (self.sort_func(key, value), key))  # 将新的键值对添加到堆中
            self.sorted_keys = None # 清空已排序的键列表
    # 覆盖dict的__delitem__方法，用于删除字典中的元素
    def __delitem__(self, key):
        super().__delitem__(key) # 删除字典中的键值对
        for i, (priority, k) in enumerate(self.heap):  # 遍历堆
            if k == key: # 找到对应的键
                del self.heap[i] # 删除堆中的元素
                heapq.heapify(self.heap) # 重新调整堆
                break
        self.sorted_keys = None # 清空已排序的键列表
    # 返回排序后的键列表
    def keys(self):
        if self.sorted_keys is None: # 如果排序后的键列表还没有生成
            self.sorted_keys = [k for _, k in sorted(self.heap, reverse=self.reverse)] # 对堆中的键进行排序
        return self.sorted_keys  # 返回排序后的键列表
    # 返回排序后的键值对列表
    def items(self):
        if self.sorted_keys is None: # 如果排序后的键列表还没有生成
            self.sorted_keys = [k for _, k in sorted(self.heap, reverse=self.reverse)]  # 对堆中的键进行排序
        sorted_items = [(k, self[k]) for k in self.sorted_keys] # 根据排序后的键获取键值对
        return sorted_items # 返回排序后的键值对列表
    # 更新堆中的优先级（私有方法）
    def _update_heap(self, key):
        for i, (priority, k) in enumerate(self.heap): # 遍历堆
            if k == key: # 找到对应的键
                new_priority = self.sort_func(key, self[key]) # 计算新的优先级
                if new_priority != priority: # 如果新的优先级和旧的不同
                    self.heap[i] = (new_priority, key) # 更新堆中的优先级
                    heapq.heapify(self.heap) # 重新调整堆
                    self.sorted_keys = None # 清空已排序的键列表
                break
    # 返回键的迭代器，支持迭代操作
    def __iter__(self):
        return iter(self.keys()) # 返回排序后的键的迭代器
    # 返回SortedDict对象的字符串表示
    def __repr__(self):
        return f"{type(self).__name__}({dict(self)}, sort_func={self.sort_func.__name__}, reverse={self.reverse})"
