import feedparser
import os, re, io
from PIL import Image # 需要安装 Pillow 库
import requests
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



def run():
    feed = fetch_reddit()
    # 每天抓取当日最热的一篇讨论
    if feed.entries:
        entry = feed.entries[0]
        print(f"Processing: {entry.title}")

        folder_name = f"game-guide-{(datetime.now()-timedelta(days=1)).strftime('%Y%m%d%H%M')}"
        post_dir = f"content/post/{folder_name}"
        os.makedirs(post_dir, exist_ok=True)

        summary = entry.summary
        img_match = re.search(r'src="([^"]+\.(?:jpg|png|webp|jpeg)[^"]*)"', summary)
        if img_match:
            url = img_match.group(1)
            name = url.split('?')[0].split('/')[-1]
            download_high_res_image(name, post_dir)
        # 让 AI 扩写
        article_md = call_ai_to_openai(entry.summary)


        full_content = f"""---
title: "{entry.title}"
date: {(datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')}
categories: ["Genshin Impact", "Game Guide"]
tags: ["Gaming", "News"]
image: "cover.webp"
---

{article_md}

---
*Source: Compiled from Reddit r/Genshin_Impact discussion.*
"""
        with open(f"{post_dir}/index.md", "w", encoding="utf-8") as f:
            f.write(full_content)


if __name__ == "__main__":
    run()