# 分布式tg eh归档bot
目前部署的bot端为[归档大王](https://t.me/ehentai_archive_bot)  
归档bot频道为[EH-ABot公告频道](https://t.me/EH_ArBot)  
作者频道为[垃圾机场](https://t.me/lajijichang)  
## bot端
如过只是想给别人加后端节点那么直接看[后端节点部分](#后端节点)  
bot端所需文件bot.py，main.py，config.yml

使用 `pip install -r requirements.txt` 安装依赖。  
创建一个mysql数据库(使用utf8mb4格式)  
不会检测数据库表单，请确保数据库默认为空  

填写config.yml  
eh_cookie可以为多个，请使用里站cookie，如果你的网络可以直接更新里站cookie那么igneous可以不填写。
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