import requests, os, json, re, yaml
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, BotCommand, Bot
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters, Application, CallbackQueryHandler, CallbackContext, filters
from main import addr_status, eh_page, eh_arc, arc_download
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import aiomysql

with open("./config.yml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
bot_token = config['bot_token']

# 定义命令列表
COMMANDS = [
    BotCommand("start", "开始使用机器人"),
    BotCommand("help", "获取帮助信息"),
    BotCommand("join", "添加节点"),
    BotCommand("server_list", "查看后端列表"),
    BotCommand("last_page", "查看最新下载的5个画廊"),
    BotCommand("white_add", "id 添加白名单(多个用空格分隔)"),
    BotCommand("white_del", "id 移除白名单(多个用空格分隔)"),
    BotCommand("ban", "id 添加黑名单(多个用空格分隔)"),
    BotCommand("ban_del", "id 移除黑名单(多个用空格分隔)"),
    BotCommand("del_client", "停用我的后端节点"),
    BotCommand("start_client", "修改并启用后端节点")
]

tag_dict = {
    0: "tag_type",  # tag类型
    1: "gallery_type",  # 画廊类型
    2: "language",  # 语言
    3: "parody",    # 原作
    4: "character", #角色
    5: "group",  # 团队
    6: "artist",    #艺术家
    7: "cosplayer", #角色扮演者
    8: "male", # 男性
    9: "female",  # 女性
    10: "mixed",    # 混合
    11: "other" #其他
}
tag_tra_dict = {
    "language": "语言",  # 语言
    "parody": "原作",    # 原作
    "character": "角色", #角色
    "group": "团队",  # 团队
    "artist": "艺术家",    #艺术家
    "cosplayer": "角色扮演者", #角色扮演者
    "male": "男性", # 男性
    "female": "女性",  # 女性
    "mixed": "混合",    # 混合
    "other": "其他" #其他
}

# 定义全局连接池变量
db_pool = None

async def init_db_pool():
    return await aiomysql.create_pool(
        host=config['mysql']['host'],  # MySQL 地址
        port=config['mysql']['prot'],         # MySQL 端口
        user=config['mysql']['user'],       # MySQL 用户名
        password=config['mysql']['password'],  # MySQL 密码
        db=config['mysql']['db'], # 数据库名称
        autocommit=True,   # 自动提交事务
        minsize=1,         # 最小连接数
        maxsize=10         # 最大连接数
    )

async def on_startup(application):
    global db_pool
    db_pool = await init_db_pool()
    print("✅ MySQL 数据库连接池已创建！")

async def on_shutdown(application):
    global db_pool
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        print("❌ MySQL 连接池已关闭！")

async def mysql_(application):
    """检测并创建数据库表"""
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接，无法创建表！")
        return
    
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    created_time DATETIME,
                    user_id BIGINT NOT NULL UNIQUE,
                    username VARCHAR(255),
                    user_gp INT,
                    use_gps INT DEFAULT 0,
                    use_num INT DEFAULT 0,
                    use_time DATETIME
                )
            """)
            print("✅ 数据表 `user_data` 已创建或已存在！")
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS server_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    created_time DATETIME,
                    user_id BIGINT NOT NULL UNIQUE,
                    username VARCHAR(255),
                    addr VARCHAR(255) UNIQUE NOT NULL,
                    token VARCHAR(255) NOT NULL,
                    status VARCHAR(255) NOT NULL,
                    gp_status VARCHAR(255) NOT NULL,
                    enable VARCHAR(255) NOT NULL,
                    use_gps INT DEFAULT 0
                )
            """)
            print("✅ 数据表 `server_data` 已创建或已存在！")
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS tag_data (
                    tag_type VARCHAR(255) NOT NULL,
                    tag VARCHAR(255) NOT NULL,
                    name VARCHAR(255)
                )
            """)
            print("✅ 数据表 `tag_data` 已创建或已存在！")
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    time DATETIME NOT NULL,
                    client_id INT,
                    user_id INT NOT NULL,
                    title1 VARCHAR(300),
                    title2 VARCHAR(300),
                    url VARCHAR(255),
                    image_url VARCHAR(255),
                    type VARCHAR(255),
                    use_gp INT
                )
            """)
            print("✅ 数据表 `logs` 已创建或已存在！")

async def tag_mysql(application):
    """使用数据库进行翻译tag"""
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接，无法增加tag！")
        return
    url = "https://api.github.com/repos/EhTagTranslation/Database/releases/latest"
    response = requests.get(url)
    data = response.json()
    date = []
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            for asset in data['assets']:
                if asset['name'].endswith("db.text.json"):
                    download_url = asset['browser_download_url']
                    response = requests.get(download_url)
                    if response.status_code == 200:
                        # 解析 JSON 数据
                        db = response.json()
                        b = 0
                        for x in db.get('data', []):  # 确保 data['data'] 存在
                            for z in x.get('data', {}):
                                date.append((tag_dict[b], str(z), str(x.get('data', {}).get(z)['name'])))
                            if not date:
                                continue
                            # 获取数据库已有的 tag_data 记录
                            await cur.execute("SELECT tag_type, tag, name FROM tag_data")
                            existing_data = set(await cur.fetchall())  # 转成集合方便去重

                            # 过滤掉已存在的记录
                            filtered_data = [d for d in date if tuple(d) not in existing_data]

                            # 只插入不重复的数据
                            if filtered_data:
                                await cur.executemany("INSERT INTO tag_data (tag_type, tag, name) VALUES (%s, %s, %s)", filtered_data)
                            date = []
                            b += 1
                        print("tag增加完成")

async def get_translations(english_words):
    # 确保英文字词列表不为空
    if not english_words:
        return []
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            china = []
            for x in english_words:
                placeholders = ', '.join(['%s'] * len(x[1:]))
                # 使用 IN 子句进行批量查询
                query = f"SELECT * FROM tag_data WHERE tag IN ({placeholders}) AND tag_type = %s"
                await cur.execute(query, (*x[1:], x[0]))  # 使用*tags解包列表
                result = await cur.fetchall()  # 获取查询结果
                b = [tag_tra_dict[x[0]]]
                # 创建一个字典存储查询结果（英文 -> 中文），如果没有找到中文翻译，默认返回英文
                translation_dict = {row[1]: row[2] for row in result}
                z = b + [translation_dict.get(word, word) for word in x[1:]]  # 如果没有翻译，返回英文单词本身
                china.append(z)
            return china

async def start(update: Update, context: CallbackContext):
    if os.path.exists("./black.json"):
        with open("./black.json", 'r', encoding='utf-8') as f:
            black_list = json.load(f)
    else:
        black_list = []
    if update.message.from_user.id in black_list:
        await update.message.reply_text("你已被添加黑名单，如果这是个错误请联系管理员")
        return
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接，无法增加用户数据！")
        pass
    user_id = update.message.from_user.id
    user_name = update.message.from_user.username
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            await cur.execute("SELECT * FROM user_data WHERE user_id = %s", (user_id))
            result = await cur.fetchone()  # 获取查询结果（单条数据）
            shanghai_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M:%S')
            if result:
                await update.message.reply_text(f"你好，我是eh归档bot，\n你可以将eh/ex链接发送给我用以获取归档下载链接\n当前上海时间为：{shanghai_time}")
            else:
                await cur.execute("INSERT INTO user_data (created_time, user_id, username, user_gp, use_gps, use_num) VALUES (%s, %s, %s, %s, %s, %s)", (shanghai_time, user_id, user_name, 20000, 0, 0))
                inserted_id = cur.lastrowid
                if not inserted_id:
                    inserted_id = 0
                await update.message.reply_text(f"用户信息录入完成\n用户id：{user_id}\n用户名：{user_name}\n用户初始GP：{20000}\n用户为第{inserted_id}位\n当前上海时间为：{shanghai_time}")

async def join_addr(update: Update, context: CallbackContext):
    if os.path.exists("./black.json"):
        with open("./black.json", 'r', encoding='utf-8') as f:
            black_list = json.load(f)
    else:
        black_list = []
    if update.message.from_user.id in black_list:
        await update.message.reply_text("你已被添加黑名单，如果这是个错误请联系管理员")
        return
    if os.path.exists("./white.json"):
        with open("./white.json", 'r', encoding='utf-8') as f:
            white_list = json.load(f)
    else:
        white_list = []
    if not update.message.from_user.id in black_list:
        await update.message.reply_text("请先联系管理员添加白名单")
        return
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        pass
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    if os.path.exists("./white.json"):
        with open("./white.json", 'r', encoding='utf-8') as f:
            white_list = json.load(f)
    else:
        white_list = []
    if not user_id in white_list:
        return ConversationHandler.END
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            await cur.execute("SELECT * FROM server_data WHERE user_id = %s", (user_id,))
            result = await cur.fetchone()  # 获取查询结果（单条数据）
            if result:
                await update.message.reply_text("当前仅支持一人一个")
                pass
            else:
                await update.message.reply_text("请输入你的后端地址如：\nhttp://127.0.0.1:11451\nhttps://eh.mhdy.shop\n输入 /cancel 取消")
                context.user_data['user_id'] = user_id
                context.user_data['username'] = username
                return "join_0"

async def join_0(update: Update, context: CallbackContext):
    addr = update.message.text
    if not addr:
        await update.message.reply_text("请输入你的后端节点地址如：\nhttp://127.0.0.1:11451\nhttps://eh.mhdy.shop")
        return ConversationHandler.END
    context.user_data['addr'] = addr
    await update.message.reply_text("请输入绑定密钥(字符串)，不要有空格或换行如：\n1234，你好，nihao...")
    return "join_1"

async def join_1(update: Update, context: CallbackContext):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        pass
    token = update.message.text
    if ' ' in token:
        await update.message.reply_text("不要有空格！！！\n请重新输入...")
        pass
    elif not token:
        await update.message.reply_text("请输入密钥...")
        pass
    else:
        addr = context.user_data['addr']
        status = await addr_status(addr, token)
        if status == 200:
            context.user_data['addr'] = addr
            async with db_pool.acquire() as conn:  # 获取连接
                async with conn.cursor() as cur:  # 创建游标
                    shanghai_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M:%S')
                    await cur.execute("INSERT INTO server_data (created_time, user_id, username, addr, token, status, gp_status, enable) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (shanghai_time, context.user_data['user_id'], context.user_data['username'], addr, token, "active", "active", "on"))
                    inserted_id = cur.lastrowid
                    await update.message.reply_text(f"恭喜添加成功！\n用户id：{context.user_data['user_id']}\n编号：{inserted_id}\n地址：{context.user_data['addr']}\n密钥：{token}")
                    context.user_data.clear()
                    return ConversationHandler.END
        else:
            await update.message.reply_text(status)
            context.user_data.clear()
            return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext):
    if os.path.exists("./black.json"):
        with open("./black.json", 'r', encoding='utf-8') as f:
            black_list = json.load(f)
    else:
        black_list = []
    if update.message.from_user.id in black_list:
        await update.message.reply_text("你已被添加黑名单，如果这是个错误请联系管理员")
        return
    context.user_data.clear()
    await update.message.reply_text("已取消操作")
    return ConversationHandler.END

async def ehentai(update: Update, context: CallbackContext):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        pass
    chat_id = update.message.from_user.id
    if os.path.exists("./black.json"):
        with open("./black.json", 'r', encoding='utf-8') as f:
            black_list = json.load(f)
    else:
        black_list = []
    if update.message.from_user.id in black_list:
        await update.message.reply_text("你已被添加黑名单，如果这是个错误请联系管理员")
        return
    pattern = r"(e-hentai|exhentai)"
    if bool(re.search(pattern, update.message.text, re.IGNORECASE)):
        url = update.message.text
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        urls = urlparse(update.message.text).path.strip("/").split("/")
        if not len(urls) == 3:
            pass
        gid, token = urls[1], urls[2]
        aaa = await update.message.reply_text("正在检测处理画廊，请稍候...")
        result = await eh_page(gid,token)
        if result == 400:
            await aaa.edit_text("画廊链接错误请检查")
        elif result == 500:
            await aaa.edit_text("发生未知错误")
        elif result == 403:
            await aaa.edit_text("请求网页错误，请联系管理员")
        elif result == 501:
            await aaa.edit_text("请求网页无内容，请联系管理员检查cookie")
        elif len(result) == 2:
            async with db_pool.acquire() as conn:  # 获取连接
                async with conn.cursor() as cur:  # 创建游标
                    await cur.execute("SELECT * FROM tag_data WHERE tag = %s AND tag_type = %s", (result[1][2], "gallery_type"))
                    page_type = await cur.fetchone()  # 获取查询结果（单条数据）
                    if not page_type:
                        page_type = result[1][2]
                    else:
                        page_type = page_type[2]
                    await cur.execute("SELECT * FROM tag_data WHERE tag = %s AND tag_type = %s", (result[1][5], "language"))
                    language = await cur.fetchone()  # 获取查询结果（单条数据）
                    if not language:
                        language = result[1][5]
                    else:
                        language = language[2]
                    tags = await get_translations(result[1][10])
                    tagg = ""
                    for x in tags:
                        tag = ' '.join([f"#{word}" for word in x[1:]])
                        tagg = tagg + x[0] + "：" + tag + "\n"
                    caption = f"主标题：{result[1][0]}\n副标题：{result[1][1]}\n画廊类型：{page_type}\n上传者：{result[1][3]}\n上传时间：{result[1][4]}\n语言：{language}\n画廊大小：{result[1][6]}\n页数：{result[1][7]}\n收藏数：{result[1][8]}\n评分：{result[1][9]}\n\n{tagg}"
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("跳转画廊", url=url), InlineKeyboardButton("归档下载", callback_data=f"arc|{gid}|{token}")]])
                    context.user_data['主标题'] = result[1][0]
                    context.user_data['副标题'] = result[1][1]
                    context.user_data['image'] = result[2]
                    await context.bot.edit_message_media(
                        media=InputMediaPhoto(media=result[0], caption=caption, parse_mode="HTML"),
                        reply_markup=keyboard,
                        chat_id=chat_id,
                        message_id=aaa.message_id,)

async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        pass
    if data[0] == 'arc':
        arc = eh_arc(data[1], data[2])
        if arc == "该画廊目前不可用":
            await context.bot.send_message(chat_id=query.message.chat.id, text="该画廊目前不可用")
        message = f"原图大小：{arc[0][0]} MB\n原图归档消耗GP：**{arc[1][0]}** GP\n重彩样大小：**{arc[0][1]}** MB\n重彩样归档消耗GP：**{arc[1][1]}** GP"
        async with db_pool.acquire() as conn:  # 获取连接
            async with conn.cursor() as cur:  # 创建游标
                await cur.execute("SELECT * FROM user_data WHERE user_id = %s", (query.from_user.id))
                result = await cur.fetchone()  # 获取查询结果（单条数据）
                if result:
                    gp = result[4]
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("原图归档", callback_data=f"original|{data[1]}|{data[2]}|{arc[1][0]}")],
                        [InlineKeyboardButton("重彩样归档", callback_data=f"resample|{data[1]}|{data[2]}|{arc[1][1]}")]
                        ])
                    await context.bot.send_message(chat_id=query.message.chat.id, text=f"主标题：{context.user_data['主标题']}\n副标题：{context.user_data['副标题']}\n{message}\n剩余GP：***{gp}***", parse_mode="Markdown", reply_markup=keyboard)
                else:
                    await context.bot.send_message(chat_id=query.message.chat.id, text="请先使用 /start 录入用户数据")
                    context.user_data.clear()
    elif data[0] == 'original' or data[0] == 'resample':
        gid, token, use_gp = data[1], data[2], data[3]
        if not db_pool:
            print("❌ 数据库未连接，无法增加用户数据！")
        async with db_pool.acquire() as conn:  # 获取连接
            async with conn.cursor() as cur:  # 创建游标
                await cur.execute("SELECT * FROM user_data WHERE user_id = %s", (query.from_user.id,))
                user_data = await cur.fetchone()  # 获取查询结果（单条数据）
                gp = user_data[4]
                remnant_gp = gp - int(use_gp)
                if remnant_gp < 0:
                    await context.bot.send_message(chat_id=query.message.chat.id, text="剩余gp不足")
                else:
                    while True:
                        await cur.execute("SELECT * FROM server_data WHERE status = 'active' AND gp_status = 'active' ORDER BY RAND() LIMIT 1")
                        result = await cur.fetchone()  # 获取查询结果
                        if not result:
                            await context.bot.send_message(chat_id=query.message.chat.id, text="当前无可用服务器")
                            break
                        addr, key, server_user_id = result[4], result[5], result[2]
                        link = arc_download(addr, key, gid, token, clarity=data[0], use_gp=int(use_gp))
                        if link[0]:
                            shanghai_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M:%S')
                            await cur.execute("UPDATE user_data SET user_gp = %s, use_gps = %s, use_num = %s, use_time = %s WHERE user_id = %s", (remnant_gp, user_data[5] + int(use_gp), user_data[6] + 1, shanghai_time, query.from_user.id))
                            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("点击跳转下载", url=link[1])]])
                            await context.bot.send_message(chat_id=query.message.chat.id, text=f"主标题：{context.user_data['主标题']}\n副标题：{context.user_data['副标题']}\n本次使用gp：{use_gp}\n剩余gp：{remnant_gp}\n下载链接默认有效期为1周，每个链接最多可以供2个ip使用。\n下载链接(可复制到多线程下载器)为：\n{link[1]}", reply_markup=keyboard)
                            await cur.execute("UPDATE server_data SET use_gps = %s WHERE user_id = %s", (result[9] + int(use_gp), server_user_id))
                            await cur.execute("INSERT INTO logs (time, client_id, user_id, title1, title2, url, image_url, type, use_gp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (shanghai_time, result[0], query.from_user.id, context.user_data['主标题'], context.user_data['副标题'], f"{gid}|{token}", context.user_data['image'], data[0], int(use_gp) ))
                            break
                        else:
                            if "GP不足" in link[1]:
                                await cur.execute("UPDATE server_data SET gp_status = %s WHERE user_id = %s", ("inactive", server_user_id))
                            else:
                                await cur.execute("UPDATE server_data SET status = %s WHERE user_id = %s", ("inactive", server_user_id))
                            await context.bot.send_message(chat_id=server_user_id, text=link[1])
        context.user_data.clear()
    elif data[0] == "yes_del":
        if not db_pool:
            print("❌ 数据库未连接！")
            return
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE server_data SET enable = %s WHERE id = %s", ("off", data[1]))
                await context.bot.send_message(chat_id=query.message.chat.id, text="停用成功")
    elif data[0] == "yes_start":
        if not db_pool:
            print("❌ 数据库未连接！")
            return
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE server_data SET enable = %s WHERE id = %s", ("on", data[1]))
                await context.bot.send_message(chat_id=query.message.chat.id, text="启用成功")
    elif data[0] == "cancel":
        await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)

async def status_task(context: CallbackContext) -> None:
    """定时任务"""
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM server_data WHERE enable = %s", ("on"))  # 查询所有数据
            result = await cur.fetchall()  # 获取所有行
            for row in result:
                addr = row[4]
                key = row[5]
                status = await addr_status(addr, token=key)
                if status == 200:
                    await cur.execute("UPDATE server_data SET status = %s, gp_status = %s WHERE id = %s", ("active", "active", row[0]))
                elif status == "GP小于50000":
                    await cur.execute("UPDATE server_data SET gp_status = %s WHERE id = %s", ("inactive", row[0]))
                else:
                    await cur.execute("UPDATE server_data SET status = %s WHERE id = %s", ("inactive", row[0]))


async def white_add(update: Update, context: ContextTypes):
    user_id = update.message.from_user.id
    if not user_id in config['gm_list']:
        return
    args = context.args
    if not args:
        await update.message.reply_text("请输入用户id")
        return
    if os.path.exists("./white.json"):
        with open("./white.json", 'r', encoding='utf-8') as f:
            white_list = json.load(f)
    else:
        white_list = []
    w = white_list + args
    with open("./white.json", 'w', encoding='utf-8') as f:
        json.dump(w, f, ensure_ascii=False)
    bb = "\n".join(w)
    await update.message.reply_text(f"添加成功，新增用户：\n{bb}")

async def white_del(update: Update, context: ContextTypes):
    user_id = update.message.from_user.id
    if not user_id in config['gm_list']:
        return
    args = context.args
    if not args:
        await update.message.reply_text("请输入用户id")
        return
    if os.path.exists("./white.json"):
        with open("./white.json", 'r', encoding='utf-8') as f:
            white_list = json.load(f)
        white_list = [x for x in white_list if x not in args]
        if not white_list:
            white_list = []
        with open("./white.json", 'w', encoding='utf-8') as f:
            json.dump(white_list, f, ensure_ascii=False)
        b = "\n".join(args)
        await update.message.reply_text(f"删除成功，被删除的用户：\n{b}")
    else:
        await update.message.reply_text("还未创建白名单")

async def ban_add(update: Update, context: ContextTypes):
    user_id = update.message.from_user.id
    if not user_id in config['gm_list']:
        return
    args = context.args
    if not args:
        await update.message.reply_text("请输入用户id")
        return
    if os.path.exists("./black.json"):
        with open("./black.json", 'r', encoding='utf-8') as f:
            black_list = json.load(f)
    else:
        black_list = []
    w = black_list + args
    with open("./black.json", 'w', encoding='utf-8') as f:
        json.dump(w, f, ensure_ascii=False)
    bb = "\n".join(w)
    await update.message.reply_text(f"添加成功，封禁用户：\n{bb}")

async def ban_del(update: Update, context: ContextTypes):
    user_id = update.message.from_user.id
    if not user_id in config['gm_list']:
        return
    args = context.args
    if not args:
        await update.message.reply_text("请输入用户id")
        return
    if os.path.exists("./black.json"):
        with open("./black.json", 'r', encoding='utf-8') as f:
            black_list = json.load(f)
        black_list = [x for x in black_list if x not in args]
        if not black_list:
            black_list = []
        with open("./black.json", 'w', encoding='utf-8') as f:
            json.dump(black_list, f, ensure_ascii=False)
        b = "\n".join(args)
        await update.message.reply_text(f"移除成功，被移除黑名单的用户：\n{b}")
    else:
        await update.message.reply_text("还未创建黑名单")

async def server_list(update: Update, context: ContextTypes):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM server_data")  # 查询所有数据
            result = await cur.fetchall()  # 获取所有行
            active = 0
            inactive = 0
            gp_inactive = 0
            for x in result:
                if x[6] == "active" and x[7] == "active":
                    active += 1
                elif x[6] == "inactive":
                    inactive += 1
                elif x[7] == "inactive":
                    gp_inactive += 1
            message = f"当前共有 **{len(result)}** 个后端节点\n✅在线可用有 **{active}** 个\n❎掉线或状态异常有 **{inactive}** 个\n❎gp不足有 **{gp_inactive}** 个"
            await update.message.reply_markdown(text=message)

async def help_(update: Update, context: ContextTypes):
    await update.message.reply_markdown(text=f"此bot为分布式eh归档链接获取bot\n基于[此项目](https://github.com/mhdy2233/tg-eh-distributed-arc-bot)制作")

async def del_client(update: Update, context: ContextTypes):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM server_data WHERE user_id = %s", (update.message.from_user.id))  # 查询所有数据
            result = await cur.fetchone()  # 获取查询结果
            if not result:
                await update.message.reply_text("您尚未添加后端节点")
            elif result[8] == "off":
                await update.message.reply_text("您的后端节点已停用")
            else:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("点击停用", callback_data=f"yes_del|{result[0]}")], [InlineKeyboardButton("取消", callback_data="cancel")]])
                await update.message.reply_text(text="您确定要停用后端节点吗？", reply_markup=keyboard)

async def start_client(update: Update, context: ContextTypes):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM server_data WHERE user_id = %s", (update.message.from_user.id))  # 查询所有数据
            result = await cur.fetchone()  # 获取查询结果
            if not result:
                await update.message.reply_text("您尚且没有后端节点，如果要添加请练习管理员获取白名单后使用 /join")
            else:
                context.user_data['token'] = result[5]
                context.user_data['addr'] = result[4]
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("点击启用client", callback_data=f"yes_start|{result[0]}")],
                    [InlineKeyboardButton("点击修改addr", callback_data="addr")],
                    [InlineKeyboardButton("点击修改token", callback_data="token")]
                ])
                await update.message.reply_text(text=f"当前client信息如下：\naddr(地址)：{result[4]}\ntoken(key)：{result[5]}\n状态：{result[8]}", reply_markup=keyboard)

async def addr_client(update: Update, context: ContextTypes):
    query = update.callback_query
    await query.answer()  # 关闭加载动画
    await query.edit_message_text("请输入addr(地址)：\n/cancel 取消")
    return "ssss"

async def addr_client_yes(update: Update, context: ContextTypes):
    url = update.message.text
    if not url:
        await update.message.reply_text("请输入addr(地址)...")
        pass
    else:
        token = context.user_data['token']
        status = await addr_status(url, token)
        if status == 200:
            async with db_pool.acquire() as conn:  # 获取连接
                async with conn.cursor() as cur:  # 创建游标
                    await cur.execute("UPDATE server_data SET addr = %s WHERE user_id = %s", (url, update.message.from_user.id))
                    await update.message.reply_text(f"修改成功！\n当前addr(地址为)：{url}\ntoken(key)为：{token}")
                    context.user_data.clear()
                    return ConversationHandler.END
        else:
            await update.message.reply_text(status)
            context.user_data.clear()
            return ConversationHandler.END

async def token_client(update: Update, context: ContextTypes):
    query = update.callback_query
    await query.answer()  # 关闭加载动画
    await query.edit_message_text("请输入token(key)：\n/cancel 取消")
    return "zzzz"

async def token_client_yes(update: Update, context: ContextTypes):
    token = update.message.text
    if not token:
        await update.message.reply_text("请输入token(key)...")
        pass
    else:
        url = context.user_data['addr']
        status = await addr_status(url, token)
        if status == 200:
            async with db_pool.acquire() as conn:  # 获取连接
                async with conn.cursor() as cur:  # 创建游标
                    await cur.execute("UPDATE server_data SET token = %s WHERE user_id = %s", (token, update.message.from_user.id))
                    await update.message.reply_text(f"修改成功！\n当前addr(地址为)：{url}\ntoken(key)为：{token}")
                    context.user_data.clear()
                    return ConversationHandler.END
        else:
            await update.message.reply_text(status)
            context.user_data.clear()
            return ConversationHandler.END

async def last_page(update: Update, context: ContextTypes):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 5;")  # 查询最新的5条
            result = await cur.fetchall()
            captions = []
            photos = []
            for x in result:
                photos.append(x[7])
            b = 0
            for x in result:
                b += 1
                if x[4]:
                    captions.append(f"{b}. <a href='{x[6]}'>{x[4]}</a>")
                elif x[5]:
                    captions.append(f"{b}. <a href='{x[6]}'>{x[5]}</a>")
            media_group = [
                InputMediaPhoto(media=photo, caption=caption, parse_mode='HTML') 
                for photo, caption in zip(photos, captions)
            ]
            await update.message.reply_media_group(media=media_group)

join_handler = ConversationHandler(
    entry_points=[CommandHandler('join', join_addr)],  # 用户输入 /start 指令时进入对话
    states={
        "join_0": [MessageHandler(filters.TEXT & ~filters.COMMAND, join_0)],  # 等待文本输入
        "join_1": [MessageHandler(filters.TEXT & ~filters.COMMAND, join_1)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]  # 处理取消命令
)

addr_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(addr_client, pattern="^addr$")],
    states={
        "ssss": [MessageHandler(filters.TEXT & ~filters.COMMAND, addr_client_yes)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

token_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(token_client, pattern="^token$")],
    states={
        "zzzz": [MessageHandler(filters.TEXT & ~filters.COMMAND, token_client_yes)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

async def register_commands(app):
    """异步注册命令"""
    await app.bot.set_my_commands(COMMANDS)

def main():
    """主函数"""
    app = Application.builder().token(bot_token).build()

    # 添加命令处理器
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("white_add", white_add))
    app.add_handler(CommandHandler("white_del", white_del))
    app.add_handler(CommandHandler("ban", ban_add))
    app.add_handler(CommandHandler("ban_del", ban_del))
    app.add_handler(CommandHandler("server_list", server_list))
    app.add_handler(CommandHandler("help", help_))
    app.add_handler(CommandHandler("del_client", del_client))
    app.add_handler(CommandHandler("start_client", start_client))
    app.add_handler(CommandHandler("last_page", last_page))

    app.add_handler(join_handler)
    app.add_handler(addr_handler)
    app.add_handler(token_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ehentai))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.job_queue.run_once(on_startup, 0)
    app.job_queue.run_once(mysql_, 3)

    app.post_init = register_commands

    app.job_queue.run_repeating(status_task, interval=300)
    app.job_queue.run_repeating(tag_mysql, interval=86400)

    print("🤖 Bot 正在运行...")
    app.run_polling()

if __name__ == "__main__":
    main()
