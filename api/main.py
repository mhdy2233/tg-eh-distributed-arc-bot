from fastapi import FastAPI, Request, HTTPException, Depends, Form
from typing import AsyncGenerator
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, func
from contextlib import asynccontextmanager
from db import verify_api_key, store_api_key, on_startup, on_shutdown, arc_download_url, use_gp_api_key
from auth import generate_api_key
from eharc import eh_arc, eh_page_meta, eh_meta
import yaml, asyncio
from database import SessionLocal
from models import Record, Item, GP, Hot
from sqlalchemy.orm import Session
from urllib.parse import urlparse
from datetime import datetime, timedelta

with open("./config.yml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 👇 全局缓存变量
cached_data = None
hot_data = None
called_ips = set()  # 记录已经访问过的 IP
# 创建一组初始 API Key（模拟用户注册）
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    print("🚀 正在启动 API 服务...")
    await on_startup()
    print("✅ 启动完成。")
    global cached_data, hot_data
    cached_data = await get_data_from_db()
    hot_data = await get_hot_data()
    async def refresh_loop():
        global cached_data, hot_data
        while True:
            print("🔄 正在刷新数据缓存...")
            cached_data = await get_data_from_db()
            hot_data = await get_hot_data()
            await asyncio.sleep(300)  # 每5分钟刷新
    asyncio.create_task(refresh_loop())
    yield
    print("🔻 正在关闭 API 服务...")
    await on_shutdown()
    print("✅ 服务关闭完成。")
    # api_key = generate_api_key()
    # await store_api_key(api_key, 1000)
    # print(f"🔑 Your API Key: {api_key}")

# 依赖项：校验 API Key
async def api_key_required(request: Request):
    key = request.headers.get("X-API-Key")
    if not key:
        raise HTTPException(status_code=401, detail="Missing API Key")
    user_data = await verify_api_key(key)
    if not user_data:
        raise HTTPException(status_code=403, detail="Invalid or inactive API Key")
    
    return user_data

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/create-key")
async def create_key(GP: GP, request: Request):
    data = GP.model_dump()
    # 限制 IP：仅允许 127.0.0.1 访问
    client_host = request.client.host
    if client_host != "127.0.0.1":
        raise HTTPException(status_code=403, detail="Access denied: Only localhost is allowed.")
    
    # 创建 API Key
    api_key = generate_api_key()

    # 假设为 user_id=1 存储
    await store_api_key(api_key, data['gp'])

    return {"message": "API Key Created", "api_key": api_key}

# 示例受保护路由
@app.get("/left")
def secure_data(user=Depends(api_key_required)):
    return {"message": f"api-key正常，剩余GP: {user[4]}GP，已使用: {user[5]}GP，使用次数: {user[6]}，最后一次使用时间: {user[7]}"}

async def get_data_from_db():
    db: Session = SessionLocal()
    data = db.query(Record).order_by(desc(Record.id)).limit(20).all()
    db.close()
    for item in data:
        item.image_url = item.image_url.replace(item.image_url.split('/')[2], 'ehgt.org')
        item.url = "https://exhentai.org/g/" + item.url.replace("|", "/")
    return data


async def get_hot_data():
    db: Session = SessionLocal()
    shanghai_time = datetime.now()
    seven_days_ago = shanghai_time - timedelta(days=7)

    # 先查前 10 热门的 URL
    hot_urls = (
        db.query(
            Hot.url,
            Hot.title1,
            func.count(Hot.id).label("count")
        )
        .filter(Hot.time >= seven_days_ago)
        .group_by(Hot.url, Hot.title1)
        .order_by(desc("count"))
        .limit(10)
        .all()
    )

    # 再用这些 URL 去查对应记录（取最新一条）
    hot_data = []
    for item in hot_urls:
        record = (
            db.query(Hot)
            .filter(Hot.url == item.url)
            .order_by(Hot.time.desc())
            .first()
        )
        if record:
            fixed_image_url = record.image_url.replace(record.image_url.split('/')[2], 'ehgt.org')
            hot_data.append({
                "url": "https://exhentai.org/g/" + record.url.replace("|", "/"),
                "title": record.title1,
                "image_url": fixed_image_url,
                "id": record.id,
                "count": item.count  # 热门次数
            })

    return hot_data

# 示例公开路由
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    global cached_data, hot_data
    return templates.TemplateResponse("index.html", {"request": request, "data": cached_data, "hot_data": hot_data})

@app.post("/parse")
async def parse(link: str = Form(...)):
    api_data = await eh_page_meta(link)
    if not api_data:
        return 
    print(api_data)
    return JSONResponse(content=api_data)

@app.post("/create-item")
async def create_item(item: Item, user = Depends(api_key_required)):
    # 如果通过 API Key 验证，返回处理后的 JSON 响应
    if type(item) == dict:
        data = item
    else:
        data = item.model_dump()
    print(data)
    gps = await eh_arc(data['gid'], data['token'])
    if data['clarity'] == "original":
        use_gp = gps[0]
    elif data['clarity'] == "resample":
        use_gp = gps[1]
    if use_gp == "N/A":
        return {"code": 401, "msg": "无选项"}
    dow_gp = user[4] - int(use_gp)
    if dow_gp < 0:
        return {
            "code": 500,
            "message": f"GP不足，剩余GP为：{user[4]}"
        }
    meta = await eh_meta(data['gid'], data['token'])
    eh_url = await arc_download_url(gid=data['gid'], token=data['token'], clarity=data['clarity'], use_gp=use_gp, title1=meta["gmetadata"][0]['title'], title2=meta["gmetadata"][0]['title_jpn'], image_url=meta["gmetadata"][0]['thumb'], log_type="key")
    if eh_url:
        await use_gp_api_key(dow_gp, use_gps=user[5] + int(use_gp), use_num=user[6]+1, key_hash=user[3])
        return {
            "code": 200,
            "gid": data['gid'],
            "eh_arc_download_url": eh_url,
            "use_gp": use_gp,
            "user_gp": dow_gp,
            "use_num": user[6]+1,
            "meta": meta
        }

@app.post("/arc")
async def arc(link: str = Form(...), clarity: bool = Form(...), api_key: str = Form(...), request: Request = None):
    if not link.startswith(("http://", "https://")):
        link = "https://" + link
    urls = urlparse(link).path.strip("/").split("/")
    if not len(urls) == 3:
        return
    gid, token = urls[1], urls[2]
    gps = await eh_arc(gid, token)
    if clarity == False:
        clarity = "original"
        use_gp = gps[0]
    elif clarity == True:
        clarity = "resample"
        use_gp = gps[1]
    if not api_key:
        user_ip = request.client.host
        if not '.' in user_ip and user_ip.count('.') == 3:
            prefix = str(user_ip).split(":")[:4]
            called_ips.add(prefix)
            user_ip = request.headers.get("X-Forwarded-For")
            if not '.' in user_ip and user_ip.count('.') == 3:
                user_ip = request.headers.get("Cf-Pseudo-IPv4")  # Cloudflare 提供的真实 IP
        if user_ip in called_ips:
            return JSONResponse(content={"code": 429, "msg": "一天只能用一次！"})
        else:
            meta = await eh_meta(gid, token)
            url = await arc_download_url(gid=gid, token=token, clarity=clarity, use_gp=use_gp, user_ip=user_ip, title1=meta["gmetadata"][0]['title'], title2=meta["gmetadata"][0]['title_jpn'], image_url=meta["gmetadata"][0]['thumb'], log_type="web")
            if url:
                api_data = {
                    "title1": meta["gmetadata"][0]['title'],
                    "title2": meta["gmetadata"][0]['title_jpn'],
                    "use_gp": use_gp,
                    "image_url": meta["gmetadata"][0]['thumb'],
                    "download_url": url[:-9] + "2" + url[-9 +1:]
                }
                print(api_data)
                called_ips.add(user_ip)
                return JSONResponse(content=api_data)
    else:
        async def api_key_requireds(api_key):
            if not api_key:
                return {"code": 401, "msg": "无密钥"}
            user_data = await verify_api_key(api_key)
            if not user_data:
                return {"code": 403, "msg": "密钥错误"}
            return user_data
        if api_key[:6] == "eh_arc":
            user = await api_key_requireds(api_key)
            if type(user) == tuple:
                result = await create_item(item={"gid": gid, "token": token, "clarity": clarity}, user=user)
                if result['code'] == 200:
                    api_data = {
                        "title1": result['meta']["gmetadata"][0]['title'],
                        "title2": result['meta']["gmetadata"][0]['title_jpn'],
                        "use_gp": use_gp,
                        "image_url": result['meta']["gmetadata"][0]['thumb'],
                        "download_url": result['eh_arc_download_url'][:-9] + "2" + result['eh_arc_download_url'][-9 +1:],
                        "user_gp": result['user_gp'],
                        "use_num": result['use_num']
                    }
                    print(api_data)
                    return JSONResponse(content=api_data)
            else:
                return JSONResponse(content={"code": 429, "msg": user['msg']})
        else:
            return JSONResponse(content={"code": 429, "msg": "密钥错误"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许访问的源
    allow_credentials=True,  # 是否允许携带 cookie
    allow_methods=["*"],  # 允许的方法（GET、POST等）
    allow_headers=["*"],  # 允许的请求头
)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config['port'])