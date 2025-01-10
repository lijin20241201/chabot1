# 从本地模块中导入相关的组件加载函数
from .contact import load_contact  # 导入联系人模块中的 load_contact 函数
from .hotreload import load_hotreload # 导入热加载模块中的 load_hotreload 函数
from .login import load_login # 导入登录模块中的 load_login 函数
from .messages import load_messages # 导入消息模块中的 load_messages 函数
from .register import load_register  # 导入注册模块中的 load_register 函数

# 加载核心组件的函数，负责将不同的子模块加载到核心系统中。
def load_components(core):
    load_contact(core)  # 加载联系人相关的组件，传递核心对象 `core`
    load_hotreload(core) # 加载热加载组件，传递核心对象 `core`
    load_login(core) # 加载登录组件，传递核心对象 `core`
    load_messages(core)  # 加载消息相关的组件，传递核心对象 `core`
    load_register(core)  # 加载注册相关的组件，传递核心对象 `core`
