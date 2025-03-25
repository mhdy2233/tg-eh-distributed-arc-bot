# 分布式tg eh归档bot
bot端为 bot.py，main.py，config.yml

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