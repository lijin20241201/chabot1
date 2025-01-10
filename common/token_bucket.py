import threading
import time

# 这是一个令牌桶算法的实现，目的是控制资源请求的速率，例如控制机器人对某个服务的请求频率，确保它不会超出系统的处理能力。
# API请求限流：限制每秒钟可以发起的请求次数。
# 网络带宽控制：限制每秒传输的数据量。
# 机器人的操作频率控制：例如，限制机器人每秒打印消息的次数，避免过于频繁的操作。
class TokenBucket:
    def __init__(self, tpm, timeout=None):
        self.capacity = int(tpm)  # 令牌桶的最大容量，根据tpm（每分钟令牌数）初始化
        self.tokens = 0  # 初始令牌数为0
        self.rate = int(tpm) / 60  # 令牌生成的速率，转换为每秒的生成数量
        self.timeout = timeout  # 获取令牌时的超时时间
        self.cond = threading.Condition()  # 创建一个条件变量，用于线程同步
        self.is_running = True  # 令牌生成线程是否运行的标志
        # 开启令牌生成线程
        threading.Thread(target=self._generate_tokens).start()
    # 令牌生成线程，定期生成令牌
    def _generate_tokens(self):
        while self.is_running:
            with self.cond:
                if self.tokens < self.capacity: # 如果令牌数未满
                    self.tokens += 1 # 增加一个令牌
                self.cond.notify()  # 通知获取令牌的线程
            time.sleep(1 / self.rate) # 按照设定的速率生成令牌，每秒生成指定数量的令牌
    # 请求令牌，如果没有令牌则等待
    # wait() 方法会释放条件变量的锁，让其他线程有机会执行，并进入等待状态
    # self.cond 并不是普通的锁，它是一个条件变量，用于在多线程环境下进行线程之间的通信。
    # wait() 使得线程可以“暂停”并等待某个条件的变化，而在等待时释放锁以便其他线程可以进来执行。
    def get_token(self):
        with self.cond:
            while self.tokens <= 0: # 如果没有令牌
                flag = self.cond.wait(self.timeout) # 等待令牌或者超时
                if not flag:  # 如果等待超时
                    return False # 返回失败
            self.tokens -= 1 # 获取到令牌，令牌数减一
        return True # 返回成功
    # 关闭令牌生成线程
    def close(self):
        self.is_running = False # 设置标志，停止令牌生成线程


if __name__ == "__main__":
    token_bucket = TokenBucket(20, None)  # 创建一个每分钟生产20个tokens的令牌桶
    # token_bucket = TokenBucket(20, 0.1) # 也可以设置超时时间，如0.1秒
    for i in range(3):
        if token_bucket.get_token():  # 尝试获取令牌
            print(f"第{i+1}次请求成功") # 如果成功，打印请求成功的信息
    token_bucket.close() # 关闭令牌生成线程
