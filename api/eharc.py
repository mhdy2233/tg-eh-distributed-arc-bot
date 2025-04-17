import requests, random, yaml, re, time
from bs4 import BeautifulSoup
from urllib.parse import urlparse

with open("./config.yml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

async def convert_to_mib(value):
    match = re.match(r"([\d.]+)\s*(MiB|GiB|KiB)", value, re.IGNORECASE)
    if not match:
        return None  # 无法匹配格式，返回 None
    
    number, unit = match.groups()
    number = float(number)

    if unit.lower() == "gib":  # GiB 转换为 MiB
        number *= 1024

    return int(number) if number.is_integer() else number

async def eh_arc(gid, token):
    url = f"https://exhentai.org/archiver.php?gid={gid}&token={token}"
    arc = requests.get(url=url, cookies=random.choice(config['eh_cookies']), proxies=random.choice(config['proxy']))

    soup = BeautifulSoup(arc.text, 'html.parser')
    if soup == "This gallery is currently unavailable.":
        return "该画廊目前不可用"
    strong = soup.find_all('strong')
    original_size = await convert_to_mib(strong[1].text)   # 原图大小
    resample_size = await convert_to_mib(strong[3].text)   # 重彩样大小
    if strong[2].text == "Free!":
        resample_gp = round(resample_size / 0.063)
    elif strong[2].text == "N/A":
        resample_gp = "N/A"
    else:
        resample_gp = round(int(strong[2].text.split(" ")[0].replace(",", "")))
    if strong[0].text == "Free!":
        original_gp = round(original_size / 0.063)
    elif strong[0].text == "N/A":
        original_gp = "N/A"
    else:
        original_gp = round(int(strong[0].text.split(" ")[0].replace(",", "")))
    gp = [original_gp, resample_gp]
    return gp

def arc_download(addr, key, gid, token, clarity, use_gp):
    url = addr + "/api/url"
    data = {
        "key": key,
        "gid": gid,
        "token": token,
        "arc": clarity,
        "use_gp": use_gp
    }
    arc = requests.post(url=url, json=data)
    if arc.status_code == 200:
        link = arc.json().get("link", False)
        if not link:
            error = arc.json().get("error", False)
            if "GP不足" in error:
                return False, error
            else:
                return False, error
        else:
            return True, link
        
async def eh_meta(gid, token):
    api = "https://e-hentai.org/api.php"
    data = {
    "method": "gdata",
    "gidlist": [
        [gid,token]
    ],
    "namespace": 1
    }
    meta = requests.post(url=api, json=data).json()
    return meta

async def eh_page_meta(link):
    from db import get_translations
    if not link.startswith(("http://", "https://")):
        link = "https://" + link
    urls = urlparse(link).path.strip("/").split("/")
    gid, token = urls[1], urls[2]
    page_meta = await eh_meta(gid, token)
    if page_meta['gmetadata'][0].get('error'):
        return 500
    else:
        data = page_meta['gmetadata'][0]
        title1 = data['title']
        page_type = data['category'].lower()
        uploader = f"<a href='https://exhentai.org/uploader/{data['uploader']}'>{data['uploader']}</a>"
        posted = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(data['posted'])))
        size = str(round(data['filesize'] / 1048576, 1)) + "MB"
        pages = data['filecount']
        average = data['rating']
        labels = data['tags']
        img_url = data['thumb']
        tar = await get_translations(labels)
        api_data = {
            "title": title1,
            "page_type": page_type,
            "image_url": img_url,
            "uploader": uploader,
            "posted": posted,
            "size": size,
            "pages": pages,
            "average": average,
            "labels": tar,
        }
        return api_data