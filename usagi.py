import discord
from discord.ext import commands, tasks
import datetime
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import re
import uuid
from dotenv import load_dotenv
import os
import json
from flask import Flask
from threading import Thread

# 設置基本配置
load_dotenv()
TOKEN = os.getenv('TOKEN')
reminder_tasks: Dict[str, dict] = {}  # 使用 UUID 作為 key 來存儲提醒
def keep_alive():
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "Bot is running!"
    
    def run():
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
    
    server = Thread(target=run)
    server.start()

# 在 bot.run(TOKEN) 之前調用 keep_alive()
# 在 ReminderManager 類中添加持久化方法
def save_reminders(self):
    with open('reminders.json', 'w') as f:
        json.dump(reminder_tasks, f)

def load_reminders(self):
    try:
        with open('reminders.json', 'r') as f:
            loaded_tasks = json.load(f)
            reminder_tasks.update(loaded_tasks)
    except FileNotFoundError:
        pass

# 在 setup_hook 或 __init__ 中調用 load_reminders

class ReminderBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.reminder_manager = None
    
    async def setup_hook(self) -> None:
        self.reminder_manager = ReminderManager(self)

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        print('Reminder system started')
        print('------')

# 創建 bot 實例
bot = ReminderBot()
# 輔助函數
def parse_date(date_str: str) -> Optional[datetime]:
    """解析日期字符串，支持 MM/DD 格式"""
    try:
        if date_str.lower() == "permanent":
            return None
        month, day = map(int, date_str.split("/"))
        current_year = datetime.now().year
        return datetime(current_year, month, day)
    except:
        return None

async def check_date_range(start_date: Optional[datetime], end_date: Optional[datetime]) -> bool:
    """檢查當前日期是否在指定範圍內"""
    if start_date is None and end_date is None:  # permanent
        return True
    
    current_date = datetime.now()
    if start_date and current_date.date() < start_date.date():
        return False
    if end_date and current_date.date() > end_date.date():
        return False
    return True

async def get_channel(ctx, channel_input: str) -> Optional[discord.TextChannel]:
    """解析頻道輸入"""
    guild = ctx.guild
    channel_input = channel_input.strip('<#>')
    
    try:
        if channel_input.isdigit():
            channel = guild.get_channel(int(channel_input))
            if channel:
                return channel
    except:
        pass
    
    channel = discord.utils.get(guild.text_channels, name=channel_input.lower())
    return channel

def get_user_reminders(user_id: int) -> List[dict]:
    """獲取用戶的所有提醒"""
    return [reminder for reminder in reminder_tasks.values() if reminder["user_id"] == user_id]

class ReminderManager:
    def __init__(self, bot):
        self.bot = bot
        self.last_check = {}  # 用於追踪上次發送的時間
        load_reminders(self)
        self.check_reminders.start()

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_minute = now.strftime("%H:%M")
        current_date = now.date()
        
        for reminder_id, reminder in list(reminder_tasks.items()):
            try:
                reminder_time = reminder["time"]
                
                # 檢查是否在當前分鐘或前30秒的分鐘內
                if reminder_time in [current_time, (now - timedelta(seconds=30)).strftime("%H:%M")]:
                    # 檢查今天是否已經發送過
                    last_sent = self.last_check.get(reminder_id)
                    if last_sent and last_sent.date() == current_date:
                        continue
                        
                    start_date = parse_date(reminder["start_date"])
                    end_date = parse_date(reminder["end_date"])
                    
                    if await check_date_range(start_date, end_date):
                        # 確保提醒時間在最後發送時間的至少23小時之後
                        if last_sent and (now - last_sent).total_seconds() < 23 * 3600:
                            continue
                            
                        channel = self.bot.get_channel(reminder["channel_id"])
                        if channel:
                            # 添加更詳細的提醒資訊
                            embed = discord.Embed(
                                title=reminder["title"],
                                description=reminder["content"],
                                color=discord.Color.green(),
                                timestamp=now
                            )
                            # embed.add_field(
                            #     name="預定時間", 
                            #     value=reminder_time,
                            #     inline=True
                            # )
                            # embed.add_field(
                            #     name="實際發送時間",
                            #     value=now.strftime("%H:%M:%S"),
                            #     inline=True
                            # )
                            # embed.set_footer(text=f"提醒 ID: {reminder_id}")
                            
                            await channel.send(embed=embed)
                            
                            # 更新最後發送時間
                            self.last_check[reminder_id] = now
                            
                            # 記錄日誌
                            print(f"Reminder {reminder_id} sent at {now.strftime('%H:%M:%S')}")
                    
                    elif end_date and now.date() > end_date.date():
                        del reminder_tasks[reminder_id]
                        if reminder_id in self.last_check:
                            del self.last_check[reminder_id]
                            
            except Exception as e:
                print(f"Error processing reminder {reminder_id}: {e}")
                continue

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()
        print("Reminder check system started!")

    def cog_unload(self):
        self.check_reminders.cancel()
        self.last_check.clear()

class ReminderView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="查看指令說明", style=discord.ButtonStyle.primary)
    async def show_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="提醒機器人使用說明", color=discord.Color.blue())
        embed.add_field(
            name="設定提醒",
            value=(
                "```!set_reminder <頻道> <時間> <標題> <開始日期> <結束日期> <內容>\n"
                "\n指定頻道的方式：\n"
                "1. 使用頻道標記：#general\n"
                "2. 使用頻道ID：1234567890\n"
                "3. 使用頻道名稱：general\n"
                "\n例如：\n"
                "1. 固定時間範圍：\n"
                "!set_reminder #公告 09:00 早安提醒 11/1 11/20 打卡提醒\n"
                "2. 永久提醒：\n"
                "!set_reminder #公告 09:00 打卡提醒 permanent permanent 記得打卡```"
            ),
            inline=False
        )
        embed.add_field(
            name="其他指令",
            value=(
                "```\n"
                "查看所有提醒：!list_reminders\n"
                "停止特定提醒：!stop_reminder <提醒ID>\n"
                "停止所有提醒：!stop_all_reminders\n"
                "顯示此幫助：!helpusagi\n"
                "```"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.command(name="helpusagi")
async def help_command(ctx):
    """顯示幫助訊息"""
    view = ReminderView()
    embed = discord.Embed(title="提醒機器人使用說明", color=discord.Color.blue())
    embed.add_field(
        name="設定提醒",
        value=(
            "```!set_reminder <頻道> <時間> <標題> <開始日期> <結束日期> <內容>\n"
            "\n指定頻道的方式：\n"
            "1. 使用頻道標記：#general\n"
            "2. 使用頻道ID：1234567890\n"
            "3. 使用頻道名稱：general\n"
            "\n例如：\n"
            "1. 固定時間範圍：\n"
            "!set_reminder #公告 09:00 早安提醒 11/1 11/20 打卡提醒\n"
            "2. 永久提醒：\n"
            "!set_reminder #公告 09:00 打卡提醒 permanent permanent 記得打卡```"
        ),
        inline=False
    )
    embed.add_field(
        name="其他指令",
        value=(
            "```\n"
            "查看所有提醒：!list_reminders\n"
            "停止特定提醒：!stop_reminder <提醒ID>\n"
            "停止所有提醒：!stop_all_reminders\n"
            "顯示此幫助：!helphelpusagi\n"
            "```"
        ),
        inline=False
    )
    await ctx.send(embed=embed, view=view)

@bot.command(name="set_reminder")
async def set_reminder(ctx, channel_input: str, time: str, title: str, 
                      start_date: str, end_date: str, *, content: str):
    """設定提醒"""
    channel = await get_channel(ctx, channel_input)
    if not channel:
        await ctx.send("找不到指定的頻道！請確認頻道名稱或ID是否正確。")
        return

    if not channel.permissions_for(ctx.guild.me).send_messages:
        await ctx.send(f"我沒有在 {channel.mention} 發送訊息的權限！")
        return

    try:
        hour, minute = map(int, time.split(":"))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError
        time = f"{hour:02d}:{minute:02d}"
    except ValueError:
        await ctx.send("時間格式不正確！請使用 HH:MM 格式，例如 09:00 或 18:30")
        return

    start_dt = parse_date(start_date)
    end_dt = parse_date(end_date)
    
    if start_date.lower() != "permanent" and not start_dt:
        await ctx.send("開始日期格式不正確！請使用 MM/DD 格式或 permanent")
        return
    
    if end_date.lower() != "permanent" and not end_dt:
        await ctx.send("結束日期格式不正確！請使用 MM/DD 格式或 permanent")
        return

    if start_dt and end_dt and start_dt > end_dt:
        await ctx.send("開始日期不能晚於結束日期！")
        return

    reminder_id = str(uuid.uuid4())
    reminder_tasks[reminder_id] = {
        "user_id": ctx.author.id,
        "channel_id": channel.id,
        "time": time,
        "title": title,
        "start_date": start_date,
        "end_date": end_date,
        "content": content
    }

    embed = discord.Embed(title="✅ 提醒設定成功", color=discord.Color.green())
    embed.add_field(name="提醒ID", value=reminder_id, inline=False)
    embed.add_field(name="頻道", value=channel.mention, inline=True)
    embed.add_field(name="時間", value=time, inline=True)
    embed.add_field(name="標題", value=title, inline=True)
    embed.add_field(name="開始日期", value=start_date, inline=True)
    embed.add_field(name="結束日期", value=end_date, inline=True)
    embed.add_field(name="內容", value=content, inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name="list_reminders")
async def list_reminders(ctx):
    """列出當前的提醒設定"""
    user_reminders = get_user_reminders(ctx.author.id)
    
    if not user_reminders:
        await ctx.send("你目前沒有設定提醒。")
        return

    embed = discord.Embed(title="當前提醒設定", color=discord.Color.blue())
    
    for idx, reminder in enumerate(user_reminders, 1):
        channel = bot.get_channel(reminder["channel_id"])
        channel_mention = channel.mention if channel else "未知頻道"
        
        reminder_id = [k for k, v in reminder_tasks.items() if v == reminder][0]
        
        embed.add_field(
            name=f"提醒 {idx}",
            value=(
                f"ID: {reminder_id}\n"
                f"頻道: {channel_mention}\n"
                f"時間: {reminder['time']}\n"
                f"標題: {reminder['title']}\n"
                f"開始日期: {reminder['start_date']}\n"
                f"結束日期: {reminder['end_date']}\n"
                f"內容: {reminder['content']}"
            ),
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name="stop_reminder")
async def stop_reminder(ctx, reminder_id: str):
    """停止特定提醒"""
    if reminder_id not in reminder_tasks:
        await ctx.send("找不到指定的提醒ID！")
        return
        
    reminder = reminder_tasks[reminder_id]
    if reminder["user_id"] != ctx.author.id:
        await ctx.send("你只能停止自己設定的提醒！")
        return

    channel = bot.get_channel(reminder["channel_id"])
    channel_mention = channel.mention if channel else "未知頻道"
    
    embed = discord.Embed(title="🛑 提醒已停止", color=discord.Color.red())
    embed.add_field(name="提醒ID", value=reminder_id, inline=True)
    embed.add_field(name="頻道", value=channel_mention, inline=True)
    embed.add_field(name="標題", value=reminder["title"], inline=True)
    
    await ctx.send(embed=embed)
    del reminder_tasks[reminder_id]

@bot.command(name="stop_all_reminders")
async def stop_all_reminders(ctx):
    """停止所有提醒"""
    user_reminders = get_user_reminders(ctx.author.id)
    
    if not user_reminders:
        await ctx.send("你目前沒有設定提醒。")
        return

    # 找出並刪除所有屬於該用戶的提醒
    removed_count = 0
    for reminder_id, reminder in list(reminder_tasks.items()):
        if reminder["user_id"] == ctx.author.id:
            del reminder_tasks[reminder_id]
            removed_count += 1

    embed = discord.Embed(title="🛑 所有提醒已停止", color=discord.Color.red())
    embed.add_field(name="已停止提醒數量", value=str(removed_count), inline=False)
    await ctx.send(embed=embed)

# 啟動機器人


bot.run(TOKEN)