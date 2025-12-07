import requests, os, json, re, yaml, random, io, time, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, BotCommand, InlineQueryResultArticle, InputTextMessageContent, InlineQueryResultPhoto, InlineQueryResultsButton, BotCommandScopeDefault, BotCommandScopeChat
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters, Application, CallbackQueryHandler, filters, InlineQueryHandler
from telegram.request import HTTPXRequest
from main import addr_status, eh_page, eh_arc, arc_download, eh_meta, eh_page_meta, eh_dmca, get_eh_info
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import aiomysql
import uuid
from collections import defaultdict
from telepress import publish_text, TelePressError, ValidationError

with open("./config.yml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
bot_token = config['bot_token']
proxies = config.get("proxy")
bot_username = config['bot_username']
my_chat = config['my_chat']
# 定义命令列表
COMMANDS = [
    BotCommand("start", "开始使用机器人"),
    BotCommand("check_in", "签到"),
    BotCommand("popular", "获取最近一周最热门的5个"),
    BotCommand("last_page", "查看最新下载的5个画廊"),
    BotCommand("server_list", "查看后端列表"),
    BotCommand("my_info", "查看我的信息"),
    BotCommand("give_gp", "[用户id] [GP数量] 赠送GP"),
    BotCommand("help", "获取帮助信息"),
]

ADMIN_COMMANDS = [
    BotCommand("start", "开始使用机器人"),
    BotCommand("check_in", "签到"),
    BotCommand("popular", "获取最近一周最热门的5个"),
    BotCommand("last_page", "查看最新下载的5个画廊"),
    BotCommand("server_list", "查看后端列表"),
    BotCommand("my_info", "查看我的信息"),
    BotCommand("give_gp", "[用户id] [GP数量] 赠送GP"),
    BotCommand("help", "获取帮助信息"),
    BotCommand("join", "添加节点"),
    BotCommand("white_add", "id 添加白名单(多个用空格分隔)"),
    BotCommand("white_del", "id 移除白名单(多个用空格分隔)"),
    BotCommand("ban", "id 添加黑名单(多个用空格分隔)"),
    BotCommand("ban_del", "id 移除黑名单(多个用空格分隔)"),
    BotCommand("add_gp", "[用户id] [gp数量] 添加gp"),
]

WHITE_COMMANDS = [
    BotCommand("start", "开始使用机器人"),
    BotCommand("check_in", "签到"),
    BotCommand("popular", "获取最近一周最热门的5个"),
    BotCommand("last_page", "查看最新下载的5个画廊"),
    BotCommand("server_list", "查看后端列表"),
    BotCommand("my_info", "查看我的信息"),
    BotCommand("give_gp", "[用户id] [GP数量] 赠送GP"),
    BotCommand("help", "获取帮助信息"),
    BotCommand("join", "添加节点"),
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
    "other": "其他", #其他
    "temp": "临时",
    "reclass": "重新分类"
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

async def on_startup(a):
    global db_pool
    db_pool = await init_db_pool()
    print("✅ MySQL 数据库连接池已创建！")

async def on_shutdown(a):
    global db_pool
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        print("❌ MySQL 连接池已关闭！")

async def mysql_(a):
    """检测并创建数据库表"""
    global db_pool
    if not db_pool:
        on_startup(a)
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
                    use_time DATETIME,
                    last_sign_in DATE
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
                    user_id BIGINT NOT NULL,
                    title1 VARCHAR(300),
                    title2 VARCHAR(300),
                    url VARCHAR(255),
                    image_url VARCHAR(255),
                    type VARCHAR(255),
                    use_gp INT,
                    log_type VARCHAR(255)
                )
            """)
            print("✅ 数据表 `logs` 已创建或已存在！")
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS message (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    gid INT NOT NULL,
                    title VARCHAR(255),
                    message_id INT NOT NULL,
                    file_id VARCHAR(255)
                )
            """)
            print("✅ 数据表 `message` 已创建或已存在！")

async def tag_mysql(application):
    """使用数据库进行翻译tag"""
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接，无法增加tag！")
        return
    url = "https://api.github.com/repos/EhTagTranslation/Database/releases/latest"
    response = requests.get(url, proxies=proxies)
    data = response.json()
    date = []
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            for asset in data['assets']:
                if asset['name'].endswith("db.text.json"):
                    download_url = asset['browser_download_url']
                    response = requests.get(download_url, proxies=proxies)
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

async def get_translations(b, english_words):
    # 确保英文字词列表不为空
    if not english_words:
        return []
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            if b == "page":
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
            elif b == "meta":
                tags_dict = defaultdict(list)
                for tag_and_type in english_words:
                    tag_list = tag_and_type.split(":")
                    await cur.execute("SELECT * FROM tag_data WHERE tag = %s AND tag_type = %s", (tag_list[1], tag_list[0]))
                    result = await cur.fetchone()  # 获取查询结果
                    if result:
                        tags_dict[tag_tra_dict[result[0]]].append(result[2])
                    else:
                        tags_dict[tag_tra_dict[tag_list[0]]].append(tag_list[1])
                return dict(tags_dict)


async def page(gid, token, context, user_id):
    global db_pool
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            await cur.execute("SELECT * FROM message WHERE gid = %s", (gid))
            result_ = await cur.fetchone()  # 获取查询结果（单条数据）
            result = await eh_page(gid,token)
            if result == 400:
                return "画廊链接错误请检查"
            elif result == 500:
                return "发生未知错误"
            elif result == 403:
                return "请求网页错误，请联系管理员"
            elif result == 501:
                return "请求网页无内容，请联系管理员检查cookie"
            elif result == 404:
                page_meta = await eh_page_meta(gid, token)
                if page_meta == 500:
                    return "画廊不存在"
                await cur.execute("SELECT * FROM tag_data WHERE tag = %s AND tag_type = %s", (page_meta[1][2], "gallery_type"))
                page_type = await cur.fetchone()  # 获取查询结果（单条数据）
                if not page_type:
                    page_type = page_meta[1][2]
                else:
                    page_type = page_type[2]
                tagg = ""
                tagg_dict = await get_translations("meta", page_meta[1][8])
                for key, value in tagg_dict.items():
                    tagg = tagg + key + "： #" + ' #'.join(value) + "\n"
                url = await eh_dmca(gid)
                if url:
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("获取元数据", callback_data=f"json|{gid}|{token}|{user_id}"), InlineKeyboardButton("点击跳转本子", url=url)], [InlineKeyboardButton("📝 推送到Telegraph", callback_data=f"telegraph|{gid}|{token}|{user_id}")]])
                    keyboard2 = InlineKeyboardMarkup([[InlineKeyboardButton("获取元数据", callback_data=f"json|{gid}|{token}|{user_id}"), InlineKeyboardButton("点击跳转本子", url=url)], [InlineKeyboardButton("📝 推送到Telegraph", callback_data=f"telegraph|{gid}|{token}|{user_id}")], [InlineKeyboardButton("还在为进不去里站而苦恼吗？点击购买里站帐号！", url="https://shop.mhdy.icu?cid=2&mid=3")]])
                else:
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("获取元数据", callback_data=f"json|{gid}|{token}|{user_id}")], [InlineKeyboardButton("📝 推送到Telegraph", callback_data=f"telegraph|{gid}|{token}|{user_id}")]])
                    keyboard2 = InlineKeyboardMarkup([[InlineKeyboardButton("获取元数据", callback_data=f"json|{gid}|{token}|{user_id}")], [InlineKeyboardButton("📝 推送到Telegraph", callback_data=f"telegraph|{gid}|{token}|{user_id}")], [InlineKeyboardButton("还在为进不去里站而苦恼吗？点击购买里站帐号！", url="https://shop.mhdy.icu?cid=2&mid=3")]])
                caption = f"<blockquote expandable>主标题：{page_meta[1][0]}\n副标题：{page_meta[1][1]}\n画廊类型：{page_type}\n上传者：{page_meta[1][3]}\n上传时间：{page_meta[1][4]}\n画廊大小：{page_meta[1][5]}\n页数：{page_meta[1][6]}\n评分：{page_meta[1][7]}\n\n{tagg}</blockquote>"
                context.user_data['主标题'] = page_meta[1][0]
                context.user_data['副标题'] = page_meta[1][1]
                context.user_data['image'] = page_meta[0]
                photo = page_meta[0]
                title = page_meta[1][0]
                dmca = url
            elif len(result) == 3:
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
                tags = await get_translations("page", result[1][10])
                tagg = ""
                for x in tags:
                    tag = ' '.join([f"#{word}" for word in x[1:]])
                    tagg = tagg + x[0] + "：" + tag + "\n"
                caption = f"<blockquote expandable>主标题：{result[1][0]}\n副标题：{result[1][1]}\n画廊类型：{page_type}\n上传者：{result[1][3]}\n上传时间：{result[1][4]}\n语言：{language}\n画廊大小：{result[1][6]}\n页数：{result[1][7]}\n收藏数：{result[1][8]}\n评分：{result[1][9]}\n\n{tagg}</blockquote>"
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("获取元数据", callback_data=f"json|{gid}|{token}|{user_id}"), InlineKeyboardButton("归档下载", callback_data=f"arc|{gid}|{token}")], [InlineKeyboardButton("📝 推送到Telegraph", callback_data=f"telegraph|{gid}|{token}|{user_id}")], [InlineKeyboardButton("还在为进不去里站而苦恼吗？点击购买里站帐号！", url="https://shop.mhdy.icu?cid=2&mid=3&from=1000")]])
                keyboard2 = InlineKeyboardMarkup([[InlineKeyboardButton("获取元数据", callback_data=f"json|{gid}|{token}|{user_id}"), InlineKeyboardButton("在bot中打开", url=f"https://t.me/{bot_username}?start={gid}_{token}")], [InlineKeyboardButton("📝 推送到Telegraph", callback_data=f"telegraph|{gid}|{token}|{user_id}")], [InlineKeyboardButton("还在为进不去里站而苦恼吗？点击购买里站帐号！", url="https://shop.mhdy.icu?cid=2&mid=3")]])
                context.user_data['主标题'] = result[1][0]
                context.user_data['副标题'] = result[1][1]
                context.user_data['image'] = result[2]
                photo = result[0]
                title = result[1][0]
                dmca = False
            if len(caption) > 1024:
                caption = caption[:1024 - 12] + "</blockquote>"
            if not result_:
                
                tg = await context.bot.send_photo(
                    chat_id=my_chat,  # 目标聊天 ID
                    photo=photo,  # 图片文件或图片 URL
                    caption=caption,  # 图片的标题
                    parse_mode="HTML",  # 设置解析模式为 HTML
                    reply_markup=keyboard2  # 回复键盘
                    )
                file_id = tg.photo[-1].file_id
                await cur.execute("INSERT INTO message (gid, title, message_id, file_id) VALUES (%s, %s, %s, %s)", (gid, title, tg.message_id, file_id))
                return file_id, caption, keyboard, title, dmca
            else:
                file_id = result_[4]
                return file_id, caption, keyboard, title, dmca

async def check(user_id):
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM user_data WHERE user_id = %s", (user_id))
            result = await cur.fetchone()  # 获取查询结果
            if not result:
                return "你还没有注册请使用 /start@ehentai_archive_bot 注册"
            else:
                await cur.execute("SELECT * FROM user_data WHERE user_id = %s AND (last_sign_in IS NULL OR last_sign_in < CURDATE());", (user_id))
                result = await cur.fetchone()  # 获取查询结果
                if result:
                    random_number = random.randint(config['s_GP'], config['b_GP'])
                    await cur.execute("UPDATE user_data SET user_gp = %s, last_sign_in = CURDATE() WHERE user_id = %s", (random_number + result[4], user_id))
                    return random_number, random_number + result[4]
                else:
                    return "今日已签到"

async def publish_to_telegraph(gid, token):
    """将画廊信息发布到Telegraph
    
    Args:
        gid: 画廊ID
        token: 画廊token
    
    Returns:
        tuple: (telegraph_url, error_message)
    """
    try:
        # 输入验证
        if not gid or not token:
            return None, "画廊ID或token为空"
        
        # 获取画廊元数据
        meta = await eh_meta(gid, token)
        if not meta or 'gmetadata' not in meta or not meta['gmetadata']:
            return None, "获取画廊元数据失败"
        
        gallery = meta['gmetadata'][0]
        
        # 检查是否有错误（如画廊不存在）
        if gallery.get('error'):
            return None, f"画廊错误: {gallery.get('error')}"
            
        # 获取预览图
        previews = []
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            }
            target_url = f"https://e-hentai.org/g/{gid}/{token}/"
            
            eh_cookie = random.choice(config.get('eh_cookies', [{}])) if config.get('eh_cookies') else {}
            
            res = await asyncio.to_thread(
                requests.get, 
                target_url, 
                headers=headers, 
                cookies=eh_cookie,
                proxies=proxies, 
                timeout=10
            )
            html = res.text
            
            # 使用更健壮的正则匹配图片链接
            found_urls = re.findall(r'https?://(?:[a-z0-9-]+\.)*(?:ehgt|exhentai|e-hentai)\.org/[a-z]/[\w/.-]+\.jpg', html)
            
            seen = set()
            for url in found_urls:
                if url not in seen and ('/t/' in url or '/m/' in url):
                    seen.add(url)
                    previews.append(url)
            previews = previews[:20]
        except Exception as e:
            print(f"获取预览图失败: {e}")
        
        title = gallery.get('title', '未知标题')
        title_jpn = gallery.get('title_jpn', '')
        category = gallery.get('category', '未知')
        uploader = gallery.get('uploader', '未知')
        posted = gallery.get('posted', '')
        filecount = gallery.get('filecount', '0')
        filesize = gallery.get('filesize', 0)
        rating = gallery.get('rating', '0')
        tags = gallery.get('tags', [])
        
        # 转换时间戳
        if posted:
            try:
                posted_time = datetime.fromtimestamp(int(posted)).strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, OSError, OverflowError):
                posted_time = posted
        else:
            posted_time = '未知'
        
        # 转换文件大小
        if filesize:
            if filesize > 1024 * 1024 * 1024:
                size_str = f"{filesize / 1024 / 1024 / 1024:.2f} GB"
            elif filesize > 1024 * 1024:
                size_str = f"{filesize / 1024 / 1024:.2f} MB"
            else:
                size_str = f"{filesize / 1024:.2f} KB"
        else:
            size_str = '未知'
        
        # 整理标签
        tags_by_type = {}
        for tag in tags:
            if ':' in tag:
                tag_type, tag_name = tag.split(':', 1)
            else:
                tag_type, tag_name = 'misc', tag
            if tag_type not in tags_by_type:
                tags_by_type[tag_type] = []
            tags_by_type[tag_type].append(tag_name)
        
        # 构建 Markdown 内容
        content = f"# {title}\n\n"
        
        # 添加封面
        thumb = gallery.get("thumb", "")
        if thumb:
            thumb = thumb.replace("s.exhentai.org", "ehgt.org")
            content += f"![封面]({thumb})\n\n"

        if title_jpn:
            content += f"**日文标题**: {title_jpn}\n\n"
        
        content += f"""## 基本信息

- **类型**: {category}
- **上传者**: {uploader}
- **发布时间**: {posted_time}
- **页数**: {filecount}
- **大小**: {size_str}
- **评分**: {rating}

## 画廊链接

- [ExHentai](https://exhentai.org/g/{gid}/{token}/)
- [E-Hentai](https://e-hentai.org/g/{gid}/{token}/)

## 标签

"""
        for tag_type, tag_list in tags_by_type.items():
            tag_type_cn = tag_tra_dict.get(tag_type, tag_type)
            content += f"**{tag_type_cn}**: {', '.join(tag_list)}\n\n"
            
        # 添加预览图
        if previews:
            content += "## 预览\n\n"
            for p in previews:
                content += f"![预览]({p}) "
            content += "\n\n"
        
        content += f"""
---

*由 [EH归档Bot](https://t.me/{bot_username}) 生成*
"""
        
        # 使用 telepress 发布到 Telegraph
        telegraph_url = await asyncio.to_thread(
            publish_text, 
            content, 
            title=title[:256]  # Telegraph 标题限制
        )
        
        return telegraph_url, None
        
    except ValidationError as e:
        return None, f"验证错误: {str(e)}"
    except TelePressError as e:
        return None, f"发布错误: {str(e)}"
    except Exception as e:
        return None, f"发生错误: {str(e)}"
                
async def my_info_text_(user_id, username):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        pass
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            await cur.execute("SELECT * FROM user_data WHERE user_id = %s", (user_id))
            result = await cur.fetchone()  # 获取查询结果（单条数据）
            print(f"第一次查询{result}")
            shanghai_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M:%S')
            if not result:
                await cur.execute("INSERT INTO user_data (created_time, user_id, username, user_gp, use_gps, use_num) VALUES (%s, %s, %s, %s, %s, %s)", (shanghai_time, user_id, username, 20000, 0, 0))
                await cur.execute("SELECT * FROM user_data WHERE user_id = %s", (user_id))
                result = await cur.fetchone()  # 获取查询结果（单条数据）
                print(f"第二次查询{result}")
                my_info_text = f"你是第{result[0]}位用户\n使用次数为：{result[6]}\n使用gp为：{result[5]}\n剩余gp为：{result[4]}"
                return my_info_text
            else:
                my_info_text = f"你是第{result[0]}位用户\n使用次数为：{result[6]}\n使用gp为：{result[5]}\n剩余gp为：{result[4]}\n最后一次使用时间为：{result[7]}"
                return my_info_text
            
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists("./black.json"):
        with open("./black.json", 'r', encoding='utf-8') as f:
            black_list = json.load(f)
    else:
        black_list = []
    if str(update.message.from_user.id) in black_list:
        await update.message.reply_text("你已被添加黑名单，如果这是个错误请联系管理员")
        return
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接，无法增加用户数据！")
        pass
    user_id = update.message.from_user.id
    user_name = update.message.from_user.username
    args = context.args
    if args:
        arg_list = args[0].split("_")
        if len(arg_list) == 2:
            gid, token = arg_list[0], arg_list[1]
            aaa = await update.message.reply_text("正在检测处理画廊，请稍候...")
            cs = await page(gid=gid, token=token, context=context, user_id=user_id)
            if len(cs) == 5:
                await context.bot.edit_message_media(
                    media=InputMediaPhoto(media=cs[0], caption=cs[1], parse_mode="HTML"),
                    reply_markup=cs[2],
                    chat_id=user_id,
                    message_id=aaa.message_id)
                return
            else:
                await aaa.edit_text(cs)
                return
        elif args[0] == "help":
            await update.message.reply_markdown(text=f"此bot为分布式eh归档链接获取bot\n基于[此项目](https://github.com/mhdy2233/tg-eh-distributed-arc-bot)制作")
    else:
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

async def join_addr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists("./black.json"):
        with open("./black.json", 'r', encoding='utf-8') as f:
            black_list = json.load(f)
    else:
        black_list = []
    if str(update.message.from_user.id) in black_list:
        await update.message.reply_text("你已被添加黑名单，如果这是个错误请联系管理员")
        return
    if os.path.exists("./white.json"):
        with open("./white.json", 'r', encoding='utf-8') as f:
            white_list = json.load(f)
    else:
        white_list = []
    if not str(update.message.from_user.id) in white_list:
        await update.message.reply_text("请先联系管理员添加白名单")
        return
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        pass
    user_id = update.message.from_user.id
    username = update.message.from_user.username
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

async def join_0(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text
    if not addr:
        await update.message.reply_text("请输入你的后端节点地址如：\nhttp://127.0.0.1:11451\nhttps://eh.mhdy.shop")
        return ConversationHandler.END
    context.user_data['addr'] = addr
    await update.message.reply_text("请输入绑定密钥(字符串)，不要有空格或换行如：\n1234，你好，nihao...")
    return "join_1"

async def join_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                    return ConversationHandler.END
        else:
            await update.message.reply_text(status)
            return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists("./black.json"):
        with open("./black.json", 'r', encoding='utf-8') as f:
            black_list = json.load(f)
    else:
        black_list = []
    if str(update.message.from_user.id) in black_list:
        await update.message.reply_text("你已被添加黑名单，如果这是个错误请联系管理员")
        return
    await update.message.reply_text("已取消操作")
    return ConversationHandler.END

async def ehentai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        pass
    if not update.message:
        return
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    context.user_data['user_id'] = user_id
    if os.path.exists("./black.json"):
        with open("./black.json", 'r', encoding='utf-8') as f:
            black_list = json.load(f)
    else:
        black_list = []
    if str(update.message.from_user.id) in black_list:
        await update.message.reply_text("你已被添加黑名单，如果这是个错误请联系管理员")
        return
    pattern = r"(e-hentai|exhentai)"
    if bool(re.search(pattern, update.message.text, re.IGNORECASE)):
        url = update.message.text
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        urls = urlparse(update.message.text).path.strip("/").split("/")
        gid, token = urls[1], urls[2]
        if not len(urls) == 3:
            return
        aaa = await update.message.reply_text("正在检测处理画廊，请稍候...")
        cs = await page(gid=gid, token=token, context=context, user_id=user_id)
        if len(cs) == 5:
            if update.message.chat.type == "private":
                keyboard = cs[2]
                has_spoiler=False
            elif update.message.chat.type == "supergroup" or update.message.chat.type == "group":
                if cs[4]:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("点击跳转画廊", url=cs[4]),
                        InlineKeyboardButton("在bot中打开", url=f"https://t.me/{bot_username}?start={gid}_{token}")]
                        ])
                else:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("点击跳转画廊", url=url),
                        InlineKeyboardButton("在bot中打开", url=f"https://t.me/{bot_username}?start={gid}_{token}")]
                        ])
                has_spoiler=True
            await context.bot.edit_message_media(
                media=InputMediaPhoto(media=cs[0], caption=cs[1], parse_mode="HTML", has_spoiler=has_spoiler),
                reply_markup=keyboard,
                chat_id=chat_id,
                message_id=aaa.message_id,
                )
        elif len(cs) == 1:
            await aaa.edit_text(cs)
            time.sleep(3)
            await aaa.delete()
            

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicked_text = query.data
    chat = await context.bot.get_chat(my_chat)
    data = query.data.split("|")
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        pass
    if data[0] == 'arc':
        await query.answer()
        if query.message.chat.id == chat.id:
            return
        keyboard = query.message.reply_markup.inline_keyboard  # 获取当前键盘
        # 移除该按钮
        new_keyboard = []
        for row in keyboard:
            new_row = [button for button in row if button.callback_data != clicked_text]
            if new_row:  # 只保留仍有按钮的行
                new_keyboard.append(new_row)

        # 更新键盘，如果键盘为空，则删除键盘
        if new_keyboard:
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
        else:
            await query.message.edit_reply_markup(reply_markup=None)  # 删除键盘
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
                    
    elif data[0] == 'original' or data[0] == 'resample':
        await query.answer()
        if query.message.chat.id == chat.id:
            return
        keyboard = query.message.reply_markup.inline_keyboard  # 获取当前键盘
        gid, token, use_gp = data[1], data[2], data[3]
        await query.message.edit_reply_markup(reply_markup=None)  # 移除键盘
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
                    nnn = 0
                    while True:
                        if nnn >= 5:
                            for x in config['gm_list']:
                                await context.bot.send_message(chat_id=x, text=f"{gid}画廊超过5次获取归档失败！请检查日志")
                        await cur.execute("SELECT * FROM server_data WHERE status = 'active' AND gp_status = 'active' ORDER BY RAND() LIMIT 1")
                        result = await cur.fetchone()  # 获取查询结果
                        if not result:
                            await context.bot.send_message(chat_id=query.message.chat.id, text="当前无可用服务器")
                            break
                        addr, key, server_user_id = result[4], result[5], result[2]
                        link = arc_download(addr, key, gid, token, clarity=data[0], use_gp=int(use_gp))
                        try:
                            if link[0]:
                                shanghai_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M:%S')
                                await cur.execute("UPDATE user_data SET user_gp = %s, use_gps = %s, use_num = %s, use_time = %s WHERE user_id = %s", (remnant_gp, user_data[5] + int(use_gp), user_data[6] + 1, shanghai_time, query.from_user.id))
                                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("点击跳转下载", url=link[1])]])
                                modified_link = link[1][:-9] + "2" + link[1][-9 +1:]
                                await context.bot.send_message(chat_id=query.message.chat.id, text=f"主标题：{context.user_data['主标题']}\n副标题：{context.user_data['副标题']}\n本次使用gp：{use_gp}\n剩余gp：{remnant_gp}\n下载链接默认有效期为1周，每个链接最多可以供2个ip使用。\n下载链接(可复制到多线程下载器)为：\n{modified_link}\n?号前数字为0-3, 分别为英文原图, 英文重采样, 日文原图, 日文重采样可以自己根据需要修改(不用试了不存在白嫖GP的bug)。", reply_markup=keyboard, disable_web_page_preview=True, reply_to_message_id=query.message.message_id)
                                await cur.execute("UPDATE server_data SET use_gps = %s WHERE user_id = %s", (result[9] + int(use_gp), server_user_id))
                                await cur.execute("INSERT INTO logs (time, client_id, user_id, title1, title2, url, image_url, type, use_gp, log_type) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (shanghai_time, result[0], int(query.from_user.id), context.user_data['主标题'], context.user_data['副标题'], f"{gid}|{token}", context.user_data['image'], data[0], int(use_gp), "bot"))
                                break
                            else:
                                if "GP不足" in link[1]:
                                    await cur.execute("UPDATE server_data SET gp_status = %s WHERE user_id = %s", ("inactive", server_user_id))
                                elif "Free" in link[1]:
                                    continue
                                else:
                                    await cur.execute("UPDATE server_data SET status = %s WHERE user_id = %s", ("inactive", server_user_id))
                                await context.bot.send_message(chat_id=server_user_id, text=link[1])
                                nnn +=1
                        except Exception as e:
                            for x in config['gm_list']:
                                await context.bot.send_message(chat_id=x, text=f"出现错误，错误信息：\n{e}")
                            print(f"出现错误！！！：{e}")
                            break
    elif data[0] == "yes_del":
        await query.answer()
        if not db_pool:
            print("❌ 数据库未连接！")
            return
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE server_data SET enable = %s WHERE id = %s", ("off", data[1]))
                await context.bot.send_message(chat_id=query.message.chat.id, text="停用成功")
    elif data[0] == "yes_start":
        await query.answer()
        if not db_pool:
            print("❌ 数据库未连接！")
            return
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE server_data SET enable = %s WHERE id = %s", ("on", data[1]))
                await cur.execute("SELECT * FROM server_data WHERE user_id = %s", (query.from_user.id,))
                result = await cur.fetchone()  # 获取查询结果
                addr = result[4]
                key = result[5]
                status = await addr_status(addr, token=key)
                if status == 200:
                    await context.bot.send_message(chat_id=query.message.chat.id, text="启用成功")
                else:
                    await context.bot.send_message(chat_id=query.message.chat.id, text=f"启用失败，错误如下：\n{status}")
    elif data[0] == "del":
        await query.answer()
        await query.delete_message()
    elif data[0] == "telegraph":
        # Telegraph 推送功能
        # 安全检查：确保 callback data 格式正确
        if len(data) < 4:
            await query.answer(text="数据格式错误", show_alert=False)
            return
        if not str(query.from_user.id) == data[3]:
            await query.answer(text="是你的东西吗？你就点！", show_alert=False)
        else:
            await query.answer(text="正在推送到Telegraph，请稍候...", show_alert=False)
            if query.message.chat.id == chat.id:
                return
            keyboard = query.message.reply_markup.inline_keyboard  # 获取当前键盘
            # 移除该按钮
            new_keyboard = []
            for row in keyboard:
                new_row = [button for button in row if button.callback_data != clicked_text]
                if new_row:  # 只保留仍有按钮的行
                    new_keyboard.append(new_row)

            # 更新键盘，如果键盘为空，则删除键盘
            if new_keyboard:
                await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
            else:
                await query.message.edit_reply_markup(reply_markup=None)  # 删除键盘
            
            # 发布到 Telegraph
            telegraph_url, error = await publish_to_telegraph(data[1], data[2])
            if telegraph_url:
                telegraph_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📖 查看Telegraph页面", url=telegraph_url)]
                ])
                await context.bot.send_message(
                    chat_id=query.message.chat_id, 
                    text=f"✅ 已成功推送到Telegraph！\n\n📝 主标题：{context.user_data.get('主标题', '未知')}\n📖 Telegraph链接：{telegraph_url}", 
                    reply_markup=telegraph_keyboard,
                    reply_to_message_id=query.message.message_id,
                    disable_web_page_preview=False
                )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id, 
                    text=f"❌ 推送到Telegraph失败\n错误信息：{error}", 
                    reply_to_message_id=query.message.message_id
                )
    elif data[0] == "json":
        if not str(query.from_user.id) == data[3]:
            await query.answer(text="是你的东西吗？你就点！", show_alert=False)
        else:
            await query.answer()
            if query.message.chat.id == chat.id:
                return
            keyboard = query.message.reply_markup.inline_keyboard  # 获取当前键盘
            # 移除该按钮
            new_keyboard = []
            for row in keyboard:
                new_row = [button for button in row if button.callback_data != clicked_text]
                if new_row:  # 只保留仍有按钮的行
                    new_keyboard.append(new_row)

            # 更新键盘，如果键盘为空，则删除键盘
            if new_keyboard:
                await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
            else:
                await query.message.edit_reply_markup(reply_markup=None)  # 删除键盘
            meta = await eh_meta(data[1], data[2])
            json_bytes = io.BytesIO(json.dumps(meta, indent=4, ensure_ascii=False).encode("utf-8"))
            json_bytes.name = f"{data[1]}.json"  # 设置文件名，Telegram 需要这个
            await context.bot.send_document(chat_id=query.message.chat_id, document=json_bytes, caption=f"画廊链接为：https://exhentai.org/g/{data[1]}/{data[2]}", reply_to_message_id=query.message.message_id)
    elif data[0] == "check_in":
        if not str(query.from_user.id) == data[1]:
            await query.answer(text="是你的东西吗？你就点！", show_alert=False)
        else:
            await query.answer()
            num = await check(user_id=data[1])
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("返回", callback_data=f"back|{str(query.from_user.id)}|{data[2]}")]
                ])
            if len(num) == 2:
                await query.edit_message_text(text=f"签到成功！\n获得 {num[0]} GP\n现在共有 {num[1]} GP", reply_markup=keyboard)
            else:
                await query.edit_message_text(text=num, reply_markup=keyboard)
    elif data[0] == "my_info":
        if not str(query.from_user.id) == data[1]:
            await query.answer(text="是你的东西吗？你就点！", show_alert=False)
        else:
            await query.answer()
            my_info_text = await my_info_text_(data[1], data[2])
            async with db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM server_data WHERE user_id = %s", (query.from_user.id,))
                    result = await cur.fetchone()  # 获取查询结果
                    if not result:
                        board = [
                                [InlineKeyboardButton("签到", callback_data=f'check_in|{str(query.from_user.id)}|{data[2]}'), InlineKeyboardButton("返回", callback_data=f"back|{str(query.from_user.id)}|{data[2]}")]
                            ]
                    else:
                        board = [
                                [InlineKeyboardButton("签到", callback_data=f'check_in|{str(query.from_user.id)}|{data[2]}'), InlineKeyboardButton("返回", callback_data=f"back|{str(query.from_user.id)}|{data[2]}")],
                                [InlineKeyboardButton("查看节点相关状态", callback_data=f'client|{str(query.from_user.id)}|{result[0]}')]
                            ]
                        context.user_data['token'] = result[5]
                        context.user_data['addr'] = result[4]
            keyboard = InlineKeyboardMarkup(board)
            await query.edit_message_text(text=my_info_text, reply_markup=keyboard)
    elif data[0] == "back":
        if not str(query.from_user.id) == data[1]:
            await query.answer(text="是你的东西吗？你就点！", show_alert=False)
        else:
            await query.answer()
            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("签到", callback_data=f'check_in|{data[1]}|{query.from_user.username}'), InlineKeyboardButton("查看我的信息", callback_data=f'my_info|{data[1]}|{data[2]}')]
                ]
            )
            await query.edit_message_text(text="点击按钮进行操作", reply_markup=keyboard)
    elif data[0] == "client":
        if not str(query.from_user.id) == data[1]:
            await query.answer(text="是你的东西吗？你就点！", show_alert=False)
        else:
            chat_type = update.effective_chat.type
            if not chat_type == "private":
                await query.answer(text="请不要在群组中点击", show_alert=False)
                return
            keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("点击启用client", callback_data=f"yes_start|{data[2]}")],
                    [InlineKeyboardButton("点击修改addr", callback_data="addr")],
                    [InlineKeyboardButton("点击修改token", callback_data="token")],
                    [InlineKeyboardButton("点击停用", callback_data=f"yes_del|{data[2]}")]
                ])
            async with db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM server_data WHERE id = %s", (data[2],))
                    result = await cur.fetchone()  # 获取查询结果
            await query.edit_message_text(text=f"当前client信息如下：\naddr(地址)：{result[4]}\ntoken(key)：{result[5]}\n是否启用：{result[8]}\n在线状态：{result[6]}\ngp状态：{result[7]}\n已消耗GP: {result[9]}", reply_markup=keyboard)

async def status_task(context: ContextTypes.DEFAULT_TYPE) -> None:
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
                    if row[7] == "active":
                        await context.bot.send_message(chat_id=row[2], text="GP不足，小于50000")
                        await cur.execute("UPDATE server_data SET gp_status = %s WHERE id = %s", ("inactive", row[0]))
                    elif row[7] == "inactive":
                        pass
                else:
                    if row[6] == "active":
                        await context.bot.send_message(chat_id=row[2], text=f"状态异常，错误如下(不准确)：{status}")
                        await cur.execute("UPDATE server_data SET status = %s WHERE id = %s", ("inactive", row[0]))
                    elif row[6] == "inactive":
                        pass

async def task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not user_id in config['gm_list']:
        return
    try:
        await status_task(context)
    except Exception as e:
        print(e)
        bb = e.json()
    else:
        bb = "执行完成"
    await update.message.reply_text(bb)

async def white_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    y = []
    n = []
    for arg in args:
        if arg in white_list:
            y.append(arg)
        else:
            white_list.append(arg)
            n.append(arg)
    with open("./white.json", 'w', encoding='utf-8') as f:
        json.dump(white_list, f, ensure_ascii=False)
    yy = "\n".join(y)
    nn = "\n".join(n)
    await update.message.reply_text(f"添加成功，新增用户：\n{nn}\n已添加的用户：{yy}")

async def white_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def ban_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    y = []
    n = []
    for arg in args:
        if arg in black_list:
            y.append(arg)
        else:
            black_list.append(arg)
            n.append(arg)
    with open("./black.json", 'w', encoding='utf-8') as f:
        json.dump(black_list, f, ensure_ascii=False)
    yy = "\n".join(y)
    nn = "\n".join(n)
    await update.message.reply_text(f"添加成功，封禁用户：\n{nn}\n已封禁的用户：{yy}")

async def ban_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def server_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            with open("./white.json", 'r', encoding='utf-8') as f:
                white_list = json.load(f)
            if (str(update.message.from_user.id) in white_list) and update.message.chat.type == "private":
                mes = ""
                for x in result:
                    enable_mark = "✔" if x[8] == "on" else "❌"
                    status_mark = "✔" if x[6] == "active" else "❌"
                    gp_mark = "足够" if x[7] == "active" else "GP不足"
                    
                    if x[3]:
                        mes += f"id：{x[0]} 用户： @{x[3]}\n启用：{enable_mark} 状态：{status_mark} GP状态：{gp_mark}\n\n"
                    else:
                        mes += f"id：{x[0]} 用户：<a href='tg://user?id={x[2]}'>{x[2]}</a>\n启用：{enable_mark} 状态：{status_mark} GP状态：{gp_mark}\n\n"
                message = f"当前共有 {len(result)} 个后端节点\n🟢在线可用有 {active} 个\n🛠掉线或状态异常有 {inactive} 个\n⚙️gp不足有 {gp_inactive} 个\n<blockquote expandable>{mes}</blockquote>"
            else:
                message = f"当前共有 {len(result)} 个后端节点\n🟢在线可用有 {active} 个\n🛠掉线或状态异常有 {inactive} 个\n⚙️gp不足有 {gp_inactive} 个"
            await update.message.reply_html(text=message)

async def help_(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(text=f"""此bot为分布式eh归档链接获取bot
基于[此项目](https://github.com/mhdy2233/tg-eh-distributed-arc-bot)制作

**功能说明：**
• 发送eh/ex链接获取画廊信息
• 获取元数据(JSON格式)
• 归档下载功能
• 📝 **推送到Telegraph** - 将画廊信息发布到Telegraph方便分享

**Telegraph功能：**
点击画廊预览下的"推送到Telegraph"按钮，即可将画廊详情发布到telegra.ph，生成一个可分享的链接。""")

async def addr_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # 关闭加载动画
    await query.edit_message_text("请输入addr(地址)：\n/cancel 取消")
    return "ssss"

async def addr_client_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url:
        await update.message.reply_text("请输入addr(地址)...")
        pass
    else:
        token = context.user_data['token']
        async with db_pool.acquire() as conn:  # 获取连接
            async with conn.cursor() as cur:  # 创建游标
                await cur.execute("UPDATE server_data SET addr = %s WHERE user_id = %s", (url, update.message.from_user.id))
                await update.message.reply_text(f"修改成功！\n当前addr(地址为)：{url}\ntoken(key)为：{token}")
                return ConversationHandler.END

async def token_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # 关闭加载动画
    await query.edit_message_text("请输入token(key)：\n/cancel 取消")
    return "zzzz"

async def token_client_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                    return ConversationHandler.END
        else:
            await update.message.reply_text(status)
            return ConversationHandler.END

async def last_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 5;")  # 查询最新的5条
            result = await cur.fetchall()
            if not result:
                await update.message.reply_text("没有画廊")
            else:
                captions = []
                media_group = []
                b = 0
                for x in result:
                    b += 1
                    z = str(x[6]).split("|")
                    if x[4]:
                        captions.append(f"{b}. <a href='https://exhentai.org/g/{z[0]}/{z[1]}'>{x[4]}</a>\n\n<a href='https://t.me/{bot_username}?start={z[0]}_{z[1]}'>在bot中打开</a>")
                    elif x[5]:
                        captions.append(f"{b}. <a href='https://exhentai.org/g/{z[0]}/{z[1]}'>{x[5]}</a>\n\n<a href='https://t.me/{bot_username}?start={z[0]}_{z[1]}'>在bot中打开</a>")
                for x, caption in zip(result, captions):
                    await cur.execute("SELECT * FROM message WHERE gid = %s", (str(x[6]).split("|")[0]))
                    result_ = await cur.fetchone()  # 获取查询结果（单条数据）
                    if result_:
                        media_group.append(InputMediaPhoto(media=result_[4], caption=caption, parse_mode='HTML'))
                await update.message.reply_media_group(media=media_group)

async def popular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            shanghai_time = datetime.now()
            seven_days_ago = shanghai_time - timedelta(days=7)
            await cur.execute("""
                SELECT url, title1, title2, COUNT(*) AS count 
                FROM logs 
                WHERE time >= %s 
                GROUP BY url, title1, title2
                ORDER BY count DESC 
                LIMIT 5;
            """, (seven_days_ago,))
            result = await cur.fetchall()
            if not result:
                await update.message.reply_text("没有画廊")
            else:
                captions = []
                media_group = []
                b = 0
                for x in result:
                    b += 1
                    z = str(x[0]).split("|")
                    if x[1]:
                        captions.append(f"{b}. <a href='https://exhentai.org/g/{z[0]}/{z[1]}'>{x[1]}</a>\n\n<a href='https://t.me/{bot_username}?start={z[0]}_{z[1]}'>在bot中打开</a>")
                    elif x[2]:
                        captions.append(f"{b}. <a href='https://exhentai.org/g/{z[0]}/{z[1]}'>{x[2]}</a>\n\n<a href='https://t.me/{bot_username}?start={z[0]}_{z[1]}'>在bot中打开</a>")
                for x, caption in zip(result, captions):
                    await cur.execute("SELECT * FROM message WHERE gid = %s", (str(x[0]).split("|")[0]))
                    result_ = await cur.fetchone()  # 获取查询结果（单条数据）
                    if result_:
                        media_group.append(InputMediaPhoto(media=result_[4], caption=caption, parse_mode='HTML'))
                await update.message.reply_media_group(media=media_group)

async def check_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    user_id = update.message.from_user.id
    num = await check(user_id)
    if len(num) == 2:
        await update.message.reply_text(f"签到成功！\n获得**{num[0]}**GP\n当前有**{num[1]}**GP", parse_mode='Markdown')
    else:
        await update.message.reply_text(num)

async def add_gp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not update.message.from_user.id in config['gm_list']:
        pass
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    if not len(args) ==2:
        await update.message.reply_text("未输入用户id或GP数量或格式不正确")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM user_data WHERE user_id = %s", (args[0]))
            result = await cur.fetchone()  # 获取查询结果
            if not result:
                await update.message.reply_text("该用户未注册")
            else:
                await cur.execute("UPDATE user_data SET user_gp = %s WHERE user_id = %s", (int(args[1]) + result[4], args[0]))
                await update.message.reply_text(f"添加成功现在一共有：{int(args[1]) + result[4]}GP")

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理内联查询，返回 web 相关的选项"""
    # 获取内联查询对象
    
    # 获取用户输入的查询文本
    user_input = update.inline_query.query.strip()

    button = InlineQueryResultsButton(text="到bot查看更多信息", start_parameter="help")

    # 获取发起查询的用户 ID
    user_id = update.inline_query.from_user.id
    username = update.inline_query.from_user.username
    if not user_input: 
        
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("签到", callback_data=f'check_in|{user_id}|{username}'), InlineKeyboardButton("查看我的信息", callback_data=f'my_info|{user_id}|{username}')]
            ]
        )
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),  # 需要唯一 ID
                title=f"请输入eh/ex链接已获取预览",
                input_message_content=InputTextMessageContent(f"请输入eh/ex链接")),
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),  # 需要唯一 ID
                title="我的信息(签到)",
                input_message_content=InputTextMessageContent("点击按钮进行操作"),
                description = "查看自己的信息以及签到",
                reply_markup = keyboard)
        ]
        await update.inline_query.answer(results, cache_time=0, button=button)
    else:
        pattern = r"(e-hentai|exhentai)"
        if bool(re.search(pattern, user_input, re.IGNORECASE)):
            url = user_input
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            urls = urlparse(user_input).path.strip("/").split("/")
            if not len(urls) == 3:
                pass
            else:
                gid, token = urls[1], urls[2]
                cs = await page(gid=gid, token=token, context=context, user_id=user_id)
                json_data = await eh_meta(gid, token)
                formatted_json = f"<blockquote expandable>{json.dumps(json_data, indent=4)}</blockquote>"
                if len(cs) == 5:
                    if cs[4]:
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("点击跳转画廊", url=cs[4]),
                            InlineKeyboardButton("在bot中打开", url=f"https://t.me/{bot_username}?start={gid}_{token}")]
                            ])
                    else:
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("点击跳转画廊", url=url),
                            InlineKeyboardButton("在bot中打开", url=f"https://t.me/{bot_username}?start={gid}_{token}")]
                            ])
                    results = [
                        InlineQueryResultPhoto(
                            id=str(uuid.uuid4()),  # 唯一 ID
                            photo_url=cs[0],  # 发送的图片 URL（必须是可访问的）
                            thumbnail_url=cs[0],  # 缩略图 URL（通常和 photo_url 相同，但可以使用不同的小图）
                            title=f"画廊解析",  # 仅用于显示在内联查询的选项列表中
                            description=cs[3],  # 仅用于内联查询选项列表的简要描述
                            caption=cs[1],  # 发送图片时的文本说明
                            parse_mode="HTML",
                            reply_markup=keyboard  # 发送图片时附带的按钮
                        ),
                        InlineQueryResultArticle(
                        id=str(uuid.uuid4()),  # 唯一 ID
                        title=f"json元数据",  # 内联查询结果标题
                        input_message_content=InputTextMessageContent(
                            formatted_json,  # 发送的消息内容（格式化的 JSON）
                            parse_mode="HTML"  # 使用 HTML 格式
                        ),
                        description=json_data['gmetadata'][0]['title']  # 描述，可以在内联查询中显示
                        )
                    ]
                    # 返回结果给用户
                    await update.inline_query.answer(results, cache_time=99999, button=button)
                elif len(cs) == 1:
                    results = [
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),  # 需要唯一 ID
                        title=cs,
                        input_message_content=InputTextMessageContent(cs)
                    )
                    ]
                    await update.inline_query.answer(results, cache_time=0)

async def my_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    text = await my_info_text_(user_id=user_id, username=username)
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM server_data WHERE user_id = %s", (user_id,))
            result = await cur.fetchone()  # 获取查询结果
            if not result:
                board = [
                        [InlineKeyboardButton("签到", callback_data=f'check_in|{str(user_id)}|{username}'), InlineKeyboardButton("返回", callback_data=f"back|{user_id}|{username}")]
                    ]
            else:
                board = [
                        [InlineKeyboardButton("签到", callback_data=f'check_in|{str(user_id)}|{username}'), InlineKeyboardButton("返回", callback_data=f"back|{user_id}|{username}")],
                        [InlineKeyboardButton("查看节点相关状态", callback_data=f'client|{str(user_id)}|{result[0]}')]
                    ]
                context.user_data['token'] = result[5]
                context.user_data['addr'] = result[4]
    keyboard = InlineKeyboardMarkup(board)
    await update.message.reply_text(text=text, reply_markup=keyboard)

async def give_GP(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    args = context.args
    if not len(args) ==2:
        await update.message.reply_text("未输入用户id或GP数量或格式不正确")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM user_data WHERE user_id = %s", (user_id,))
            result = await cur.fetchone()  # 获取查询结果
            if result[4] < int(args[1]):
                await update.message.reply_text("GP数量不足")
            else:
                await cur.execute("SELECT * FROM user_data WHERE user_id = %s", (args[0],))
                row = await cur.fetchone()
                if not row:
                    await update.message.reply_text("用户不存在")
                else:
                    await cur.execute("UPDATE user_data SET user_gp = %s WHERE user_id = %s", (int(args[1]) + row[4], args[0]))
                    await cur.execute("UPDATE user_data SET user_gp = %s WHERE user_id = %s", (result[4] - int(args[1]), user_id))
                    await update.message.reply_text(f"🎁赠送给用户: {args[0]} GP: {args[1]}成功，现剩余{result[4] - int(args[1])}GP")
                    await context.bot.send_message(text=f"🎁用户: {user_id} 赠送给你{args[1]}GP，现在共有{result[4] - int(args[1])}GP", chat_id=args[0])

async def eh_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    if os.path.exists("./white.json"):
        with open("./white.json", 'r', encoding='utf-8') as f:
            white_list = json.load(f)
    if str(update.message.from_user.id) in white_list:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM server_data WHERE user_id = %s", (update.message.from_user.id))  # 查询所有数据
                result = await cur.fetchone()  # 获取所有行
                if result:
                    addr, token = result[4], result[5]
                    res = await get_eh_info(addr, token)
                    if type(res) == dict:
                        message = f"<blockquote expandable>GP: \n总GP: {res['gp']['gp']}\n已用GP: {res['gp']['use_gp']}\n重置需要: {res['gp']['need_gp']}\n种子: \n上传: {res['tor']['upload']}\n下载: {res['tor']['download']}\n比率: {res['tor']['ratio']}\n完成种子: {res['tor']['torrent_completes']}\n完成画廊: {res['tor']['gallery_completes']}\n做种时间: {res['tor']['seedmins']}\nGP来源: \n浏览画廊: {res['GP_Gained']['gallery_visits']}\n完成种子: {res['GP_Gained']['torrent_completions']}\n存档下载: {res['GP_Gained']['archive_downloads']}\nH@H: {res['GP_Gained']['Hentai@Home']}\n排行: \n{', '.join(f'{k}: {v}' for k, v in res['Toplists'].items())}\n愿力: {res['power']}</blockquote>"
                        await update.message.reply_html(message)
                    else:
                        await update.message.reply_text(f"出现问题: \n{res}")

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
    await app.bot.set_my_commands(COMMANDS, scope=BotCommandScopeDefault())
    if os.path.exists("./white.json"):
        with open("./white.json", 'r', encoding='utf-8') as f:
            white_list = json.load(f)
            for x in white_list:
                await app.bot.set_my_commands(WHITE_COMMANDS, scope=BotCommandScopeChat(chat_id=x))
    for x in config['gm_list']:
        await app.bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=x))

async def on_mysql(update: Update):
    user_id = update.message.from_user.id
    if not user_id in config['gm_list']:
        return
    global db_pool
    db_pool = await init_db_pool()
    if db_pool:
        await update.message.reply_text("数据库已启用")

async def off_mysql(update: Update):
    user_id = update.message.from_user.id
    if not user_id in config['gm_list']:
        return
    global db_pool
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        await update.message.reply_text("数据库已关闭")

def main():
    """主函数"""
    app = Application.builder().token(bot_token).request(HTTPXRequest(connect_timeout=30,read_timeout=30,pool_timeout=30)).build()

    # 添加命令处理器
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check_in", check_in))
    app.add_handler(CommandHandler("last_page", last_page))
    app.add_handler(CommandHandler("popular", popular))
    app.add_handler(CommandHandler("server_list", server_list))
    app.add_handler(CommandHandler("my_info", my_info))
    app.add_handler(CommandHandler("give_gp", give_GP))
    app.add_handler(CommandHandler("eh_info", eh_info))
    app.add_handler(CommandHandler("white_add", white_add))
    app.add_handler(CommandHandler("white_del", white_del))
    app.add_handler(CommandHandler("ban", ban_add))
    app.add_handler(CommandHandler("ban_del", ban_del))
    app.add_handler(CommandHandler("help", help_))
    app.add_handler(CommandHandler("add_gp", add_gp))
    app.add_handler(CommandHandler("on_mysql", on_mysql))
    app.add_handler(CommandHandler("off_mysql", off_mysql))
    app.add_handler(CommandHandler("task", task))

    app.add_handler(join_handler)
    app.add_handler(addr_handler)
    app.add_handler(token_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ehentai))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.add_handler(InlineQueryHandler(inline_query))

    app.job_queue.run_once(on_startup, 3)
    app.job_queue.run_once(mysql_, 5)

    app.post_init = register_commands

    app.job_queue.run_repeating(status_task, interval=300)
    app.job_queue.run_repeating(tag_mysql, interval=86400)

    print("🤖 Bot 正在运行...")
    app.run_polling()

if __name__ == "__main__":
    main()
