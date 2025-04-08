import yaml, requests, random, re, io, time, os, json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse
from datetime import datetime

with open("./config.yml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
def obtain_cover(img_url):
    """获取画廊封面

    Args:
        soup (_type_): 页面

    Returns:
        _type_: _description_
    """
    response = requests.get(img_url, cookies=random.choice(config['eh_cookies']), proxies=random.choice(config['proxy']))

    if response.status_code == 200:
        # 将图片数据保存到内存中的 BytesIO 对象
        img_data = io.BytesIO(response.content)
        img_data.seek(0)  # 将游标重置到文件开头
    return img_data

async def addr_status(addr,token):
    data = {
        "key": token
    }
    url = addr + "/api/status"
    try:
        ceshi = requests.post(url, json=data, timeout=5).json()
    except requests.exceptions.InvalidSchema:
        return "地址无效"
    except requests.exceptions.Timeout:
        return "超时"
    except requests.exceptions.MissingSchema:
        return "不是https?://url格式"
    except Exception as e:
        return e
    else:
        if ceshi.get("status", 0) == 200:
            return 200
        else:
            return ceshi['error']
    
async def eh_page(gid, token):
    eh_cookie = random.choice(config['eh_cookies'])
    url = "https://exhentai.org/g/" + str(gid) + "/" + str(token)
    print(url)
    eh = requests.get(url, cookies=eh_cookie, proxies=random.choice(config['proxy']))
    if eh.status_code == 200:
        if eh.text == "Key missing, or incorrect key provided.":
            return 400
        soup = BeautifulSoup(eh.text, 'html.parser')
        if not soup:
            return 501
        match = re.search(r'url\((https?://[^\s)]+)\)', soup.find("div", style=re.compile(r'url\((.*?)\)'))['style'])
        if match:
            img_url = match.group(1)
        image = obtain_cover(urlunparse(urlparse(img_url)._replace(netloc="ehgt.org")))  # 获取画廊封面数据
        title1 = soup.find('h1', id='gn').text   # 主标题
        title2 = soup.find('h1', id='gj').text   # 副标题
        page_type = soup.find('div', id='gdc').text.lower()  # 画廊类型
        uploader = f"<a href='{soup.find('div', id='gdn').find('a')['href']}'>{soup.find('div', id='gdn').find('a').text}</a>"    # 上传者
        posted = soup.find_all('td', class_='gdt2')[0].text   # 上传时间
        language = soup.find_all('td', class_='gdt2')[3].text.lower()   # 语言
        size = soup.find_all('td', class_='gdt2')[4].text   # 大小
        pages = soup.find_all('td', class_='gdt2')[5].text.split(" ")[0]   # 页数
        favorited = soup.find_all('td', class_='gdt2')[6].text.split(" ")[0]   # 收藏数
        average = soup.find('td', id='rating_label').text.split(" ")[1]    # 评分
        labels = []
        for x in soup.find('div', id='taglist').find_all('tr'):
            tag_type = [x.find('td', class_='tc').text.replace(":", "")]
            tags = [a.get_text(strip=True) for a in x.find_all('a')]
            b = tag_type + tags
            labels.append(b)
        caption = [title1, title2, page_type, uploader, posted, language, size, pages, favorited, average, labels]
        comment = soup.find('div', id='cdiv').find_all('div', class_='c1')
        com = ""
        for x in comment:
            tt = x.find('div', class_='c3').decode_contents()
            # 提取时间字符串
            time_str = tt.split("Posted on ")[1].split(" by:")  # '01 April 2022, 20:15'
            # 解析时间
            dt = datetime.strptime(time_str[0], "%d %B %Y, %H:%M")
            # 转换为标准格式
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            try:
                score = x.find('div', class_='c5').text
            except AttributeError:
                score = None
            try:
                message = x.find('div', class_='c6').text
            except:
                message = None
            mes = f"{formatted_time} by：{time_str[1]}  {score}\n   {message}\n"
            if len(com) + len(mes) > 700:
                continue
            else:
                com += mes
        return image, caption, img_url, com
    elif eh.status_code == 403:
        return 403
    elif eh.status_code == 404:
        return 404
    else:
        return 500

def convert_to_mib(value):
    """_summary_

    Args:
        value (str): 提取出的画廊大小

    Returns:
        _type_: _description_
    """
    match = re.match(r"([\d.]+)\s*(MiB|GiB)", value, re.IGNORECASE)
    if not match:
        return None  # 无法匹配格式，返回 None
    
    number, unit = match.groups()
    number = float(number)

    if unit.lower() == "gib":  # GiB 转换为 MiB
        number *= 1024

    return int(number) if number.is_integer() else number

def eh_arc(gid, token):
    url = f"https://exhentai.org/archiver.php?gid={gid}&token={token}"
    arc = requests.get(url=url, cookies=random.choice(config['eh_cookies']), proxies=random.choice(config['proxy']))

    soup = BeautifulSoup(arc.text, 'html.parser')
    if soup == "This gallery is currently unavailable.":
        return "该画廊目前不可用"
    strong = soup.find_all('strong')
    original_size = convert_to_mib(strong[1].text)   # 原图大小
    resample_size = convert_to_mib(strong[3].text)   # 重彩样大小
    if strong[2].text == "Free!":
        original_gp = round(original_size / 0.063)
        resample_gp = round(resample_size / 0.063)
    elif strong[2].text == "N/A" and strong[0].text == "Free!":
        original_gp = round(int(strong[0].text.split(" ")[0].replace(",", "")))
        resample_gp = "N/A"
    else:
        original_gp = round(int(strong[0].text.split(" ")[0].replace(",", "")))
        resample_gp = round(int(strong[2].text.split(" ")[0].replace(",", "")))
    size = [original_size, resample_size]
    gp = [round(original_gp), resample_gp]
    return size, gp

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

async def eh_page_meta(gid, token):
    page_meta = await eh_meta(gid, token)
    if page_meta['gmetadata'][0].get('error'):
        return 500
    else:
        data = page_meta['gmetadata'][0]
        title1 = data['title']
        title2 = data['title_jpn']
        page_type = data['category'].lower()
        uploader = f"<a href='https://exhentai.org/uploader/{data['uploader']}'>{data['uploader']}</a>"
        posted = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(data['posted'])))
        size = str(round(data['filesize'] / 1048576, 1)) + "MB"
        pages = data['filecount']
        average = data['rating']
        labels = data['tags']
        img_url = data['thumb']
        if data['expunged'] == True:
            labels.append("other:已删除")
        caption = [title1, title2, page_type, uploader, posted, size, pages, average, labels]
        return img_url, caption
    
async def eh_dmca(gid):
    if os.path.exists("./ehdmca.json"):
        with open("./ehdmca.json", 'r', encoding='utf-8') as f:
            ehdmca = json.load(f)
            if gid in ehdmca:
                ehdmca_page = ehdmca[gid]
                gg = ehdmca_page['archive'].split('<')
                if gg[0] == "chaika":
                    return gg[1].replace('>', '')
                elif gg[0] == "local" or gg[0] == "":
                    return None
                else:
                    if "in" in gg[0]:
                        zs = gg[0].split(' in ')
                        if zs[1] == "DMCA":
                            return None
                        else:
                            url = "https://pan1.mhdy.shop/主要/本子/eh_DMCA/" + zs[1] + f"/{zs[0]}_{ehdmca_page['title'].replace("|", "")}.zip"
                            return url
                    else:
                        url = "https://pan1.mhdy.shop/主要/本子/eh_DMCA/" + gg[0] + f"/{gid}_{ehdmca_page['title'].replace("|", "")}.zip"
                        return url
            else:
                return None
    else:
        return None