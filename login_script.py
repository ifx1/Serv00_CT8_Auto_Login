import json
import asyncio
from pyppeteer import launch
from datetime import datetime, timedelta
import aiofiles
import random
import requests
import os

# 从环境变量中获取 Telegram Bot Token 和 Chat ID
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def format_to_iso(date):
    return date.strftime('%Y-%m-%d %H:%M:%S')

async def delay_time(ms):
    await asyncio.sleep(ms / 1000)

# 全局浏览器实例
browser = None

# telegram消息
message = ""

async def login(username, password, panel):
    global browser

    page = None  # 确保 page 在任何情况下都被定义
    serviceName = 'CT8' if 'ct8' in panel else 'Serv00'  # 修改大小写
    try:
        if not browser:
            browser = await launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])

        page = await browser.newPage()
        url = f'https://{panel}/login/?next=/'
        await page.goto(url)

        username_input = await page.querySelector('#id_username')
        if username_input:
            await page.evaluate('''(input) => input.value = ""''', username_input)

        await page.type('#id_username', username)
        await page.type('#id_password', password)

        login_button = await page.querySelector('#submit')
        if login_button:
            await login_button.click()
        else:
            raise Exception('无法找到登录按钮')

        await page.waitForNavigation()

        is_logged_in = await page.evaluate('''() => {
            const logoutButton = document.querySelector('a[href="/logout/"]');
            return logoutButton !== null;
        }''')

        return is_logged_in

    except Exception as e:
        print(f'{serviceName}账号 {username} 登录时出现错误: {e}')
        return False

    finally:
        if page:
            await page.close()

async def shutdown_browser():
    global browser
    if browser:
        await browser.close()
        browser = None

async def main():
    global message

    try:
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        accounts = json.loads(accounts_json)
    except Exception as e:
        print(f'读取 accounts.json 文件时出错: {e}')
        return

    # 初始化计数器
    total_count = len(accounts)
    success_count = 0
    failed_count = 0

    for account in accounts:
        username = account['username']
        password = account['password']
        panel = account['panel']

        serviceName = 'CT8' if 'ct8' in panel else 'Serv00'  # 修改大小写
        is_logged_in = await login(username, password, panel)

        # 更新计数器
        if is_logged_in:
            success_count += 1
        else:
            failed_count += 1

        now_beijing = format_to_iso(datetime.utcnow() + timedelta(hours=8))
        status_icon = "✅" if is_logged_in else "❌"
        status_text = "登录成功" if is_logged_in else "登录失败"
        
        message += (
            f"{status_icon} *账号*: {username}      【{serviceName}】\n"
        )

        delay = random.randint(1000, 8000)
        await delay_time(delay)
    
    # 添加报告尾部
    await send_telegram_message(message, total_count, success_count, failed_count)
    print('所有账号登录完成！')
    await shutdown_browser()

async def send_telegram_message(message, total_count, success_count, failed_count):
    formatted_message = f"""
📩 *Serv00 & CT8 保号脚本运行报告*
⏰ 北京时间: `{format_to_iso(datetime.utcnow() + timedelta(hours=8))}`
📊 共计:{total_count} | ✅ 成功:{success_count} | ❌ 失败:{failed_count}
━━━━━━━━━━━━━━━━━━
{message}
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': formatted_message,
        'parse_mode': 'Markdown',
    }
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"发送消息到Telegram失败: {response.text}")
    except Exception as e:
        print(f"发送消息到Telegram时出错: {e}")

if __name__ == '__main__':
    asyncio.run(main())
