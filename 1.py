import requests
from bs4 import BeautifulSoup

key = "mhdy"
port = 11451
eh_cookie = {
    "ipb_member_id": "7405455",
    "ipb_pass_hash": "8626a2f1efa51a6b0fd464145e32cea7",
    "igneous": "kug8yttlibrjsy1g1"
}

z = requests.get("https://exhentai.org/archiver.php?gid=3291709&token=27ad74bd58", cookies=eh_cookie)

soup = BeautifulSoup(z.text, 'html.parser')
print(soup.find('a', onclick="return cancel_sessions()"))