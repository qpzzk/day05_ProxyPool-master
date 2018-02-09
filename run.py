#coding:utf8
from proxypool.api import app
from proxypool.schedule import Schedule

def main():

    s = Schedule()
    s.run()  #运行了一个调度器
    app.run()  #api接口




if __name__ == '__main__':
    main()

