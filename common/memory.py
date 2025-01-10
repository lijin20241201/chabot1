from common.expired_dict import ExpiredDict
# 它会存储用户图像数据，并且每个图像数据都会在3分钟后自动过期，从而避免缓存过期的数据占用内存。
USER_IMAGE_CACHE = ExpiredDict(60 * 3)