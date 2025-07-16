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

    # 统计变量
    total_accounts = len(accounts)
    success_count = 0
    success_accounts = []
    failed_accounts = []

    for account in accounts:
        username = account['username']
        password = account['password']
        panel = account['panel']

        serviceName = 'CT8' if 'ct8' in panel else 'Serv00'
        is_logged_in = await login(username, password, panel)

        if is_logged_in:
            success_count += 1
            success_accounts.append({'username': username, 'service': serviceName})
        else:
            failed_accounts.append({'username': username, 'service': serviceName})

        delay = random.randint(1000, 8000)
        await delay_time(delay)
    
    # 构建报告消息
    beijing_time = format_to_iso(datetime.utcnow() + timedelta(hours=8))
    fail_count = total_accounts - success_count
    
    message = f"📄 *Serv00 & CT8 保号脚本运行报告*\n"
    message += f"⏰ *北京时间*: {beijing_time}\n"
    message += f"📊 *共计*: {total_accounts} | ✅ *成功*: {success_count} | ❌ *失败*: {fail_count}\n"
    message += "━━━━━━━━━━━━━━━━━━\n"
    
    # 添加成功账号详情
    if success_accounts:
        for success in success_accounts:
            message += f"✅ *账号*: `{success['username']}` 📍{success['service']}\n"
    
    # 添加失败账号详情
    if failed_accounts:
        for failed in failed_accounts:
            message += f"❌ *账号*: `{failed['username']}` 📍{failed['service']}\n"
    
    await send_telegram_message(message)
    print('所有账号登录完成！')
    await shutdown_browser()

async def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
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
