import time
import textwrap
import feedparser
import os, re, io, json
from PIL import Image, ImageDraw, ImageFont
import requests
import shutil
from datetime import datetime, timedelta
from openai import OpenAI
# from config import AICONFIG

# config = AICONFIG()
API_KEY = os.getenv("APIKEY", "")
BASE_URL = os.getenv("BASEURL", "")
MODEL = os.getenv("MODEL", "")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
# client = OpenAI(api_key=config.APIKEY, base_url=config.BASEURL)


# 抓取原神官方公告或 Reddit 热门的 RSS
REDDIT_RSS = "https://www.reddit.com/r/Genshin_Impact/top/.rss?t=day"
HISTORY_FILE = "scripts/history.json"


def load_history():
    """读取已抓取的 URL 列表"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []


def call_ai_to_write(raw_content):
    """调用 DeepSeek 把它转化成专业攻略文章"""
    url = "https://api.deepseek.com/chat/completions"  # 确认接口地址
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    prompt = f"""
    You are a pro game journalist. Based on this Reddit discussion/news, write a detailed English guide for a gaming blog.
    Include a catchy SEO title, a summary, and three key points. Format as Markdown.

    Content Source: {raw_content[:2000]} 
    """

    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}]
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()['choices'][0]['message']['content']


def call_ai_to_openai(raw_content):
    try:
        prompt = f"""
            You are a pro game journalist. Based on this Reddit discussion/news, write a detailed English guide for a gaming blog.
            Include a catchy SEO title, a summary, and three key points. Format as Markdown.

            Content Source: {raw_content} 
            """
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content
        return result
    except Exception as e:
        return

def fetch_reddit():
    # 模拟浏览器 Header，防止被 Reddit 拒收
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }

    try:
        # 1. 先用 requests 获取内容
        # 如果你电脑开了梯子，建议加上 proxies 参数，例如：
        # proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        # response = requests.get(REDDIT_RSS, headers=headers, timeout=30, proxies=proxies)

        response = requests.get(REDDIT_RSS, headers=headers, timeout=30)
        response.raise_for_status()  # 检查是否请求成功

        # 2. 将获取到的文本交给 feedparser 解析
        feed = feedparser.parse(response.content)
        return feed

    except Exception as e:
        print(f"抓取失败: {e}")
        return None


def create_pro_cover(text, save_path):
    # 1. 打开一张你预先做好的“漂亮背景” (比如 1200x630)
    # 路径可以是在你的仓库里的 static 资源
    img = Image.new('RGB', (1200, 630), color=(0, 102, 204))

    draw = ImageDraw.Draw(img)

    # 2. 获取字体 (使用固定字号即可，无需复杂计算)
    font = ImageFont.truetype("./assets/fonts/bold.ttf", 60)

    # 3. 粗暴的自动换行 (前 30 个字，两行显示)
    # 这里不需要精确算法，利用 textwrap 简单切分即可

    lines = textwrap.wrap(text, width=20)  # 每行20字符

    # 4. 固定位置写入（比如从坐标 100, 200 开始写）
    y_text = 200
    for line in lines[:2]:  # 只显示前两行，防止溢出
        draw.text((100, y_text), line, font=font, fill=(255, 255, 255))
        y_text += 80

    img.save(f'{save_path}/cover.webp', "WEBP", quality=80)

def download_high_res_image(name, post_dir):
    """
    通过请求头验证，强制下载真实的二进制图片
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        # stream=True 允许我们先读头不读内容
        # allow_redirects=True 会自动帮我们跳过所有的 301/302 页面，找到最后的原图
        response = requests.get(f"https://i.redd.it/{name}", headers=headers, timeout=20, stream=True, allow_redirects=True)

        # 检查返回的到底是不是图片
        content_type = response.headers.get('Content-Type', '')
        if 'image' not in content_type.lower():
            return False

        # 检查是否成功并保存二进制文件
        if response.status_code == 200:

            # 使用 Pillow 打开二进制图片数据
            img = Image.open(io.BytesIO(response.content))

            # 1. 如果图片是 RGBA（如带透明的PNG），转化为 RGB
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # 2. 缩小尺寸（比如宽度最大 1200px，高度按比例缩放）
            max_width = 640
            if img.width > max_width:
                w_percent = (max_width / float(img.width))
                h_size = int((float(img.height) * float(w_percent)))
                img = img.resize((max_width, h_size), Image.LANCZOS)

            # 3. 保存为 WebP 格式（极致压缩），质量设为 75-80
            # 注意：保存后缀改为 .webp
            save_path = f'{post_dir}/cover.webp'
            img.save(save_path, "WEBP", quality=80)
            # with open(f'{post_dir}/cover.png', 'wb') as f:
            #     for chunk in response.iter_content(chunk_size=8192):
            #         f.write(chunk)
            return True

    except Exception as e:
        print(f"下载过程中出错: {e}")
    return False

def save_history(history):
    """保存更新后的列表"""
    # 只保留最近 100 条记录，防止文件无限增大
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-100:], f, indent=2)


def run():
    history = load_history()
    feed = fetch_reddit()
    # 每天抓取当日最热的一篇讨论
    new_count = 0
    # 每次只抓取最近的 5 条进行判断
    for entry in feed.entries[:5]:
        folder_name = f"game-guide-{int(time.time())}"
        post_dir = f"content/post/{folder_name}"
        try:
            post_url = entry.link

            # --- 核心查重逻辑 ---
            if post_url in history:
                print(f"跳过已存在的文章: {entry.title}")
                continue

            print(f"Processing: {entry.title}")


            os.makedirs(post_dir, exist_ok=True)

            summary = entry.summary
            img_match = re.search(r'src="([^"]+\.(?:jpg|png|webp|jpeg)[^"]*)"', summary)

            if img_match:
                url = img_match.group(1)
                name = url.split('?')[0].split('/')[-1]
                res = download_high_res_image(name, post_dir)
                if not res:
                    create_pro_cover(entry.title, post_dir)

            else:
                create_pro_cover(entry.title, post_dir)
            # 让 AI 扩写
            article_md = call_ai_to_openai(entry.summary)


            full_content = f"""---
    title: "{entry.title}"
    date: {(datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')}
    categories: ["Genshin Impact", "Game Guide"]
    tags: ["Gaming", "News"]
    image: "cover.png"
    ---
    
    {article_md}
    
    ---
    *Source: Compiled from Reddit r/Genshin_Impact discussion.*
    """
            with open(f"{post_dir}/index.md", "w", encoding="utf-8") as f:
                f.write(full_content)

            history.append(post_url)
            new_count += 1

            # 如果你只想每天更 1 篇，成功后直接 break
            if new_count >= 3:
                break
        except Exception as e:
            if os.path.exists(post_dir):
                shutil.rmtree(post_dir)  # 彻底删除整个文件夹及其内容

    if new_count > 0:
        save_history(history)


if __name__ == "__main__":
    run()