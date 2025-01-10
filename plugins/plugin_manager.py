# encoding:utf-8

import importlib
import importlib.util
import json
import os
import sys

from common.log import logger
from common.singleton import singleton
from common.sorted_dict import SortedDict
from config import conf, remove_plugin_config, write_plugin_config

from .event import *

# PluginManager 类是一个用于插件管理的核心类，它负责插件的注册、配置、加载、启用、禁用、安装、卸载、更新等功能。
# 插件（Plugin） 是一种软件设计模式，它使得某个程序的功能能够通过外部代码扩展，而不需要修改程序本身的核心代码。插件通常是独立的、可替换的模块
# ，它们通过定义好的接口与宿主程序进行交互，增强或扩展宿主程序的功能。
@singleton # 单例
class PluginManager: # 插件管理
    def __init__(self):
        # 键是插件名的大写,值是插件类,按插件类的优先级从高到低排列
        self.plugins = SortedDict(lambda k, v: v.priority, reverse=True)
        self.listening_plugins = {} # 键是事件名,值是handers中有当前事件的插件的插件名列表
        self.instances = {} # 键是插件名,值是具体的插件(子类)实例
        self.pconf = {} # 存储插件原名和其对应的优先级等配置
        self.current_plugin_path = None # 当前插件的路径
        # self.loaded 用来存储已加载的插件。这个字典可以用于跟踪哪些插件已经被加载并可以执行。
        # 插件路径-->插件模块对象
        self.loaded = {}
    # register 方法用于注册插件。注册的插件会被保存到 self.plugins 字典中，并且插件的相关信息（如名称、优先级、描述、作者等）会被存储在插件类中。
    # 当你调用 register 方法并将其作为装饰器应用到一个插件类时，插件类会被装饰并注册到 self.plugins 字典中。
    # wrapper 是一个闭包，它接收插件类 plugincls 作为参数，并为插件类添加元数据。
    # plugincls 代表的是单个插件的类，而不是多个插件。
    # register 装饰器不能算作注解，但它可以实现类似注解的功能：通过传递额外的元数据（如 name、desc 等）来“标记”类，并修改类的行为。
    # 这里的 plugincls 是传递给 wrapper 装饰器的参数，它实际上代表的是一个 插件类。这个类是一个具有特定行为和方法的对象，可以被实例化成插件的实例。
    def register(self, name: str, desire_priority: int = 0, **kwargs):
        # 这个 wrapper 函数是 装饰器 的核心部分。装饰器是 Python 中的一种用于修改或增强函数或类行为的方式。装饰器可以接受一个
        # 函数（或类）作为输入，然后返回一个新的函数（或类）。
        # plugincls 是 wrapper 装饰器的参数，它代表被装饰的 插件类。
        def wrapper(plugincls): # plugincls 是一个单独的插件类，而不是一堆插件。
            plugincls.name = name # 这个属性通常表示插件的名称。
            plugincls.priority = desire_priority # 插件的优先级决定了插件加载的顺序。
            plugincls.desc = kwargs.get("desc") # 插件的描述。
            plugincls.author = kwargs.get("author") # 插件的作者。
            plugincls.path = self.current_plugin_path # 插件的路径
            # 从 kwargs 中获取 version 参数（如果存在），如果没有提供 version，则默认使用 "1.0" 作为插件版本。
            plugincls.version = kwargs.get("version") if kwargs.get("version") != None else "1.0"
            # 这一行从 kwargs 中获取 namecn 参数（插件中文名），并将其赋值给插件类的 namecn 属性。如果 namecn 不存在，则使用
            # name 作为插件的中文名。
            plugincls.namecn = kwargs.get("namecn") if kwargs.get("namecn") != None else name
            # 这一行从 kwargs 中获取 hidden 参数（如果存在），并将其赋值给插件类的 hidden 属性。如果没有提供 hidden，则默认
            # 为 False，表示插件不是隐藏的。
            plugincls.hidden = kwargs.get("hidden") if kwargs.get("hidden") != None else False
            plugincls.enabled = True # 这一行将插件类的 enabled 属性设置为 True，表示插件是启用的。
            # 这一行检查 self.current_plugin_path 是否为空。如果为空，表示当前插件的路径没有设置，抛出一个异常
            # Exception("Plugin path not set")。
            if self.current_plugin_path == None:
                raise Exception("Plugin path not set")
            self.plugins[name.upper()] = plugincls # 将插件按插件名大写做键,插件类做值放入self.plugins字典中
            # 记录一条日志，表明插件已经成功注册，并输出插件的名称、版本和路径。
            logger.info("Plugin %s_v%s registered, path=%s" % (name, plugincls.version, plugincls.path))
        return wrapper
    # 将self.pconf中保存的插件优先级之类的配置保存到文件中,这个配置是插件管理对不同插件的优先级之类的管理配置
    def save_config(self):
        # ensure_ascii=True（默认值）：所有非 ASCII 字符会被转义成 Unicode 序列。
        # ensure_ascii=False：非 ASCII 字符会以原始字符的形式输出，不会转义。如果是中文,会输出中文
        with open("./plugins/plugins.json", "w", encoding="utf-8") as f:
            json.dump(self.pconf, f, indent=4, ensure_ascii=False)
    # 这个主要是设置pconf，pconf是管理插件的优先级的配置字典
    def load_config(self):
        logger.info("Loading plugins config...") # 打印日志
        modified = False # modified 用于标记配置文件是否已被修改。初始化为 False，表示默认情况下配置文件没有被修改。
        # 使用 os.path.exists() 检查 ./plugins/plugins.json 配置文件是否存在
        if os.path.exists("./plugins/plugins.json"):
            with open("./plugins/plugins.json", "r", encoding="utf-8") as f:
                # 如果配置文件存在，打开该文件（使用 UTF-8 编码），并通过 json.load() 方法将 JSON 格式的数据解析为 Python 字典对象 pconf。
                # 这里使用 SortedDict对插件按优先级排序。
                pconf = json.load(f)
                # 倒序排序意味着 优先级大的插件 会排在 前面，优先级小的插件排在 后面。
                pconf["plugins"] = SortedDict(lambda k, v: v["priority"], pconf["plugins"], reverse=True)
        else: # 处理文件不存在的情况
            # 如果配置文件 plugins.json 不存在，设置 modified = True，表示配置已被修改（即创建了一个新的配置）。
            modified = True
            # 这里创建了一个新的字典 pconf，它包含一个键 plugins，这个键对应一个空的 SortedDict。
            # 由于没有传入 init_dict，SortedDict 默认创建了一个空的字典，并且排序是基于值中的 priority 属性。如果你之后向 
            # pconf["plugins"] 中添加元素，它会按照这个规则自动排序
            pconf = {"plugins": SortedDict(lambda k, v: v["priority"], reverse=True)}
        self.pconf = pconf
        # 保存配置文件（如果已修改）：
        # 如果配置被修改（modified 为 True），调用 save_config() 方法将配置保存到文件中。
        if modified: 
            self.save_config()
        return pconf
    # 背景: 目前插件配置存放于每个插件目录的config.json下，docker运行时不方便进行映射，故增加统一管理的入口，优先
    # 加载 plugins/config.json，原插件目录下的config.json 不受影响
    # 从 plugins/config.json 中加载全局插件配置，并写入全局插件配置字典。
    # 从 plugins/config.json 中加载所有插件的配置并写入 config.py 的全局配置中，供插件中使用
    # 插件实例中通过 config.pconf(plugin_name) 即可获取该插件的配置
    @staticmethod
    def _load_all_config():
        all_config_path = "./plugins/config.json" # 指定了全局插件配置文件的路径，plugins/config.json，这是一个统一存放所有插件配置的地方。
        try:
            if os.path.exists(all_config_path):
                # 打开文件并使用 json.load(f) 将文件内容解析为 Python 字典 all_conf。
                with open(all_config_path, "r", encoding="utf-8") as f:
                    all_conf = json.load(f)
                    logger.info(f"load all config from plugins/config.json: {all_conf}")
                # 将读取到的配置 all_conf(各个具体插件的配置) 写入到全局插件配置字典中。
                write_plugin_config(all_conf)
        except Exception as e:
            logger.error(e)
    # 扫描 ./plugins 目录下的插件，加载插件模块并检查是否需要重新加载。如果pconf中没有该插件的信息，则将插件
    # 的配置添加到 pconf 中。
    def scan_plugins(self):
        logger.info("Scaning plugins ...")
        plugins_dir = "./plugins"
        raws = [self.plugins[name] for name in self.plugins] # 这个得到的是目前插件管理中所有的插件类
        for plugin_name in os.listdir(plugins_dir): # 这个得到目录下的文件或目录的路径
            plugin_path = os.path.join(plugins_dir, plugin_name)
            # 只有当插件目录中包含 __init__.py 文件时，该插件才会被视为有效的插件并进行处理。__init__.py 是 Python 中标识一个目录为包的特
           # 殊文件，通常用于定义包的初始化行为，或者为该包下的子模块提供入口。
            if os.path.isdir(plugin_path):
                main_module_path = os.path.join(plugin_path, "__init__.py")
                if os.path.isfile(main_module_path):
                    # 要导入的插件路径
                    import_path = "plugins.{}".format(plugin_name)
                    try:
                        self.current_plugin_path = plugin_path # 设置当前插件的路径
                        if plugin_path in self.loaded: # 如果插件已经被加载过了
                            if plugin_name.upper() != 'GODCMD': # 如果不是管理员插件
                                logger.info("reload module %s" % plugin_name)
                                # sys.modules[import_path]：这是 Python 中存储已加载模块的字典，import_path 是模块的名称（字符串形式）
                                # 在reload时,插件模块会被重新加载,这时会调用里面的plugins.register方法设置插件到self.plugins里
                                # self.loaded的键是插件路径,值是重新加载后的插件模块对象
                                self.loaded[plugin_path] = importlib.reload(sys.modules[import_path])
                                # name.startswith(import_path + ".") 用来筛选出所有依赖于 import_path 模块的子模块（或依赖模块）。这里的 "." 表示模
                                # 块的层次结构。
                                dependent_module_names = [name for name in sys.modules.keys() if name.startswith(import_path + ".")]
                                for name in dependent_module_names:
                                    logger.info("reload module %s" % name)
                                    importlib.reload(sys.modules[name])
                        # 当你导入一个模块时，Python 会自动处理该模块的依赖。也就是说，如果 import_path 对应的模块（如 my_plugin）导入时，
                        # 它会尝试导入该模块中所依赖的其他模块（如 my_plugin.submodule1、my_plugin.submodule2）以及它们之间的依赖关系。
                        else:  # 如果插件还没被加载,loaded里设置的是插件路径和其对应的导入模块(包括会导入子模块)
                            self.loaded[plugin_path] = importlib.import_module(import_path)
                        # 设置当前插件路径为None可以避免错误,外层循环遍历每一个插件,每进入一次遍历,当前插件路径都会改变设置,而self.plugins里的插件类
                        # 已经设置了对应的插件路径
                        self.current_plugin_path = None
                    except Exception as e:
                        logger.warn("Failed to import plugin %s: %s" % (plugin_name, e))
                        continue # 如果出现异常,退出当次循环,继续加载下个插件模块
        pconf = self.pconf # 获取当前插件管理的配置pconf
        # 找出当前插件列表中新增的插件（news 是当前插件列表，raws 是之前加载的插件列表）。new_plugins 存储了新增的插件。
        # 因为上面无论reload,还是import_module的模块,要么新增一个键值对，要么改变名称对应的插件实例，所以这里获取的就是新的更改后的插件元数据列表
        news = [self.plugins[name] for name in self.plugins]
        # 这里用 set(news) 和 set(raws) 将 news 和 raws 转换为集合，然后通过集合的差集操作（-）来找出 news 中存在而 raws 中不存在的元素。
        new_plugins = list(set(news) - set(raws))
        modified = False # 设置标记
        # name 是插件的注册名称，因为上面的reload会加载插件模块,间接调用了regist方法把插件设置到了self.plugins中
        # rawname 是插件类的原始名称，通常保留插件的原始大小写。这个 rawname 是用来从插件配置（pconf）中查找配置项的。
        for name, plugincls in self.plugins.items(): # 遍历所有插件类
            rawname = plugincls.name # 插件的原名称,name是大写形式
            # pconf["plugins"]对应的是字典,字典中的键是插件原名,值是一个包含插件优先级之类的字典
            if rawname not in pconf["plugins"]: # 这种情况是新导入的插件模块 
                modified = True
                logger.info("Plugin %s not found in pconfig, adding to pconfig..." % name)
                # 用self.plugins中的插件优先级等的配置设置pconf中插件的配置
                pconf["plugins"][rawname] = {
                    "enabled": plugincls.enabled,
                    "priority": plugincls.priority,
                }
            else: # 如果插件已经在pconf中,这种是reload的情况,用pconf中插件的优先级配置改变self.plugins中的配置
                self.plugins[name].enabled = pconf["plugins"][rawname]["enabled"]
                self.plugins[name].priority = pconf["plugins"][rawname]["priority"]
                # 在更新完插件的启用状态和优先级后，调用 self.plugins._update_heap(name) 来确保插件的优先级顺序是最新的。
                self.plugins._update_heap(name) 
        if modified: # 如果有修改，就是pconf被改变，就调用save_config保存pconf的配置
            self.save_config()
        return new_plugins # 返回reload或新导入的插件的列表
     # 对每个事件（event）所对应的插件列表（self.listening_plugins[event]）进行排序，使得插件按照优先级降序排列。优先级高的插件会排
    # 在前面，优先级低的插件会排在后面。
    # 举个例子：self.listening_plugins = {'event1': ['pluginA', 'pluginB', 'pluginC']}。
    # self.plugins = {'pluginA': {'priority': 3}, 'pluginB': {'priority': 1}, 'pluginC': {'priority': 2}}。
    # 在执行 refresh_order 后，self.listening_plugins['event1'] 会变成 ['pluginA', 'pluginC', 'pluginB']，也就是插件列表按照
    # 优先级降序排列。
    def refresh_order(self):
        for event in self.listening_plugins.keys(): # 遍历里面的键
            self.listening_plugins[event].sort(key=lambda name: self.plugins[name].priority, reverse=True)
    # 用于激活插件实例的过程，其中涉及到插件的实例化,事件处理器的注册以及异常处理
    def activate_plugins(self):  
        failed_plugins = [] # 初始化一个空列表 failed_plugins，用于存储在激活过程中失败的插件名称。
        # 遍历 self.plugins 字典，其中键是插件名称大写（name），值是插件的类（plugincls）。
        for name, plugincls in self.plugins.items():
            if plugincls.enabled: # 检查插件是否已启用。
                if 'GODCMD' in self.instances and name == 'GODCMD':  # 过滤掉管理员插件
                    continue
                try:
                    instance = plugincls() # 这会构建具体的插件子类实例
                # 如果在实例化插件时发生异常，捕获异常并记录警告信息。logger.warn 打印警告日志，表明插件实例化失败，接着调
                # 用 self.disable_plugin(name) 禁用该插件，并将插件名称加入到 failed_plugins 列表中。
                except Exception as e:
                    logger.warn("Failed to init %s, diabled. %s" % (name, e))
                    self.disable_plugin(name) # 禁用插件
                    failed_plugins.append(name)
                    continue # 退出本次循环,继续对下个插件的激活
                # 如果当前插件名对应的插件已经实例化过,就调用旧的插件实例的handlers清空字典
                if name in self.instances:
                    self.instances[name].handlers.clear()
                # self.instances[name] = instance会把旧的插件实例标记为垃圾对象，但 Python 的垃圾回收机制（GC）并不会立刻回
                # 这些对象。因此，如果旧插件实例的 handlers 字典仍然占用内存，直到垃圾回收器决定清理它，可能会造成内存的暂时浪费。通过 
                # self.instances[name].handlers.clear() 显式清除字典中的数据，可以 加速内存的释放。
                self.instances[name] = instance  # 建立插件名大写到插件实例的映射
                # self.listening_plugins 是一个字典，存储了每个 事件 对应的 监听插件 列表，表示哪些插件能够处理某个事件。
                # self.listening_plugins = {
                #     'event_1': ['plugin_1', 'plugin_2'],  # plugin_1 和 plugin_2 都监听 event_1
                #     'event_2': ['plugin_2']               # 只有 plugin_2 监听 event_2
                # }
                for event in instance.handlers:  #  遍历当前插件实例能够处理的所有事件。
                    # 在这里，self.listening_plugins 用来追踪每个事件的 监听者（即哪些插件处理这个事件）
                    #  如果listening_plugins的键中不存在当前事件,就建立新映射
                    if event not in self.listening_plugins:
                        self.listening_plugins[event] = []
                    self.listening_plugins[event].append(name) # listening_plugins是个字典,事件-->包含此事件的插件列表
        self.refresh_order() # 让self.listening_plugins中每个事件对应的插件按对应插件的优先级排序
        return failed_plugins
    # 重新加载指定的插件(用在改变了插件事件处理器的情况下)
    def reload_plugin(self, name: str):
        name = name.upper() # 将插件名称转换为大写
        remove_plugin_config(name) # # 移除全局插件配置字典中的当前插件配置项
        if name in self.instances: # 检查该插件是否存在于实例化插件字典中
            for event in self.listening_plugins: # 遍历所有监听事件类型
                if name in self.listening_plugins[event]: # 如果当前插件正在监听此事件，则从监听列表中移除它
                    self.listening_plugins[event].remove(name) 
            if name in self.instances:
                self.instances[name].handlers.clear() # 清空插件实例的handlers字典中的所有项
            del self.instances[name]  # 从实例字典中删除该插件对应的项
            self.activate_plugins() # 重新激活所有插件，可能是为了加载更新后的插件或恢复默认状态
            return True # 返回True表示操作成功
        return False  # 如果插件从未被实例化过，则返回False表示操作失败

    def load_plugins(self): # 加载插件
        self.load_config() # 从./plugins/plugins.json加载插件优先级之类的配置到pconf/
        self.scan_plugins() # 扫描加载所有插件模块,在加载中设置self.plugins,之后设置self.pconf
        # 加载全局插件配置，并写入全局插件配置字典。
        self._load_all_config()
        pconf = self.pconf
        logger.debug("plugins.json config={}".format(pconf))
        # 遍历pconf["plugins"]中的所有插件配置,如果对应的插件名大写没在self.plugins里,就打印错误日志
        # pconf中插件要对应self.plugins中的插件
        for name, plugin in pconf["plugins"].items():
            if name.upper() not in self.plugins:
                logger.error("Plugin %s not found, but found in plugins.json" % name)
        self.activate_plugins() # 为所有插件创建实例,绑定事件监听
    # 这段代码的作用是 触发（发出）一个事件，并根据该事件去调用所有 监听 该事件的插件的处理函数。代码通过 emit_event 方法实现了 事件驱动 的
    # 机制，其中插件系统根据事件上下文 (e_context) 来判断哪些插件可以响应该事件，并执行相应的处理函数。
    # e_context: EventContext：e_context 是事件上下文，包含了与事件相关的各种信息，如事件名、事件的状态、是否停止事件传播等。
    # *args 和 **kwargs：这是事件处理函数的标准参数，允许你传递任意数量的位置参数和关键字参数，传递给插件的事件处理函数。
    # emit_event 方法的整体流程是：
    # 根据 e_context.event 查找是否有插件监听该事件。
    # 对于每个监听该事件且启用的插件，调用该插件的事件处理函数。
    # 如果某个插件中断了事件（通过 e_context.is_break()），记录中断信息并停止后续插件的事件处理。
    # 返回更新后的事件上下文，可能包含中断信息。
    def emit_event(self, e_context: EventContext, *args, **kwargs):
         # 检查是否有插件监听该事件
        # self.listening_plugins 是一个字典，它的键是事件名（例如 'event_1'），值是一个列表，包含所有 监听 该事件的插件名称
        if e_context.event in self.listening_plugins:
            # 遍历监听该事件的插件,返回一个插件列表，表示所有能够处理当前事件 (e_context.event) 的插件名称。
            for name in self.listening_plugins[e_context.event]: 
                # 如果当前插件是启用状态,并且e_context的事件传播行为是CONTINUE,这时才能执行里面的逻辑
                # 获取插件实例,之后调用插件的handlers中对应事件的事件处理函数处理e_context
                # 如果事件传播行为是BREAK,BREAK_PASS就会进不去if里面,直接返回e_context
                if self.plugins[name].enabled and e_context.action == EventAction.CONTINUE:
                    # 记录一条日志，表示插件 name 被 e_context.event 事件触发。
                    logger.debug("Plugin %s triggered by event %s" % (name, e_context.event))
                    instance = self.instances[name] # 获取当前插件实例
                    # 获取当前插件实例对该事件的处理函数。handlers 是一个字典，其中键是事件名，值是事件对应的处理函数。
                    # 调用处理函数，并将事件上下文（e_context）和其他参数传递给它。
                    instance.handlers[e_context.event](e_context, *args, **kwargs)
                    # 因为在调用插件的处理函数时,有可能改变e_context的事件行为,这里检查e_context的事件行为
                    # 如果被打断,就在e_context中设置个属性,记录是哪个插件打断的,之后打印日志,返回e_context
                    # 因为在事件行为is_break的情况下,e_context.action == EventAction.CONTINUE这个条件不成立
                    if e_context.is_break():
                        e_context["breaked_by"] = name # 记录哪个插件中断了事件的传播。
                        logger.debug("Plugin %s breaked event %s" % (name, e_context.event)) # 记录一条日志，表示事件已经被插件 name 中断。
                        return e_context
        # 如果当前事件没有在self.listening_plugins里面,说明没有监听的插件,返回原e_context
        return e_context
    # 设置指定插件的优先级
    def set_plugin_priority(self, name: str, priority: int):
        name = name.upper() # 转为大写
        if name not in self.plugins: # 如果名称不在当前管理的插件里面,返回False,表示设置失败
            return False
        if self.plugins[name].priority == priority: # 如果要设置的优先级和当前插件的优先级一致,直接返回True
            return True
        self.plugins[name].priority = priority # 其他情况下，改变插件管理字典中插件的优先级
        self.plugins._update_heap(name)
        rawname = self.plugins[name].name # 获取插件的原名称
        # 更新pconf中对应插件的优先级,并重新排序
        self.pconf["plugins"][rawname]["priority"] = priority
        self.pconf["plugins"]._update_heap(rawname) 
        self.save_config() # 将self.pconf的更新写到配置文件中
        self.refresh_order() # 刷新self.listening_plugins中事件对应的插件的顺序(按插件的优先级从高到低)
        return True
    # 启用插件
    def enable_plugin(self, name: str):
        name = name.upper() # 获取大写形式
        if name not in self.plugins: # 如果当前名称在插件字典中不存在
            return False, "插件不存在" # 返回启用失败,提示
        if not self.plugins[name].enabled: # 如果当前名称的插件未启用
            self.plugins[name].enabled = True # 设置为启用状态
            rawname = self.plugins[name].name # 获取插件的原名
            self.pconf["plugins"][rawname]["enabled"] = True # 更新pconf中当前插件的配置
            self.save_config() # 将pconf的更改写到配置文件中
            # 激活插件(包括创建插件实例,绑定插件对相应事件的监听),返回激活失败的插件列表
            failed_plugins = self.activate_plugins() 
            if name in failed_plugins: # 如果激活失败,返回启用失败,提示
                return False, "插件开启失败"
            return True, "插件已开启" # 如果启用成功,返回消息
        return True, "插件已开启" # 如果本来就是启用状态,直接返回
    # 禁用插件
    def disable_plugin(self, name: str):
        name = name.upper() # 转为大写
        # 如果插件不存在，返回 False，表示禁用失败。
        if name not in self.plugins:
            return False
        # 如果插件启用，则禁用插件，更新pconf中对应配置，保存更改到配置文件
        if self.plugins[name].enabled:
            self.plugins[name].enabled = False
            rawname = self.plugins[name].name
            self.pconf["plugins"][rawname]["enabled"] = False
            self.save_config()
            return True # 返回禁用成功标记
        # 如果插件已经禁用，则直接返回 True，不做额外的操作。
        return True
    # 显示当前管理的插件类的字典
    def list_plugins(self):
        return self.plugins
    # 这段代码的作用是安装插件。它通过 Git 克隆仓库来获取插件代码，并处理一些可能的错误情况，最后返回插件安装是否成功的状态信息
    # 接受一个参数 repo，即插件的 Git 仓库地址。该方法用于安装一个插件。
    # 这段代码的目的是从 GitHub 克隆一个插件仓库，并安装其中的依赖。
    # 这段代码的作用是安装一个插件，具体步骤如下：
    # 检查是否已安装 dulwich 库，若没有则尝试安装。
    # 验证插件仓库地址是否合法，如果不合法，尝试从 source.json 配置文件获取合法的仓库地址。
    # 克隆 Git 仓库到本地 ./plugins/{插件名} 目录。
    # 如果插件目录下有 requirements.txt 文件，则安装插件所需的依赖。
    # 如果安装过程中出现任何问题，会捕获异常并返回错误信息。
    def install_plugin(self, repo: str):
        try:
            # dulwich 是一个用于操作 Git 仓库的 Python 库，它提供了对 Git 仓库的原生支持。具体来说，dulwich 允许开发者通过 Python 
            # 代码直接与 Git 仓库进行交互，而不需要依赖外部的 Git 命令行工具。
            import common.package_manager as pkgmgr
            pkgmgr.check_dulwich()
        # 如果在尝试导入 dulwich 或执行 check_dulwich() 时发生异常，将记录错误日志，并返回一个失败的响应，指示插件安装失败。
        except Exception as e:
            logger.error("Failed to install plugin, {}".format(e))
            return False, "无法导入dulwich，安装插件失败"
        # 导入正则表达式库 re 和 dulwich.porcelain 模块。porcelain 模块提供了高层的 Git 操作接口，如克隆仓库等。
        import re
        from dulwich import porcelain
        logger.info("clone git repo: {}".format(repo)) # 使用日志记录插件安装的 Git 仓库地址 repo。
        match = re.match(r"^(https?:\/\/|git@)([^\/:]+)[\/:]([^\/:]+)\/(.+).git$", repo)
        # 使用正则表达式检查 repo 是否符合 Git 仓库的 URL 格式。该正则表达式支持两种 URL 形式：
        # https:// 或 git@ 协议开头。
        # 用户名、仓库名等部分遵循特定的规则，最后必须以 .git 结尾。
        # 如果 repo 地址不符合 Git 仓库的 URL 格式，尝试从 ./plugins/source.json 文件中加载插件源配置。
        if not match:
            try:
                # source.json 可能包含一些插件仓库的 URL 映射，文件中应该有一个 repo 字段，映射着插件名称到其对应的仓库 URL。
                with open("./plugins/source.json", "r", encoding="utf-8") as f:
                    source = json.load(f)
                # 如果 repo 存在于配置文件中，使用配置中的 URL 重新匹配仓库地址。如果匹配不合法，则返回错误信息。
                if repo in source["repo"]:
                    repo = source["repo"][repo]["url"]
                    match = re.match(r"^(https?:\/\/|git@)([^\/:]+)[\/:]([^\/:]+)\/(.+).git$", repo)
                    if not match:
                        return False, "安装插件失败，source中的仓库地址不合法"
                # 如果配置文件中没有找到 repo，返回错误提示，表示仓库地址不合法。
                else:
                    return False, "安装插件失败，仓库地址不合法"
           #  如果在加载 source.json 配置文件时发生异常，捕获异常并记录日志，返回仓库地址不正确的错误信息。
            except Exception as e:
                logger.error("Failed to install plugin, {}".format(e))
                return False, "安装插件失败，请检查仓库地址是否正确"
        # match.group(4) 是正则表达式匹配到的 Git 仓库的路径部分（不包括 .git），用它作为插件的安装目录。
        # dirname 表示插件安装目录，这里是 ./plugins/{插件名称}。
        # match.group(4) 是正则表达式中第 4 个捕获组（括号内的部分）匹配到的内容。
        # \/(.+).git$：匹配仓库路径，(.+) 捕获仓库的完整路径部分（例如 repository-name），最后 .git 表示仓库 URL 必须以 .git 结尾。
        dirname = os.path.join("./plugins", match.group(4))
        try:
           #  尝试使用 dulwich 的 porcelain.clone() 方法克隆 Git 仓库到 dirname 目录下
           #  checkout=True 表示克隆后立即检出（即下载最新代码）。
            repo = porcelain.clone(repo, dirname, checkout=True)
            # 检查克隆的插件目录下是否存在 requirements.txt 文件，如果存在，表示该插件有依赖项。
            # 调用 pkgmgr.install_requirements() 安装插件所需的 Python 包。
            if os.path.exists(os.path.join(dirname, "requirements.txt")):
                logger.info("detect requirements.txt，installing...")
            pkgmgr.install_requirements(os.path.join(dirname, "requirements.txt"))
           #  如果插件成功克隆并安装依赖项，返回一个成功的响应，表示插件安装成功，并提示用户可以扫描插件或重启程序。
            return True, "安装插件成功，请使用 #scanp 命令扫描插件或重启程序，开启前请检查插件是否需要配置"
        # 如果在插件克隆或安装过程中出现异常，捕获异常并记录错误日志，返回安装失败的错误信息，包含异常描述。
        except Exception as e:
            logger.error("Failed to install plugin, {}".format(e))
            return False, "安装插件失败，" + str(e)
    # pull 只是更新本地仓库，与远程仓库进行同步，相同部分保持不变，不同部分会被替换或合并。
    # 它不会删除本地仓库中的文件，除非远程仓库中删除了文件。
    # 如果存在未提交的本地更改，它可能会引发冲突并要求手动解决，避免丢失本地工作。
    def update_plugin(self, name: str):
        try:
            import common.package_manager as pkgmgr
            pkgmgr.check_dulwich()
        except Exception as e:
            logger.error("Failed to install plugin, {}".format(e))
            return False, "无法导入dulwich，更新插件失败"
        from dulwich import porcelain
        name = name.upper()
        if name not in self.plugins:
            return False, "插件不存在"
        if name in [
            "HELLO",
            "GODCMD",
            "ROLE",
            "TOOL",
            "BDUNIT",
            "BANWORDS",
            "FINISH",
            "DUNGEON",
        ]:
            return False, "预置插件无法更新，请更新主程序仓库"
        dirname = self.plugins[name].path
        try:
            # 这行代码是 dulwich 库中的 pull 方法，它的作用是将远程仓库（origin）的最新更改拉取到本地 dirname 目录下。
            # pull 操作会将远程仓库的变更合并到本地仓库中。如果本地有修改且没有推送到远程，pull 时可能会遇到冲突，但如果本地没有
            # 修改，它会直接覆盖本地的文件。
            # 本地目录（dirname）会被覆盖，尤其是在以下两种情况下：
            # 如果本地目录的文件与远程仓库的文件有不同，pull 会将远程的文件覆盖本地的文件，除非本地有未提交的更改（在这种情况下，pull 可能会产生冲突）。
            # 如果本地目录已经存在文件并且这些文件与远程仓库中的文件一致，pull 不会删除这些文件，但会确保本地仓库的内容与远程仓库的最新内容一致。
            porcelain.pull(dirname, "origin")
            if os.path.exists(os.path.join(dirname, "requirements.txt")):
                logger.info("detect requirements.txt，installing...")
            pkgmgr.install_requirements(os.path.join(dirname, "requirements.txt"))
            return True, "更新插件成功，请重新运行程序"
        except Exception as e:
            logger.error("Failed to update plugin, {}".format(e))
            return False, "更新插件失败，" + str(e)
    
    # 卸载一个已安装的插件
    def uninstall_plugin(self, name: str):
        name = name.upper()
        # 这行代码检查插件是否存在于已加载的插件字典 self.plugins 中。如果不存在，函数返回 False 和 "插件不存在" 的提示信息。
        if name not in self.plugins:
            return False, "插件不存在"
        # 如果插件正在运行或已被实例化，代码会调用 self.disable_plugin(name) 来禁用插件实例，防止在删除
        # 插件文件夹时产生冲突。
        if name in self.instances:
            self.disable_plugin(name)
        # 获取插件的路径（self.plugins[name].path）并删除该目录及其内容。这里使用 shutil.rmtree() 方法，
        # 它可以递归删除文件夹及其内的所有文件。
        dirname = self.plugins[name].path
        try:
            import shutil
            shutil.rmtree(dirname)
            # 从监听列表中移除插件 
            # 这段代码遍历 self.listening_plugins 字典，检查每个事件（例如，插件的触发事件）下是否有该插件的监听。
            # 如果有，插件就从这些事件的监听列表中移除。self.listening_plugins 可能是一个事件驱动的系统，用来管理插
            # 件对不同事件的监听。
            rawname = self.plugins[name].name
            for event in self.listening_plugins:
                if name in self.listening_plugins[event]:
                    self.listening_plugins[event].remove(name)
            # 删除 self.plugins 字典中插件的记录，这会使得插件不再被认为是已加载的插件。
            del self.plugins[name]
           #  删除配置文件（self.pconf）中该插件的配置记录（通过 rawname 获取原始插件名），从而清除插件的所有配置信息。
            del self.pconf["plugins"][rawname]
            # 这里 self.loaded是一个记录已加载插件的字典，dirname 是插件的路径。通过将该路径对应的条目设置为 None，
            # 表示插件已被卸载并且不再处于加载状态。
            # 通过将 self.loaded[dirname] 设置为 None，而不是完全删除字典中的键，意味着插件的路径（dirname）仍然存在于 
            # self.loaded 字典中，但它的值为 None。这种方式可能表示“该插件已经卸载，但路径仍然存在”，可以用来表示插件已卸载但仍然存在记录。
            # 这种做法可能是为了在后续的处理过程中，保留已卸载插件的历史记录，避免完全删除该插件的路径信息。
            # None 值表示插件的卸载状态，这样可以让系统知道这个路径曾经有过插件，但现在已经没有插件加载。
            # self.loaded[dirname] = None 的做法是为了保持插件卸载后的状态，但不完全删除路径记录。通过将值设为 None，可以表示插件已卸
            # 载，但路径仍然保留在字典中，方便后续追踪、调试或状态恢复。这种做法在需要保留历史数据或防止直接删除引起问题的情况下比较常见。
            self.loaded[dirname] = None
            # 该方法调用保存配置文件，确保插件卸载后的状态被持久化。保存的内容可能包括插件列表、配置等。
            self.save_config()
            return True, "卸载插件成功"
      #  在卸载过程中，如果出现任何异常（如删除文件失败），捕获异常并记录错误日志。然后返回一个失败的消息，提示用户手动删除插件文件夹。
        except Exception as e:
            logger.error("Failed to uninstall plugin, {}".format(e))
            return False, "卸载插件失败，请手动删除文件夹完成卸载，" + str(e)
