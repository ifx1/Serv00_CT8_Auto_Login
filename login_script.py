import json
import asyncio
from pyppeteer import launch
from datetime import datetime, timezone, timedelta
import aiofiles
import random
import requests
import os
import gc  # 垃圾回收

# 从环境变量中获取 Telegram Bot Token 和 Chat ID
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def format_to_iso(date):
    # ✅ Python 3.13兼容版
    return date.strftime('%Y-%m-%d %H:%M:%S')

async def delay_time(ms):
    await asyncio.sleep(ms / 1000)

# 全局浏览器实例
browser = None
message = ""

async def login(username, password, panel):
    global browser
    page = None
    serviceName = 'CT8' if 'ct8' in panel else 'Serv00'
    
    try:
        # 1. 浏览器初始化（单例 + 内存优化）
        if not browser:
            browser = await launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',  # ✅ GitHub Actions内存优化
                    '--disable-gpu',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process'  # ✅ 单进程模式
                ],
                defaultViewport=None  # 禁用视口限制
            )
            print(f'✅ {serviceName} 浏览器启动完成')

        page = await browser.newPage()
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        # 2. 访问登录页
        url = f'https://{panel}/login/?next=/'
        await page.goto(url, {'waitUntil': 'domcontentloaded', 'timeout': 30000})
        print(f'✅ {serviceName} 页面加载完成')

        # 3. 输入账号密码（简化）
        await page.type('#id_username', username, {'delay': 30})
        await page.type('#id_password', password, {'delay': 30})
        print(f'✅ {serviceName} 输入完成: {username}')

        # 4. 【终极稳定】直接表单提交（零DOM操作）
        await page.evaluate('''() => {
            const form = document.querySelector('form[action="/login/"]');
            if (form) form.submit();
        }''')
        print(f'✅ {serviceName} 表单提交成功')

        # 5. 【简化等待】只用URL变化检测
        try:
            await page.waitForFunction(
                '() => window.location.pathname !== "/login/"',
                {'timeout': 30000}
            )
            print(f'✅ {serviceName} 跳转检测成功')
        except:
            print(f'⚠️ {serviceName} 跳转超时，检查URL...')
            await asyncio.sleep(5)

        # 6. 【安全验证】检查关键元素
        current_url = page.url
        logout_exists = await page.evaluate('''() => !!document.querySelector('a[href="/logout/"]')''')
        
        is_logged_in = logout_exists or '/login/' not in current_url
        
        print(f'📍 {serviceName} 最终URL: {current_url}')
        print(f'🔑 {serviceName} 登出链接: {"存在" if logout_exists else "不存在"}')
        
        return is_logged_in

    except Exception as e:
        print(f'❌ {serviceName}账号 {username} 错误: {e}')
        return False
        
    finally:
        # ✅ 强制清理（防止Target closed）
        if page:
            try:
                await page.close()
            except:
                pass
        gc.collect()  # 强制垃圾回收

async def shutdown_browser():
    global browser
    try:
        if browser:
            await browser.close()
            browser = None
    except:
        pass
    gc.collect()

async def main():
    global message

    # ✅ Python 3.13时间修复
    now_beijing = format_to_iso(datetime.now(timezone.utc) + timedelta(hours=8))
    
    try:
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        accounts = json.loads(accounts_json)
    except Exception as e:
        print(f'读取 accounts.json 出错: {e}')
        return

    total_count = len(accounts)
    success_count = 0
    failed_count = 0

    for i, account in enumerate(accounts):
        username = account['username']
        password = account['password']
        panel = account['panel']
        serviceName = 'CT8' if 'ct8' in panel else 'Serv00'  # ✅ 移到这里

        print(f'\n🔄 [{i+1}/{total_count}] 处理 {username}')
        is_logged_in = await login(username, password, panel)

        if is_logged_in:
            success_count += 1
            print(f'✅ {username} 登录成功')
        else:
            failed_count += 1
            message += f"❌ 账号: {username}      【{serviceName}】\n"  # ✅ 现在可用

        # 随机延时
        if i < total_count - 1:
            delay = random.randint(2000, 5000)
            print(f'⏳ 等待 {delay/1000:.1f}秒...')
            await delay_time(delay)

    # 发送报告
    await send_telegram_message(message, total_count, success_count, failed_count)
    print('\n🎉 所有账号处理完成！')
    await shutdown_browser()

async def send_telegram_message(message, total_count, success_count, failed_count):
    now_beijing = format_to_iso(datetime.now(timezone.utc) + timedelta(hours=8))
    formatted_message = f"""
📩 *Serv00 & CT8 保号脚本运行报告*
⏰ 北京时间: `{now_beijing}`
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
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print('✅ Telegram报告发送成功')
        else:
            print(f'❌ Telegram发送失败: {response.text}')
    except Exception as e:
        print(f'❌ Telegram错误: {e}')

if __name__ == '__main__':
    # ✅ 异常捕获主程序
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n⏹️ 用户中断')
    except Exception as e:
        print(f'\n💥 主程序错误: {e}')
    finally:
        asyncio.run(shutdown_browser())
