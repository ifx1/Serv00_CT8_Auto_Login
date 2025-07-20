import json
import asyncio
from datetime import datetime, timezone
import pytz
import aiofiles
import random
import requests
import os
from pyppeteer import launch

# 从环境变量中获取 Telegram Bot Token 和 Chat ID
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def format_to_iso(date):
    return date.strftime('%Y-%m-%d %H:%M:%S')

async def delay_time(ms):
    await asyncio.sleep(ms / 1000)

async def login(username, password, panel):
    page = None
    browser = None
    serviceName = 'CT8' if 'ct8' in panel else 'Serv00'
    try:
        browser = await launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'], autoClose=False)
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
        if browser:
            await browser.close()
            if browser.process is not None:
                browser.process.terminate()

async def send_telegram_message(message, success_count, failed_count, account_count):
    now_utc = datetime.now(timezone.utc)
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now_beijing = now_utc.astimezone(beijing_tz)
    formatted_message = f"""
✉️ *Serv00 & CT8 保号脚本运行报告*
🕘 北京时间: `{format_to_iso(now_beijing)}`
📊 共计:{account_count} | ✅ 成功:{success_count} | ❌ 失败:{failed_count}
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

async def main():
    message = ""
    success_count = 0
    failed_count = 0

    try:
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        accounts = json.loads(accounts_json)
    except Exception as e:
        print(f'读取 accounts.json 文件时出错: {e}')
        return

    for account in accounts:
        username = account['username']
        password = account['password']
        panel = account['panel']

        serviceName = 'CT8' if 'ct8' in panel else 'Serv00'
        is_logged_in = await login(username, password, panel)

        if is_logged_in:
            success_count += 1
        else:
            failed_count += 1

        now_utc = datetime.now(timezone.utc)
        beijing_tz = pytz.timezone('Asia/Shanghai')
        now_beijing = now_utc.astimezone(beijing_tz)
        status_icon = "✅" if is_logged_in else "❌"
        status_text = "登录成功" if is_logged_in else "登录失败"
        
        message += (
            f"{status_icon} 账号: `{username}`  【{serviceName}】\n"
        )

        delay = random.randint(1000, 8000)
        await delay_time(delay)

    # 发送 Telegram 消息
    await send_telegram_message(message, success_count, failed_count, len(accounts))

if __name__ == '__main__':
    asyncio.run(main())
