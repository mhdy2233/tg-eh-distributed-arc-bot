import requests, logging
from bs4 import BeautifulSoup
from flask import request, Flask, jsonify, redirect
from flask_cors import CORS

key = "1234"
port = 11451
eh_cookie = {"ipb_member_id": "", "ipb_pass_hash": "", "igneous": ""}
proxies = {
    # 不用的时候就#
    # "http": "http://127.0.0.1:8080",
    # "https": "http://127.0.0.1:8080"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def detection(gid, token, clarity, use_gp):
    # 检测是否有下载链接
    arc_url = "https://exhentai.org/archiver.php" + f"?gid={gid}" + f"&token={token}"
    response = requests.get(arc_url, cookies=eh_cookie, proxies=proxies)
    soup = BeautifulSoup(response.text, "html.parser")
    free = soup.find("strong")
    if not free.text == "Free!":
        url = "https://e-hentai.org/archiver.php?gid=3285545&token=7745b19f1e"
        response = requests.get(url, cookies=eh_cookie, proxies=proxies)
        soup = BeautifulSoup(response.text, "html.parser")
        for x in soup.find_all("p"):
            if "GP" in x.text and "Credits" in x.text:
                m_list = (
                    x.text.replace("[", "")
                    .replace("]", "")
                    .replace("?", "")
                    .replace(",", "")
                    .split()
                )
                if m_list[0] - use_gp < 0:
                    return False, f"GP不足，GP还剩余{[m_list[0]]}，C还剩余{[m_list[2]]}"
    if soup.find("a", onclick="return cancel_sessions()"):
        if refresh_url(gid=gid, token=token):
            logging.info("销毁成功")
        else:
            return False, "链接销毁失败"

    link = download_url(gid, token, clarity)
    return link


def download_url(gid, token, clarity):
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
        soup = BeautifulSoup(response.text, "html.parser")
        url = soup.find("a")["href"]
        link_original = url + "?start=1"
        return True, link_original
    else:
        code = response.status_code
        logging.error(f"请求原始图像失败，错误代码为：{code}")
        return False, code


def refresh_url(gid, token):
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


@app.route("/api/url", methods=["POST", "GET"])
def process_data():
    if request.method == "POST":
        try:
            # 获取 JSON 数据
            data = request.get_json()
            if not data:
                return jsonify({"error": "请求体不能为空"})

            if data["key"] == key:
                # 处理数据（获取gid和token然后获取下载链接）
                gid = data["gid"]
                token = data["token"]
                clarity = data["arc"]
                use_gp = data["use_gp"]
                link = detection(gid, token, clarity, use_gp)
                logging.info(link)
                if link[0]:
                    # 构造返回结果(返回画廊原图下载链接)
                    response = {"link": link[1]}
                    return jsonify(response)
                else:
                    return jsonify({"error": str(link[1])})
            else:
                return jsonify({"error": "密钥错误！"})
        except Exception as e:
            return jsonify({"error": str(e)})
    if request.method == "GET":
        # 处理 GET 请求，进行 302 重定向
        logging.info("处理 GET 请求 - 重定向到另一个路径")
        return redirect("https://www.mohuangdiyu.com")  # 可以根据需求更改重定向的 URL


@app.route("/api/status", methods=["POST"])
def status():
    data = request.get_json()
    if data["key"] == key:
        ceshi = requests.get("https://exhentai.org", cookies=eh_cookie, proxies=proxies)
        if ceshi.status_code == 200:
            cc = requests.get(
                "https://e-hentai.org/archiver.php?gid=3285402&token=9cf3194f42",
                cookies=eh_cookie,
                proxies=proxies,
            )
            if cc.status_code == 200:
                soup = BeautifulSoup(cc.text, "html.parser")
                for x in soup.find_all("p"):
                    if "GP" in x.text and "Credits" in x.text:
                        m_list = (
                            x.text.replace("[", "")
                            .replace("]", "")
                            .replace("?", "")
                            .split()
                        )
                        if int(m_list[0].replace(",", "")) > 50000:
                            return jsonify({"status": 200})
                        else:
                            logging.error("GP小于50000无法加入")
                            return jsonify({"error": "GP小于50000"})
        else:
            logging.error("里站无内容，请检查cookie是否正确")
            return jsonify({"error": "里站无内容，请检查cookie是否正确"})
    else:
        logging.error("密钥错误！")
        return jsonify({"error": "密钥错误"})


if __name__ == "__main__":
    app.run(debug=True, port=port)
