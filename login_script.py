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
    page = None
    serviceName = 'CT8' if 'ct8' in panel else 'Serv00'
    
    try:
        if not browser:
            browser = await launch(
                headless=True, 
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )

        page = await browser.newPage()
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        url = f'https://{panel}/login/?next=/'
        await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': 30000})

        # 输入账号密码
        await page.type('#id_username', username, {'delay': 50})
        await page.type('#id_password', password, {'delay': 50})

        # 🔥 终极点击逻辑
        login_selectors = ['button[type="submit"]', '.login-form__button button']
        login_button = None
        for selector in login_selectors:
            login_button = await page.querySelector(selector)
            if login_button:
                print(f'✅ {serviceName} 找到登录按钮: {selector}')
                break
        
        if not login_button:
            raise Exception('未找到登录按钮')

        # 🔥 单次点击 + 智能等待
        print(f'✅ {serviceName} 准备点击登录按钮...')
        await page.evaluate('''(button) => {
            button.scrollIntoView({ behavior: "smooth", block: "center" });
            button.style.display = "block";
            button.style.visibility = "visible";
            button.style.opacity = "1";
            const overlays = document.querySelectorAll('.select2-container, [data-form-loader]');
            overlays.forEach(el => el.style.display = "none");
        }''', login_button)

        await page.evaluate('''(button) => button.click()''', login_button)
        print(f'✅ {serviceName} JS点击已发送')

        # 立即等待导航
        try:
            await page.waitForNavigation({'timeout': 15000, 'waitUntil': 'domcontentloaded'})
            print(f'✅ {serviceName} 导航完成')
        except:
            print(f'⚠️ {serviceName} 导航超时，使用备用等待...')
            await page.waitForTimeout(3000)

        await page.waitForTimeout(1000)

        # 验证登录
        is_logged_in = await page.evaluate('''() => {
            const logoutLink = document.querySelector('a[href="/logout/"]');
            if (logoutLink) return true;
            const userMenu = document.querySelector('[href*="/profile/"], .user-menu, .dropdown-user');
            if (userMenu) return true;
            return window.location.pathname !== '/login/';
        }''')

        if is_logged_in:
            print(f'✅ {serviceName} 账号 {username} 登录成功')
            return True
        else:
            print(f'❌ {serviceName} 账号 {username} 登录失败')
            await page.screenshot({'path': f'{username}_fail.png'})
            return False

    except Exception as e:
        print(f'❌ {serviceName}账号 {username} 登录错误: {e}')
        if page:
            await page.screenshot({'path': f'{username}_error.png'})
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
            # 仅在登录失败时添加到消息
            now_beijing = format_to_iso(datetime.utcnow() + timedelta(hours=8))
            message += (
                f"❌ 账号: {username}      【{serviceName}】\n"
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
{message if message else "🎉 所有账号登录成功，无失败账号！"}
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
