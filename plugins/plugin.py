import os
import json
from config import pconf, plugin_config, conf, write_plugin_config
from common.log import logger

# 所有插件的基类(默认继承自object)
class Plugin:
    def __init__(self):
        self.handlers = {} # 事件名-->事件处理函数的映射
    # 加载当前插件配置
    def load_config(self) -> dict:
        # pconf(self.name) 这行代码从全局配置字典中获取当前插件的配置。
        plugin_conf = pconf(self.name)
        # 如果没有从全局配置字典中找到插件的配置，就会去插件所在的目录（self.path）查找名为 config.json 的文件，并加载该文件的配置。
        if not plugin_conf:
            # 这里的 plugin_config_path指向的是 当前插件的配置文件，而不是所有插件的配置文件。
            plugin_config_path = os.path.join(self.path, "config.json")
            logger.debug(f"loading plugin config, plugin_config_path={plugin_config_path}, exist={os.path.exists(plugin_config_path)}")
            if os.path.exists(plugin_config_path): # 如果当前插件的配置文件存在,就加载它,并把它写入到全局插件配置字典里
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    plugin_conf = json.load(f)
                # 写入全局配置内存
                write_plugin_config({self.name: plugin_conf})
        logger.debug(f"loading plugin config, plugin_name={self.name}, conf={plugin_conf}")
        return plugin_conf # 返回当前插件的配置
    # save_config 方法的作用是 双重保存配置
    def save_config(self, config: dict):
        try:
            write_plugin_config({self.name: config}) # 首先把配置写到全局插件配置字典
            # 写入的全局插件配置文件路径
            global_config_path = "./plugins/config.json"
            if os.path.exists(global_config_path): # plugin_config 是全局插件配置字典，它被写入到全局插件配置文件里
                with open(global_config_path, "w", encoding='utf-8') as f:
                    json.dump(plugin_config, f, indent=4, ensure_ascii=False)
            # 把当前配置写入当前插件的单独配置文件（config.json，每个插件一个配置文件）
            plugin_config_path = os.path.join(self.path, "config.json")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "w", encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e: # 出现异常时,记录警告日志
            logger.warn("save plugin config failed: {}".format(e))

    def get_help_text(self, **kwargs):
        return "暂无帮助信息"

    def reload(self):
        pass
