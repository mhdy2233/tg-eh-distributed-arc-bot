import yaml, requests, random, re, io
from bs4 import BeautifulSoup

with open("./config.yml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

def obtain_cover(eh_text):
    """获取画廊封面

    Args:
        soup (_type_): 页面

    Returns:
        _type_: _description_
    """
    soup = BeautifulSoup(eh_text, 'html.parser')
    div = soup.find("div", style=re.compile(r'url\((.*?)\)'))  
    match = re.search(r'url\((https?://[^\s)]+)\)', div['style'])
    if match:
        img_url = match.group(1)
        response = requests.get(img_url, cookies=random.choice(config['eh_cookies']))
    
        if response.status_code == 200:
            # 将图片数据保存到内存中的 BytesIO 对象
            img_data = io.BytesIO(response.content)
            img_data.seek(0)  # 将游标重置到文件开头
        return img_data
    else:
        return False

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
    eh = requests.get(url, cookies=eh_cookie)
    if eh.status_code == 200:
        if eh.text == "Key missing, or incorrect key provided.":
            return 400
        soup = BeautifulSoup(eh.text, 'html.parser')
        if not soup:
            return 501
        image_url = obtain_cover(eh.text)  # 获取画廊封面数据
        title1 = soup.find('h1', id='gn').text   # 主标题
        title2 = soup.find('h1', id='gj').text   # 副标题
        page_type = soup.find('div', id='gdc').text.lower()  # 画廊类型
        uploader = soup.find('div', id='gdn').find('a').text    # 上传者
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
        return image_url, caption
    elif eh.status_code == 403:
        return 403
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
    url = "https://e-hentai.org/archiver.php?" + f"gid={gid}" + "&" + f"token={token}"
    arc = requests.get(url=url, cookies=random.choice(config['eh_cookies']))

    soup = BeautifulSoup(arc.text, 'html.parser')
    if soup == "This gallery is currently unavailable.":
        return "该画廊目前不可用"
    strong = soup.find_all('strong')
    original_size = convert_to_mib(strong[1].text)   # 原图大小
    resample_size = convert_to_mib(strong[3].text)   # 重彩样大小
    if strong[2].text == "Free!":
        original_gp = round(original_size / 0.063)
        resample_gp = round(original_size / 0.063)
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
        
        