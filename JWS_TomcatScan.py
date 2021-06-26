from script import BruteForce, Tomcat_CNVD_2020_10487, Tomcat_CVE_2017_12615
from colorama import init, Fore
import sys

if __name__ == '__main__':
    print(Fore.GREEN + '''
       ___          _______    _______                        _                       
      | \ \        / / ____|  |__   __|                      | |                      
      | |\ \  /\  / / (___ ______| | ___  _ __ ___   ___ __ _| |_ ___  ___ __ _ _ __  
  _   | | \ \/  \/ / \___ \______| |/ _ \| '_ ` _ \ / __/ _` | __/ __|/ __/ _` | '_ \ 
 | |__| |  \  /\  /  ____) |     | | (_) | | | | | | (_| (_| | |_\__ \ (_| (_| | | | |
  \____/    \/  \/  |_____/      |_|\___/|_| |_| |_|\___\__,_|\__|___/\___\__,_|_| |_|
                                                                                      
                                                                                      
    用法：python3 JWS_Tomcatscan.py 192.168.30.131:8080    
                                                                            --by jammny.
                                                                            
    ''')
    init(autoreset=True)
    host = sys.argv[1]
    print(Fore.GREEN + '[!] 开始扫描目标：{}'.format(host))
    BruteForce.run(host)
    Tomcat_CVE_2017_12615.run(host)
    Tomcat_CNVD_2020_10487.run(host)
    print(Fore.GREEN + '[!] 扫描结束!')