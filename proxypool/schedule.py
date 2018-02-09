import time
from multiprocessing import Process
import asyncio
import aiohttp
try:
    from aiohttp.errors import ProxyConnectionError,ServerDisconnectedError,ClientResponseError,ClientConnectorError
except:
    from aiohttp import ClientProxyConnectionError as ProxyConnectionError,ServerDisconnectedError,ClientResponseError,ClientConnectorError
from proxypool.db import RedisClient
from proxypool.error import ResourceDepletionError
from proxypool.getter import FreeProxyGetter
from proxypool.setting import *
from asyncio import TimeoutError


class ValidityTester(object):
    test_api = TEST_API

    def __init__(self):
        self._raw_proxies = None
        self._usable_proxies = []  #临时存储要检测的代理

    #将代理数组传过来,将其设置内变量,代理的数组依次遍历循环
    def set_raw_proxies(self, proxies):
        self._raw_proxies = proxies
        self._conn = RedisClient()

    #async利用IOhttp这个库实现异步检测的方法(python3的新特性)
    async def test_single_proxy(self, proxy): #ip+端口的代理
        """
        text one proxy, if valid, put them to usable_proxies.
        """
        try:
            #aiohttp异步请求库
            async with aiohttp.ClientSession() as session:
                try:
                    if isinstance(proxy, bytes):
                        proxy = proxy.decode('utf-8')
                    real_proxy = 'http://' + proxy
                    print('Testing', proxy)
                    #异步请求的测试,请求百度的连接
                    async with session.get(self.test_api, proxy=real_proxy, timeout=get_proxy_timeout) as response:
                        if response.status == 200:
                            #put方法将其加到redis里面
                            self._conn.put(proxy)
                            print('Valid proxy', proxy)
                except (ProxyConnectionError, TimeoutError, ValueError):
                    print('Invalid proxy', proxy)
        except (ServerDisconnectedError, ClientResponseError,ClientConnectorError) as s:
            print(s)
            pass

    def test(self):
        """
        aio test all proxies.
        """
        print('ValidityTester is working')
        try:
            loop = asyncio.get_event_loop()
            #利用for循环将每个代理进行检测
            tasks = [self.test_single_proxy(proxy) for proxy in self._raw_proxies]
            loop.run_until_complete(asyncio.wait(tasks))
        except ValueError:
            print('Async Error')


class PoolAdder(object):
    """
    add proxy to pool
    """

    def __init__(self, threshold):
        self._threshold = threshold
        self._conn = RedisClient()
        self._tester = ValidityTester()
        self._crawler = FreeProxyGetter()  #从各大网站抓取

    def is_over_threshold(self):
        """
        judge if count is overflow.
        """
        if self._conn.queue_len >= self._threshold:
            return True
        else:
            return False
#代理池没有满的时候
    def add_to_queue(self):
        print('PoolAdder is working')
        proxy_count = 0
        while not self.is_over_threshold():
            for callback_label in range(self._crawler.__CrawlFuncCount__):
                callback = self._crawler.__CrawlFunc__[callback_label]
                raw_proxies = self._crawler.get_raw_proxies(callback)
                # test crawled proxies
                self._tester.set_raw_proxies(raw_proxies)
                self._tester.test()
                proxy_count += len(raw_proxies)
                if self.is_over_threshold():
                    print('IP is enough, waiting to be used')
                    break
            if proxy_count == 0:
                raise ResourceDepletionError


class Schedule(object):
    @staticmethod
    # 方法:调度器,参数是一个时间的参数,一次隔多少秒检测
    def valid_proxy(cycle=VALID_CHECK_CYCLE):
        """
        Get half of proxies which in redis
        """
        conn = RedisClient()
        tester = ValidityTester() #检测代理是否可用
        while True:
            print('Refreshing ip')
            count = int(0.5 * conn.queue_len) #取出左侧一半的代理进行检测
            if count == 0:   #队列长度要是不够,等待
                print('Waiting for adding')
                time.sleep(cycle)
                continue
            raw_proxies = conn.get(count)
            tester.set_raw_proxies(raw_proxies)
            tester.test()
            time.sleep(cycle)

    @staticmethod

    def check_pool(lower_threshold=POOL_LOWER_THRESHOLD,#代理池数量
                   upper_threshold=POOL_UPPER_THRESHOLD,
                   cycle=POOL_LEN_CHECK_CYCLE):  #时间轮询
        """
        If the number of proxies less than lower_threshold, add proxy
        """
        conn = RedisClient()
        adder = PoolAdder(upper_threshold)
        #要是代理池够了就停止加载,保护代理池不会崩
        while True:
            if conn.queue_len < lower_threshold:
                adder.add_to_queue()
            time.sleep(cycle)

    def run(self):
        print('Ip processing running')
        valid_process = Process(target=Schedule.valid_proxy) #从网上获取代理进行筛选,再将其放数据库
        check_process = Process(target=Schedule.check_pool)  #定期对代理池进行检测
        valid_process.start()
        check_process.start()
