import aiomysql, yaml
from datetime import datetime
from zoneinfo import ZoneInfo
from eharc import arc_download
from collections import defaultdict
import ipaddress

with open("./config.yml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

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

async def on_startup():
    global db_pool
    db_pool = await init_db_pool()
    print("✅ MySQL 数据库连接池已创建！")
    if not db_pool:
        on_startup()
        if not db_pool:
            print("❌ 数据库未连接，无法创建表！")
            return
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS api_key (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT,
                    name VARCHAR(255),
                    key_hash VARCHAR(255),
                    user_gp BIGINT,
                    use_gps BIGINT DEFAULT 0,
                    use_num BIGINT DEFAULT 0,
                    use_time DATETIME
                )
            """)

async def on_shutdown():
    global db_pool
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        print("❌ MySQL 连接池已关闭！")

async def store_api_key(raw_key: str, GP):
    global db_pool
    from auth import hash_api_key
    hashed = hash_api_key(raw_key)
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            await cur.execute("INSERT INTO api_key (key_hash, user_gp) VALUES (%s, %s)", (hashed, GP))

async def verify_api_key(raw_key: str):
    global db_pool
    from auth import hash_api_key
    hashed = hash_api_key(raw_key)
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            await cur.execute("SELECT * FROM api_key WHERE key_hash = %s", (hashed))
            result = await cur.fetchone()  # 获取查询结果（单条数据）
            if not result:
                return None
            data = result[3]
    if data == hashed:
        return result
    return None

async def arc_download_url(gid, token, clarity, use_gp, title1, title2, image_url, log_type, user_ip= None):
    nnn = 0
    global db_pool
    while True:
        if nnn < 5:
            async with db_pool.acquire() as conn:  # 获取连接
                async with conn.cursor() as cur:  # 创建游标
                    await cur.execute("SELECT * FROM server_data WHERE status = 'active' AND gp_status = 'active' ORDER BY RAND() LIMIT 1")
                    result = await cur.fetchone()  # 获取查询结果
                    if not result:
                        break
                    addr, key, server_user_id = result[4], result[5], result[2]
                    link = arc_download(addr, key, gid, token, clarity=clarity, use_gp=use_gp)
                    try:
                        if link[0]:
                            shanghai_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M:%S')
                            await cur.execute("UPDATE server_data SET use_gps = %s WHERE user_id = %s", (result[9] + int(use_gp), server_user_id))
                            await cur.execute("INSERT INTO logs (time, client_id, user_id, title1, title2, url, image_url, type, use_gp, log_type) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (shanghai_time, result[0], int(ipaddress.IPv4Address(user_ip)) if user_ip else 1234, title1, title2, f"{gid}|{token}", image_url, clarity, int(use_gp), log_type))
                            return link[1]
                        else:
                            if "Free" in link[1]:
                                continue
                            nnn +=1
                    except Exception as e:
                        print(f"出现错误！！！：{e}")
                        break
        else:
            break

async def use_gp_api_key(dow_gp, use_gps, use_num, key_hash):
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            await cur.execute("UPDATE api_key SET user_gp = %s, use_gps = %s, use_num = %s WHERE key_hash = %s", (dow_gp, use_gps, use_num, key_hash))

async def get_db():
    global db_pool
    async with db_pool.acquire() as conn:  # 获取连接
        async with conn.cursor() as cur:  # 创建游标
            await cur.execute("SELECT * FROM logs")
            result = await cur.fetchall()
            return result
        

async def get_translations(english_words):
    global db_pool
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
    # 确保英文字词列表不为空
    if not english_words:
        return []
    global db_pool
    if not db_pool:
        print("❌ 数据库未连接！")
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
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
        