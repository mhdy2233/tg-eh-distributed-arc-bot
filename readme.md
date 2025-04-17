# 分布式tg eh归档bot
目前部署的bot端为[归档大王](https://t.me/ehentai_archive_bot)  
归档bot频道为[EH-ABot公告频道](https://t.me/EH_ArBot)  
作者频道为[垃圾机场](https://t.me/lajijichang) 
<details>
  <summary>目前已经实现的功能</summary>

1. - 接收到ex/eh链接后返回解析后的图片以及说明
  - ![](https://fj.mhdy.shop/2025-04-17-20-31-26_20250417203126858.png)
2. - 获取一周内获取归档链接次数最多的5本
  - ![](https://fj.mhdy.shop/2025-04-17-20-36-09_20250417203609010.png)
3. - 查看最近5个被归档的本子
  - ![](https://fj.mhdy.shop/2025-04-17-20-37-30_20250417203730073.png)
4. - 签到获取GP(bot货币与EH无关)
  - ![](https://fj.mhdy.shop/2025-04-17-20-39-13_20250417203913183.png)
5. - 白名单用户可以看到当前全部节点状态(普通用户只能看到数量)
  - ![](https://fj.mhdy.shop/2025-04-17-20-40-40_20250417204040100.png)
6. - 查看本人使用次数及GP
  - ![](https://fj.mhdy.shop/2025-04-17-20-41-56_20250417204156293.png)
7. - 可以已礼物的方式赠送GP，接收方会得到bot的提醒
  - ![](https://fj.mhdy.shop/2025-04-17-20-47-54_20250417204754104.png)
8. - 管理员主动给用户添加GP 
  - ![](https://fj.mhdy.shop/2025-04-17-20-47-08_20250417204708454.png)
9. 1. 内联消息
  1. - 通过内联消息的按钮查看信息和签到
      -   ![](https://fj.mhdy.shop/2025-04-17-20-58-34_20250417205834258.png)
  2. - 通过内联消息直接获取画廊解析和json源信息文件
      -   ![](https://fj.mhdy.shop/2025-04-17-20-59-48_20250417205948804.png)
10. - 添加节点以及管理员黑白名单的操作
    - ![](https://fj.mhdy.shop/2025-04-17-21-01-26_20250417210126569.png)

</details> 

## bot端
如过只是想给别人加后端节点那么直接看[后端节点部分](#后端节点)  
bot端所需文件bot.py，main.py，config.yml

使用 `pip install -r requirements.txt` 安装依赖。  
创建一个mysql数据库(使用utf8mb4格式)  
不会检测数据库表单，请确保数据库默认为空  
目前仅支持MySQL作为存储，代码较为简单并不难有需要的可以自己替换为SQLite。  
填写config.yml  
eh_cookie可以为多个，请使用里站cookie，如果你的网络可以直接更新里站cookie那么igneous可以不填写。  
配置文件中的eh_cookie虽然只写了id, hash, ig但是最好也补上其他的如sk和star(避免超频率)  
填写时按照列表格式填写，如：
```
eh_cookies: [{
  ipb_member_id: "",
  ipb_pass_hash: "",
  igneous: "",
  },{
  ipb_member_id: "",
  ipb_pass_hash: "",
  igneous: "",
  }
]
```
`python3 bot.py` 启动bot  
/start 开始并录入用户数据  
/join 添加后端节点  

使用方法直接对bot发送eh或ex链接即可  
2025/04/02增加内联消息，可以通过@bot输入链接直接发送

## 后端节点
后端节点文件为client.py  
修改文件中的cookie以及key和端口(如果你的网络可以直接更新ig那么ig可不填)  
key为在bot中添加时所需  
`python3 client.py` 启动  
**注意事项：**
首先你的网络需要可以连接到e-hentai以及exhentai(可使用http代理)  
client需要flask, flask_CORS, bs4, requests，flask_limiter可以使用pip3进行安装