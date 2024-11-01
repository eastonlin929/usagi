

from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    # 确保使用 Render 提供的端口
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# 修改 keep_alive() 的實現
def keep_alive():
    # 如果 thread 已經在運行，就不要再建立新的
    if not hasattr(keep_alive, 'thread') or not keep_alive.thread.is_alive():
        keep_alive.thread = Thread(target=run)
        keep_alive.thread.daemon = True  # 設置為 daemon thread
        keep_alive.thread.start()

import discord
from discord.ext import commands, tasks
import datetime
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import re
import uuid
from dotenv import load_dotenv

import json


# 設置基本配置
load_dotenv()
TOKEN = os.getenv('TOKEN')
reminder_tasks: Dict[str, dict] = {}  # 使用 UUID 作為 key 來存儲提醒

# 添加環境變量支持
REMINDERS_FILE = os.getenv('REMINDERS_FILE', 'reminders.json')

def save_reminders(self):
    try:
        with open(REMINDERS_FILE, 'w') as f:
            json.dump(reminder_tasks, f)
            print(f"Saved {len(reminder_tasks)} reminders")
    except Exception as e:
        print(f"Error saving reminders: {e}")

# 在 Render 上設置環境變量
# REMINDERS_FILE=/tmp/reminders.json
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
        self.last_check = {}
        try:
            self.load_reminders()  # 修改為實例方法
            print("Reminders loaded successfully")
        except Exception as e:
            print(f"Error loading reminders: {e}")
        self.check_reminders.start()

    def load_reminders(self):  # 修改為實例方法
        try:
            with open('reminders.json', 'r') as f:
                loaded_tasks = json.load(f)
                reminder_tasks.update(loaded_tasks)
                print(f"Loaded {len(loaded_tasks)} reminders")
        except FileNotFoundError:
            print("No existing reminders file found")
            pass
        except Exception as e:
            print(f"Error in load_reminders: {e}")

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        try:
            now = datetime.now()
            print(f"Checking reminders at {now}")  # 添加日誌
            current_time = now.strftime("%H:%M")
            
            for reminder_id, reminder in list(reminder_tasks.items()):
                print(f"Checking reminder {reminder_id}")  # 添加日誌
                # ... 其餘代碼保持不變 ...
                
        except Exception as e:
            print(f"Error in check_reminders: {e}")
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

@bot.command(name="remove_reminder")
async def remove_reminder(ctx, reminder_id: str):
    """移除特定的提醒消息"""
    try:
        # 檢查提醒是否存在
        if reminder_id not in reminder_tasks:
            await ctx.send("❌ 找不到指定的提醒ID。請使用 `!list_reminders` 查看所有可用的提醒。")
            return

        reminder = reminder_tasks[reminder_id]
        
        # 確認是否為提醒的創建者
        if reminder["user_id"] != ctx.author.id:
            await ctx.send("❌ 您只能移除自己創建的提醒。")
            return

        # 創建嵌入訊息顯示要刪除的提醒詳情
        embed = discord.Embed(
            title="🗑️ 確認移除提醒",
            color=discord.Color.yellow(),
            timestamp=datetime.now()
        )

        channel = bot.get_channel(reminder["channel_id"])
        channel_name = channel.name if channel else "未知頻道"

        embed.add_field(
            name="提醒詳情",
            value=(
                f"**標題:** {reminder['title']}\n"
                f"**頻道:** #{channel_name}\n"
                f"**結束日期:** {reminder['end_date']}\n"
                f"**提醒ID:** {reminder_id}"
            ),
            inline=False
        )

        # 創建確認按鈕
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(label="確認刪除", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ 只有提醒的創建者可以確認刪除。", ephemeral=True)
                    return

                # 移除提醒
                del reminder_tasks[reminder_id]
                
                # 更新嵌入訊息
                embed.color = discord.Color.green()
                embed.title = "✅ 提醒已移除"
                
                # 停用所有按鈕
                for child in self.children:
                    child.disabled = True
                
                await interaction.message.edit(embed=embed, view=self)
                await interaction.response.send_message("✅ 提醒已成功移除！", ephemeral=True)

            @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ 只有提醒的創建者可以取消操作。", ephemeral=True)
                    return

                embed.color = discord.Color.blue()
                embed.title = "❌ 取消移除提醒"
                
                # 停用所有按鈕
                for child in self.children:
                    child.disabled = True
                
                await interaction.message.edit(embed=embed, view=self)
                await interaction.response.send_message("已取消移除提醒。", ephemeral=True)

        view = ConfirmView()
        await ctx.send(embed=embed, view=view)

    except Exception as e:
        await ctx.send(f"❌ 移除提醒時發生錯誤：{str(e)}")
        print(f"Error removing reminder: {e}")

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
            "移除過期提醒：!remove_old_reminders\n"
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

keep_alive()
bot.run(TOKEN)