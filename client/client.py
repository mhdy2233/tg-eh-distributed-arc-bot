import requests, logging, yaml, random
from bs4 import BeautifulSoup
from flask import request, Flask, jsonify, redirect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta, timezone

with open("./config.yml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
proxies = config.get('proxies', {})

# 定义上海时区（UTC+8）
SHANGHAI_TZ = timezone(timedelta(hours=8))

# 自定义 formatter 以使用上海时间
class ShanghaiFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, SHANGHAI_TZ)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            s = dt.isoformat()
        return s

# 设置日志格式和 handler
log_format = "[%(asctime)s] [%(levelname)s] %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"
console = logging.StreamHandler()
handler = logging.FileHandler("eh_arc_log.txt")
handler.setFormatter(ShanghaiFormatter(log_format, datefmt=date_format))

# 让 console 也用上海时间格式
console.setFormatter(ShanghaiFormatter(log_format, datefmt=date_format))

# 应用日志配置：输出到文件 + 控制台
logging.basicConfig(
    level=logging.INFO,
    handlers=[handler, console]
)

def detection(gid,token,clarity,use_gp,eh_cookie):
    # 检测是否有下载链接
    arc_url = "https://exhentai.org/archiver.php" + f"?gid={gid}" + f"&token={token}"
    response = requests.get(arc_url, cookies=eh_cookie, proxies=proxies)
    soup = BeautifulSoup(response.text, 'html.parser')
    free = soup.find_all('strong')
    if config['Free']:
        if clarity == "original":
            if free[0].text == "Free!":
                return False, "Free"
        elif clarity == "resample":
            if free[0].text == "Free!":
                return False, "Free"
    if not free[0].text == "Free!":
        url = "https://e-hentai.org/archiver.php?gid=3285545&token=7745b19f1e"
        response = requests.get(url, cookies=eh_cookie, proxies=proxies)
        soup = BeautifulSoup(response.text, 'html.parser')
        for x in soup.find_all('p'):
            if "GP" in x.text and "Credits" in x.text:
                m_list = x.text.replace("[", "").replace("]", "").replace("?", "").replace(",", "").split()
                if m_list[0] - use_gp < 0:
                    return False, f"GP不足，GP还剩余{[m_list[0]]}，C还剩余{[m_list[2]]}"
    if soup.find('a', onclick="return cancel_sessions()"):
        if refresh_url(gid=gid, token=token, eh_cookie=eh_cookie):
            logging.info("销毁成功")
        else:    
            return False, "链接销毁失败"

    link = download_url(gid,token,clarity,eh_cookie)
    return link

def download_url(gid,token,clarity,eh_cookie):
    # 获取下载链接
    if clarity == "original":
        clarity = "Original"
        cc = "org"
    elif clarity == "resample":
        clarity = "Resample"
        cc = "res"
    payload = {
        "dltype": cc,
        "dlcheck": f"Download {clarity} Archive",  # 按钮对应的名字和按钮值
    }
    arc_url = f"https://exhentai.org/archiver.php?gid={gid}&token={token}"
    response = requests.post(arc_url, data=payload, cookies=eh_cookie, proxies=proxies)
    # 对下载原始图像进行post请求
    if response.status_code == 200:
        logging.info("请求原始图像成功")
        if response.text != "You do not have enough funds to download this archive. Obtain some Credits or GP and try again.":
            soup = BeautifulSoup(response.text, 'html.parser')
            url = soup.find('a')["href"]
            link_original = url + "?start=1"
            return True, link_original
        elif "This IP address has been" in response.text:
            return False, "IP频率过高"
        else:
            return False, "GP不足"
    else:
        code = response.status_code
        logging.error(f"请求原始图像失败，错误代码为：{code}")
        return False, code

def refresh_url(gid, token, eh_cookie):
    # 销毁下载链接
    payload = {
        "invalidate_sessions": 1,
    }
    arc_url = f"https://exhentai.org/archiver.php?gid={gid}&token={token}"
    response = requests.post(arc_url, data=payload, cookies=eh_cookie, proxies=proxies)
    if response.status_code == 200:
        return True
    else:
        return False

app = Flask(__name__)
CORS(app)

# 设置 IP 限制器
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1000 per hour"]  # 默认全局限制
)

@app.route('/api/url', methods=['POST', 'GET'])
@limiter.limit("100 per minute")  # 单独给这个路由加限制
def process_data():
    if request.method == 'POST':
        try:
            # 获取 JSON 数据
            data = request.get_json()
            if not data:
                return jsonify({"error": "请求体不能为空"})
            
            if data["key"] == config['key']:
                # 处理数据（获取gid和token然后获取下载链接）
                gid = data['gid']
                token = data['token']
                clarity = data['arc']
                use_gp = data['use_gp']
                eh_cookie = random.choice(config['eh_cookies'])
                link = detection(gid, token, clarity, use_gp, eh_cookie)
                logging.info(f"获取到画廊请求:{gid}")
                if link[0]:
                    logging.info(f"请求成功, 使用cookie_id为：{eh_cookie['ipb_member_id']}, 链接为：{link}")
                    # 构造返回结果(返回画廊原图下载链接)
                    response = {
                        "link": link[1]
                    }
                    return jsonify(response)
                else:
                    logging.error(f"请求失败{link}")
                    return jsonify({"error": str(link[1])})
            else:
                logging.error("密钥错误，获取归档失败！")
                return jsonify({"error": "密钥错误！"})
        except Exception as e:
            return jsonify({"error": str(e)})
    if request.method == 'GET':
        # 处理 GET 请求，进行 302 重定向
        print("处理 GET 请求 - 重定向到另一个路径")
        return redirect("https://www.mohuangdiyu.com")  # 可以根据需求更改重定向的 URL

@app.route('/api/status', methods=['POST'])
def status():
    data = request.get_json()
    if data["key"] == config['key']:
        while True:
            eh_cookie = random.choice(config['eh_cookies'])
            ceshi = requests.get("https://exhentai.org", cookies=eh_cookie, proxies=proxies)
            if ceshi.status_code == 200:
                if not ceshi.text:
                    num -=1
                    if num <= 0:
                        logging.error(f"cookie_id为：{eh_cookie['ipb_member_id']}, 里站无内容，请检查cookie是否正确")
                        return jsonify({"error": f"cookie_id为：{eh_cookie['ipb_member_id']}, 里站无内容，请检查cookie是否正确"})
                    else:
                        continue
                cc = requests.get("https://e-hentai.org/archiver.php?gid=3285402&token=9cf3194f42", cookies=eh_cookie, proxies=proxies)
                if cc.status_code ==200:
                    if "login" in cc.url:
                        logging.error(f"cookie_id为：{eh_cookie['ipb_member_id']}, 请求表站跳转登录，请检查cookie")
                        return jsonify({"error": f"cookie_id为：{eh_cookie['ipb_member_id']}, 请求表站跳转登录，请检查cookie"})
                    soup = BeautifulSoup(cc.text, 'html.parser')
                    for x in soup.find_all('p'):
                        if "GP" in x.text and "Credits" in x.text:
                            m_list = x.text.replace("[", "").replace("]", "").replace("?", "").split()
                            if int(m_list[0].replace(",", "")) > 50000:
                                logging.info("状态正常")
                                return jsonify({"status": 200})
                            else:
                                logging.error(f"cookie_id为：{eh_cookie['ipb_member_id']}, GP小于50000无法加入")
                                return jsonify({"error": f"cookie_id为：{eh_cookie['ipb_member_id']}, GP小于50000"})
                else:
                    num -=1
                    if num <= 0:
                        logging.error(f"cookie_id为：{eh_cookie['ipb_member_id']}, 表站请求出错，检查网络")
                        return jsonify({"error": f"cookie_id为：{eh_cookie['ipb_member_id']}, 表站请求出错，检查网络"})
                    else:
                        continue
            else:
                num -=1
                if num <= 0:
                    logging.error(f"cookie_id为：{eh_cookie['ipb_member_id']}, 里站请求出错，检查网络")
                    return jsonify({"error": f"cookie_id为：{eh_cookie['ipb_member_id']}, 里站请求出错，检查网络"})
                else:
                    continue
    else:
        logging.error("密钥错误！")
        return jsonify({"error": "密钥错误"})

@app.route('/api/eh-status', methods=['POST'])
def eh_hh_status():
    data = request.get_json()
    if data["key"] == config['key']:
        eh_cookie = random.choice(config['eh_cookies'])
        hh = requests.get(url="https://e-hentai.org/hentaiathome.php", cookies=eh_cookie, proxies=proxies)
        if hh.status_code == 200:
            b = []
            soup = BeautifulSoup(hh.text, 'html.parser')
            table = soup.find("table", id="hct")
            if not table:
                return jsonify({"code": 500, "message": "你没有H@H"})
            trs = table.find_all("tr")
            for tr in trs:
                tds = tr.find_all("td")
                if not tds:
                    continue
                else:
                    b.append(f"名: {tds[0].text.replace("\n", "").replace(" ", "")}: \n状态: {"🟢" if tds[2].text == "Online" else "🔴"}, 最后: {tds[4].text}, 信任: {tds[10].text}, 质量: {tds[11].text}, 速度: {tds[12].text}, 获取量: {tds[13].text}, 地区: {tds[14].text}\n")
            return jsonify({"code": 200, "message": b})
        else:
            return jsonify({"code": 404, "message": "请求页面失败"})
    else:
        return jsonify({"code": 403, "message": "密钥错误"})
    
@app.route('/api/h@h', methods=['POST'])
def eh_status():
    data = request.get_json()
    if data["key"] == config['key']:
        eh_cookie = random.choice(config['eh_cookies'])
        hh = requests.get(url="https://e-hentai.org/hentaiathome.php", cookies=eh_cookie, proxies=proxies)
        if hh.status_code == 200:
            soup = BeautifulSoup(hh.text, 'html.parser')
            table = soup.find("table", id="hct")
            if not table:
                return jsonify({"code": 500, "message": "你没有H@H"})
            trs = table.find_all("tr")
            for tr in trs:
                tds = tr.find_all("td")
                if not tds:
                    continue
                else:
                    if not tds[2].text == "Online":
                        return jsonify({"code": 200, "message": "‼️‼️‼️‼️‼️‼️‼️\n有H@H掉线啦‼️‼️"})
        else:
            return jsonify({"code": 404, "message": "请求页面失败"})
    else:
        return jsonify({"code": 403, "message": "密钥错误"})
    
@app.route('/api/eh-info', methods=['POST'])
def eh_info():
    data = request.get_json()
    if data["key"] == config['key']:
        eh_cookie = random.choice(config['eh_cookies'])
        hh = requests.get(url="https://e-hentai.org/home.php", cookies=eh_cookie, proxies=proxies)
        if hh.status_code == 200:
            soup = BeautifulSoup(hh.text, 'html.parser')
            homeboxs = soup.find_all("div", class_="homebox")
            GPs = homeboxs[0].find_all("strong")
            tors = homeboxs[1].find_all("td", class_="c1")
            GP_Gained = homeboxs[2].find_all("td", style="font-weight:bold; text-align:right")
            if not homeboxs[3].find("td", style="vertical-align:top; padding-top:4px"):
                Toplists = ""
            else:
                Toplists = homeboxs[3].find_all("td", style="text-align:right")
                Toplist = homeboxs[3].find_all("a")
            power = homeboxs[4].find("div", style="margin-top:5px; font-size:14pt; font-weight:bold")
            info = {
                "gp": {
                    "gp": GPs[1].text,
                    "use_gp": GPs[0].text,
                    "need_gp": GPs[2].text
                },
                "tor": {
                    "upload": tors[0].text,
                    "download": tors[1].text,
                    "ratio": tors[2].text,
                    "torrent_completes": tors[3].text,
                    "gallery_completes": tors[4].text,
                    "seedmins": tors[5].text
                },
                "GP_Gained": {
                    "gallery_visits": GP_Gained[0].text,
                    "torrent_completions": GP_Gained[1].text,
                    "archive_downloads": GP_Gained[2].text,
                    "Hentai@Home": GP_Gained[3].text
                },
                "Toplists": {name.text: st.text for name, st in zip(Toplist, Toplists)} if Toplists else {},
                "power": power.text
            }
            return jsonify({"code": 200, "json": info})
        else:
            return jsonify({"code": 404, "message": "请求页面失败"})
    else:
        return jsonify({"code": 403, "message": "密钥错误"})

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=config['port'])