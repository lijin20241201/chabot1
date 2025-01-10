from queue import Full, Queue # 导入标准库中的 Full 和 Queue 类，Full 是用来表示队列满时的异常
from time import monotonic as time # 从 time 库导入 monotonic 函数，并重命名为 time，用来获取不受系统时钟影响的单调时间

# 定义 Dequeue 类，继承自 Queue 类，添加了 putleft 方法来在队列的左边插入元素
class Dequeue(Queue):
    # putleft 方法用于将元素插入队列的左侧
    def putleft(self, item, block=True, timeout=None):
        # self.not_full 是一个 Condition 对象，通常会与一个锁（Lock 或 RLock）一起使用。进入 with 语句时，Python 会自动获得该锁，从而
        # 确保后续代码块内对共享资源（如队列）的访问是 线程安全 的。程序始终会进入
        # wait() 方法是 Condition 类的一个特有方法， 并不是 self.not_full 特有的，而是所有 Condition 对象共有的方法。它用于使当前线
        # 程 等待某个条件，并在等待期间释放锁。
        with self.not_full:
            if self.maxsize > 0: # 如果队列的最大大小大于0，即有限队列
                if not block: # 如果 block=False，表示不阻塞插入，当队列满时直接抛出 Full 异常
                    if self._qsize() >= self.maxsize:
                        raise Full
                elif timeout is None: # 如果 block=True，并且没有设置 timeout，阻塞等待直到队列有空余空间
                    while self._qsize() >= self.maxsize:
                        self.not_full.wait()
                elif timeout < 0: # 如果 timeout < 0，抛出 ValueError 异常，因为 timeout 必须是非负数
                    raise ValueError("'timeout' must be a non-negative number")
                else: # 如果 timeout 是非负数，计算结束时间，通过阻塞直到队列有空余空间
                    endtime = time() + timeout # 计算结束时间
                    while self._qsize() >= self.maxsize:  # 如果队列已满，阻塞等待直到队列空间空余
                        remaining = endtime - time() # 这个在循环内随迭代次数会不断改变
                        if remaining <= 0.0: # 如果剩余时间为负，则超时，抛出 Full 异常
                            raise Full
                        self.not_full.wait(remaining) # 等待剩余时间，直到有空间
            self._putleft(item) # 在队列不满的时候，才会将元素插入队列。
            self.unfinished_tasks += 1 # 增加未完成任务计数器
            self.not_empty.notify() # 唤醒所有等待队列非空的线程，表示队列中有元素
    # putleft_nowait 方法是 putleft 方法的简化版，不进行阻塞，如果队列已满，直接抛出 Full 异常
    def putleft_nowait(self, item):
        return self.putleft(item, block=False)
    # _putleft 方法是将元素放入队列的左边，队列是双端队列（deque）
    def _putleft(self, item): # 这个self.queue是collections.deque对象
        self.queue.appendleft(item)
