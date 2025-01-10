import io
import os
import re
from urllib.parse import urlparse
from PIL import Image
from common.log import logger
# 获取文件大小
def fsize(file):
    if isinstance(file, io.BytesIO): # 如果是 BytesIO 类型
        return file.getbuffer().nbytes # 返回 BytesIO 对象的字节数
    elif isinstance(file, str):  # 如果是文件路径（字符串）
        return os.path.getsize(file) # 获取文件的实际大小
    elif hasattr(file, "seek") and hasattr(file, "tell"): # 如果是类文件对象（如打开的文件）
        pos = file.tell() #  返回文件当前的指针位置，也就是当前读取的位置。这里是记录文件指针当前位置的值，用来在获取文件大小后恢复文件指针。
        #  将文件指针移动到文件的末尾。os.SEEK_END 是告诉 seek 方法移动到文件的末尾位置，0 表示相对于末尾的位置偏移量为 0，即直接指向文件末尾。
        file.seek(0, os.SEEK_END) 
        # tell() 此时返回的是文件末尾的位置，也就是文件的总大小，因为文件指针已经被移动到末尾。
        size = file.tell() 
        file.seek(pos) # 恢复到之前记录的 pos 位置，即文件指针恢复到最初的位置
        return size
    else:
        raise TypeError("Unsupported type") # 如果类型不支持，抛出异常

# 压缩图片文件，直到小于指定的最大文件大小,file:类文件对象
def compress_imgfile(file, max_size):
    if fsize(file) <= max_size: # 如果文件大小已经小于等于最大值
        return file # 直接返回文件，不需要压缩
    file.seek(0) # 重置文件指针到文件开头
    img = Image.open(file) # 打开图片文件
    rgb_image = img.convert("RGB") # 转换为RGB模式
    quality = 95 # 初始压缩质量
    while True: 
        out_buf = io.BytesIO() # 创建一个内存中的字节流对象
        rgb_image.save(out_buf, "JPEG", quality=quality)  # 保存图片到字节流，指定JPEG格式和质量
        if fsize(out_buf) <= max_size:  # 如果压缩后的文件小于等于最大值
            return out_buf # 返回压缩后的文件
        quality -= 5 # 否则降低质量，再次尝试

# 按照UTF-8字节长度切分字符串
def split_string_by_utf8_length(string, max_length, max_split=0):
    encoded = string.encode("utf-8") # 将字符串编码为UTF-8字节
    start, end = 0, 0 # 初始化开始和结束位置
    result = []  # 存储结果的列表
    while end < len(encoded): # 遍历整个编码后的字节流
        if max_split > 0 and len(result) >= max_split: # 如果达到最大分割次数
            result.append(encoded[start:].decode("utf-8")) # 将剩余部分加入结果
            break
        end = min(start + max_length, len(encoded))  # 设置结束位置，确保不超过最大长度
        # 如果当前字节不是UTF-8编码的开始字节，向前查找直到找到开始字节为止
        while end < len(encoded) and (encoded[end] & 0b11000000) == 0b10000000:
            end -= 1 # 如果是UTF-8的续字节，向前回退
        result.append(encoded[start:end].decode("utf-8")) # 将当前切分的字节解码为字符串并加入结果
        start = end  # 更新开始位置
    return result # 返回最终的切分结果

# 获取文件路径的后缀名（不含点）
def get_path_suffix(path):
    path = urlparse(path).path  # 解析URL，获取路径部分
    return os.path.splitext(path)[-1].lstrip('.') # 获取文件扩展名并去掉前导点

# 将WEBP图片转换为PNG格式
def convert_webp_to_png(webp_image):
    from PIL import Image
    try:
        webp_image.seek(0) # 重置WEBP图片的文件指针到文件开头
        img = Image.open(webp_image).convert("RGBA")  # 打开并转换为RGBA模式
        png_image = io.BytesIO() # 创建一个字节流对象来保存PNG图片
        img.save(png_image, format="PNG")  # 将图片保存为PNG格式
        png_image.seek(0) # 重置PNG图片字节流的指针
        return png_image # 返回转换后的PNG图片字节流
    except Exception as e:
        logger.error(f"Failed to convert WEBP to PNG: {e}") # 如果出现异常，记录错误日志
        raise # 抛出异常

# 移除Markdown格式中的**符号（粗体）
def remove_markdown_symbol(text: str):
    # 移除markdown格式，目前先移除**
    if not text: # 如果文本为空
        return text  # 直接返回原文本
    return re.sub(r'\*\*(.*?)\*\*', r'\1', text) # 使用正则表达式去掉**符号，将粗体内容保留
