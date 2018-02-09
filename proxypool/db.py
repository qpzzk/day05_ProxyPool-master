import redis
from proxypool.error import PoolEmptyError
from proxypool.setting import HOST, PORT, PASSWORD


class RedisClient(object):  #redis连接信息
    def __init__(self, host=HOST, port=PORT):
        if PASSWORD:
            self._db = redis.Redis(host=host, port=port, password=PASSWORD)
        else:
            self._db = redis.Redis(host=host, port=port)

#保持右侧是新的,左侧是旧的
    def get(self, count=1): #lrange从队列左侧批量获取方法
        """
        get proxies from redis
        """
        proxies = self._db.lrange("proxies", 0, count - 1)
        self._db.ltrim("proxies", count, -1)
        return proxies
#将新的代理放到右侧在检测成功之后rpush
    def put(self, proxy):
        """
        add proxy to right top
        """
        self._db.rpush("proxies", proxy)
#给api使用,从里面拿出新的代理,从右边拿出,取出最新的代理
    def pop(self):
        """
        get proxy from right.
        """
        try:
            return self._db.rpop("proxies").decode('utf-8')
        except:
            raise PoolEmptyError
#队列长度
    @property
    def queue_len(self):
        """
        get length from queue.
        """
        return self._db.llen("proxies")
#刷新
    def flush(self):
        """
        flush db
        """
        self._db.flushall()


if __name__ == '__main__':
    conn = RedisClient()
    print(conn.pop())
