import feedparser
import os, json
import requests
from datetime import datetime
from openai import OpenAI

API_KEY = os.getenv("APIKEY", "")
BASE_URL = os.getenv("BASEURL", "")
MODEL = os.getenv("MODEL", "")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


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

def run():
    feed = fetch_reddit()
    # 每天抓取当日最热的一篇讨论
    if feed.entries:
        entry = feed.entries[0]
        print(f"Processing: {entry.title}")

        # 让 AI 扩写
        article_md = call_ai_to_openai(entry.summary)

        # 保存为 Hugo Markdown
        # 用日期做文件名避免重复
        file_name = f"post/game-guide-{datetime.now().strftime('%Y%m%d')}/index.md"
        os.makedirs(os.path.dirname(f"content/{file_name}"), exist_ok=True)

        full_content = f"""---
title: "{entry.title}"
date: {datetime.now().strftime('%Y-%m-%d')}
categories: ["Genshin Impact", "Game Guide"]
tags: ["Gaming", "News"]
image: "cover.jpg"
---

{article_md}

---
*Source: Compiled from Reddit r/Genshin_Impact discussion.*
"""
        with open(f"content/{file_name}", "w", encoding="utf-8") as f:
            f.write(full_content)


if __name__ == "__main__":
    run()