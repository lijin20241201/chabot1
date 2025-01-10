# 定义一个装饰器函数，用于实现单例模式，cls是被装饰的类
def singleton(cls):
    instances = {} # 用一个字典来存储已经创建的实例，键是类，值是实例对象
    # 定义一个内部函数，用来获取类的实例
    def get_instance(*args, **kwargs):
        # 如果这个类的实例还没有创建过
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs) # 创建实例并存储到字典中
        return instances[cls] # 返回已创建的实例，保证返回的是同一个实例

    return get_instance  # 返回内部函数，这样外部调用时会使用这个函数来获取实例
