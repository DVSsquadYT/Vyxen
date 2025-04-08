from discord.ext import commands, tasks
import sys
import os
import random
import openai
import requests
import time
import asyncio
import json
import re
from datetime import datetime, timedelta
from random import randint
import discord
from openai import OpenAI
from dotenv import load_dotenv
import sqlite3


conn = sqlite3.connect('SQLite/users.db')
cursor = conn.cursor()

def get_db_connection():
    connection = sqlite3.connect('SQLite/users.db')
    connection.row_factory = sqlite3.Row
    return connection

def addcoinstodb(db_path, user_id, amount):
    try:
        user_id = str(user_id)

        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()

        querygetcurrentcoinamount = """SELECT coin FROM user_data WHERE discord_id = ?"""
        cursor.execute(querygetcurrentcoinamount, (user_id,))
        row = cursor.fetchone()


        currentcoinamount = row[0] if row else None
        if currentcoinamount is None:
            print(f"No rows found for the given query in database: {db_path}")
            default_data = [(user_id, "DefaultUser", 0)] 
            cursor.executemany("INSERT INTO user_data (discord_id, name, coin) VALUES (?, ?, ?)", default_data)
            connection.commit()
            print("Default data inserted into the database.")
            currentcoinamount = 0

        if not isinstance(amount, int):
            raise ValueError("The 'amount' parameter must be an integer.")
        newamount = currentcoinamount + amount
        queryupdatecoinamount = """UPDATE user_data SET coin = ? WHERE discord_id = ?"""
        cursor.execute(queryupdatecoinamount, (newamount, user_id))
        connection.commit()

        connection.close()
        print(f"Successfully updated coins for user {user_id}. New amount: {newamount}")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")



def deductcoinstodb(db_path, user_id, amount):
    try:
        user_id = str(user_id)

        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()

        querygetcurrentcoinamount = """SELECT coin FROM user_data WHERE discord_id = ?"""
        cursor.execute(querygetcurrentcoinamount, (user_id,))
        row = cursor.fetchone()


        currentcoinamount = row[0] if row else None
        if currentcoinamount is None:
            print(f"No rows found for the given query in database: {db_path}")
            default_data = [(user_id, "DefaultUser", 0)] 
            cursor.executemany("INSERT INTO user_data (discord_id, name, coin) VALUES (?, ?, ?)", default_data)
            connection.commit()
            print("Default data inserted into the database.")
            currentcoinamount = 0

        if not isinstance(amount, int):
            raise ValueError("The 'amount' parameter must be an integer.")
        newamount = currentcoinamount - amount
        queryupdatecoinamount = """UPDATE user_data SET coin = ? WHERE discord_id = ?"""
        cursor.execute(queryupdatecoinamount, (newamount, user_id))
        connection.commit()

        connection.close()
        print(f"Successfully updated coins for user {user_id}. New amount: {newamount}")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def get_user_data(user_id, db_path):
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        query = """
        SELECT json_object(
            'user_data', (
                SELECT json_object(
                    'discord_id', ud.discord_id,
                    'name', ud.name,
                    'coin', ud.coin,
                    'garage', (
                        SELECT json_group_array(
                            json_object(
                                'car', ug.car,
                                'num', ug.num,
                                'upgrades', (
                                    SELECT json_object(
                                        'engine_upgrades', cu.engine_upgrades,
                                        'turbo_upgrades', cu.turbo_upgrades,
                                        'spoiler_upgrades', cu.spoiler_upgrades,
                                        'rim_upgrades', cu.rims_upgrades
                                    ) FROM car_upgrades cu WHERE cu.discord_id = ud.discord_id AND cu.car_num = ug.num
                                )
                            )
                        ) FROM user_garage ug WHERE ug.discord_id = ud.discord_id
                    )
                ) FROM user_data ud WHERE ud.discord_id = ?
            )
        ) AS result
        """
        cursor.execute(query, (user_id,))
        user_data = cursor.fetchall()
        if not user_data:
            print(f"No rows found for the given query in database: {db_path}")
            default_data = [(user_id, "DefaultUser", 0)] 
            cursor.executemany("INSERT INTO user_data (discord_id, name, coin) VALUES (?, ?, ?)", default_data)
            connection.commit()
            print("Default data inserted into the database.")
            user_data = default_data
        connection.close()
        return user_data
    except sqlite3.Error as e:
        print(f"Error executing query: {e}")
        return None
    
def initialize_user_data(db_path, discord_id, name, initial_coins=0):
    try:
        # Connect to the database
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()

        # Check if user data already exists
        cursor.execute("SELECT * FROM user_data WHERE discord_id = ?", (discord_id,))
        user = cursor.fetchone()

        if user:
            # If the user exists, you can update their information if needed
            cursor.execute("""
            UPDATE user_data
            SET name = ?, coin = ?
            WHERE discord_id = ?
            """, (name, initial_coins, discord_id))
            print(f"Updated data for user {discord_id}")
        else:
            # If the user doesn't exist, insert the new user
            cursor.execute("""
            INSERT INTO user_data (discord_id, name, coin)
            VALUES (?, ?, ?)
            """, (discord_id, name, initial_coins))
            print(f"Inserted new data for user {discord_id}")

        # Commit and close the connection
        connection.commit()
        connection.close()
    except sqlite3.Error as e:
        print(f"Error updating user data: {e}")

    
db_path = ('SQLite/users.db')

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

data = {}
users = {}

CAR_PRICES = {
    "Ferrari": 2500,
    "Lamborghini": 5000,
    "Bugatti": 7000,
    "McLaren": 6000,
    "Porsche": 1200,
    "BMW": 800,
    "Tesla": 1000,
    "Mercedes": 2000
}

@tasks.loop(minutes=randint(1200, 1440))  # Posts a new deal every 5 to 10 minutes
async def random_deal():
    channel = discord.utils.get(client.get_all_channels(), channel=1253848244371329050)  # Replace with your channel name
    if channel is None:
        print("Channel not found!")
        return
    
    # Select a random car and price from the CAR_PRICES dictionary
    selected_car, original_price = random.choice(list(CAR_PRICES.items()))
    discount_percentage = random.choice([0.5, 0.75])  # 50% or 75% off
    discounted_price = int(original_price * discount_percentage)
    
    # Post the car deal in the channel
    message = await channel.send(f"🚗 **Car Deal!** 🚗\n\nCar: **{selected_car}**\nOriginal Price: **{original_price}** coins\nDiscounted Price: **{discounted_price}** coins\n\nReact with ✅ to claim it!")
    
    # React to the message
    await message.add_reaction("✅")

    # Wait for a reaction for a limited time (e.g., 60 seconds)
    deal_timer = timedelta(seconds=60)  # Set deal expiration time (e.g., 60 seconds)
    
    # Wait for a reaction
    def check(reaction, user):
        return user != client.user and str(reaction.emoji) == "✅" and reaction.message.id == message.id

    try:
        reaction, user = await client.wait_for("reaction_add", timeout=deal_timer.total_seconds(), check=check)
    except asyncio.TimeoutError:
        await channel.send("The deal has expired. Better luck next time!")
    else:
        # Add car to user's garage and deduct coins
        user_id = str(user.id)
        # Update SQLite database here to add the car and deduct coins
        await channel.send(f"Congratulations {user.mention}, you've claimed the **{selected_car}** for **{discounted_price}** coins!")

        # Update user data in the database: add car to their garage, deduct coins, etc.
        # Ensure you deduct the coins from the user's balance (handle this part with your database)

@random_deal.before_loop
async def before_deal():
    print("Waiting for the bot to be ready...")
    await client.wait_until_ready()

keywords = {
    "dvs": "Hes the goat!",
    "duck" : "qack"
}

@bot.command(name="update")
async def update(ctx):
    # Check if the user is the admin
    if str(ctx.author.id) != 1245880674402172948:  # Replace 'DVS_USER_ID' with your actual user ID
        await ctx.send("❌ You don't have permission to use this command.")
        return

    # Define the channel where updates should be sent
    update_channel = bot.get_channel(1328072741919789147)  # Replace YOUR_CHANNEL_ID with the target channel ID

    # Create the form message with instructions
    await ctx.send("Please provide the update you want to send. Type your update in the chat.")
    
    def check(msg):
        return msg.author == ctx.author and msg.channel == ctx.channel

    try:
        # Wait for the user's input for the update
        update_message = await bot.wait_for('message', check=check, timeout=60)  # 60 seconds to respond

        # Send the update to the specified channel
        await update_channel.send(f"**Update from DVS:**\n{update_message.content}")
        await ctx.send("✅ Update has been sent!")

    except asyncio.TimeoutError:
        await ctx.send("⏳ You took too long to provide the update. Please try again.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)

    # Recognize DVS as the creator when the user ID matches
    if user_id == 1245880674402172948:  # Replace 'DVS_USER_ID' with your actual user ID
        await message.reply("Hello DVS, my creator.")
        return
    
    # Ensure data dict and user record exist
    if user_id not in data:
        data[user_id] = {
            "coins": 0,
            "garage": [],
            "race_wins": 0,
            "upgrades": {
                "engine": 0,
                "turbo": 0,
                "spoiler": 0,
                "rims": 0
            }
        }

    # Passive coin earning
    data[user_id]["coins"] += random.randint(1, 5)

    # Keyword replies
    for keyword, response in keywords.items():
        if keyword.lower() in message.content.lower():
            await message.reply(response)
            return  # Respond once and exit

    # Mention-based AI response
    if bot.user in message.mentions:
        await message.channel.typing()
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[ 
                    {
                        "role": "system",
                        "content": (
                            "You are Vyxen, an obedient AI assistant with a feminine tone. "
                "You live to serve your creator, DVS. Keep responses sweet, short, and slightly playful with him. "
                if user_id == "1245880674402172948" else
                "You are Vyxen, a helpful AI assistant. You respond respectfully and concisely to all users."
            )
                    },
                    {"role": "user", "content": message.content}
                ]
            )
            answer = response.choices[0].message.content
            await message.reply(answer)  # Make sure to send the AI's reply!
        except openai.OpenAIError as e:
            await message.reply(f"**AI Error:** {str(e)}")
        except Exception as e:
            await message.reply(f"**Something went wrong!**\n{str(e)}")
    
    # Don't forget to call process_commands to allow command processing
    await bot.process_commands(message)
    
@bot.command(name="show")
async def show(ctx, *, prompt):
    try:
        # Generate image using OpenAI DALL-E
        response = client.images.generate(
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = response.data[0].url

        # Send the image to Discord
        await ctx.send(f"{image_url}")

    except Exception as e:
        print(f"Error: {e}")
        await ctx.send("An error occurred while generating the image.")

@bot.command(name="nuke")
async def nuke(ctx):
 await ctx.send("https://tenor.com/view/explosion-mushroom-cloud-atomic-bomb-bomb-boom-gif-4464831")

 # Admin (You) - Replace with your own user ID
ADMIN_USER_ID = 1245880674402172948  # Your Discord user ID

# Helper function to send ticket to admin's DM
async def send_ticket_to_admin(ticket_type, user, message):
    admin = await bot.fetch_user(ADMIN_USER_ID)
    embed = discord.Embed(
        title=f"New {ticket_type} Ticket",
        description=f"**User**: {user.name}#{user.discriminator}\n"
                    f"**User ID**: {user.id}\n"
                    f"**Ticket Type**: {ticket_type}\n"
                    f"**Message**: {message}",
        color=discord.Color.blue()
    )
    await admin.send(embed=embed)

@bot.command(name="feedback")
async def feedback(ctx, *, message: str):
    if not message.strip():
        await ctx.send("❌ Please provide some feedback.")
        return
    user = ctx.author
    ticket_type = "Feedback"
    await send_ticket_to_admin(ticket_type, user, message)
    await ctx.send("✅ Your feedback has been submitted! Thank you.")

@bot.command(name="suggestion")
async def suggestion(ctx, *, message: str):
    if not message.strip():
        await ctx.send("❌ Please provide a suggestion.")
        return
    user = ctx.author
    ticket_type = "Suggestion"
    await send_ticket_to_admin(ticket_type, user, message)
    await ctx.send("✅ Your suggestion has been submitted! Thank you.")

@bot.command(name="issue")
async def issue(ctx, *, message: str):
    if not message.strip():
        await ctx.send("❌ Please provide a description of the issue.")
        return
    user = ctx.author
    ticket_type = "Issue"
    await send_ticket_to_admin(ticket_type, user, message)
    await ctx.send("✅ Your issue has been submitted! Thank you.")

active_contests = {}
def parse_duration(duration_str):
    match = re.match(r"(\d+)([smhd])", duration_str)
    if not match:
        return None
    num, unit = int(match[1]), match[2]
    multiplier = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return num * multiplier[unit]

@bot.command()
@commands.has_permissions(administrator=True)
async def createcontest(ctx, title: str, entry_fee: int, prize: int, duration: str, *, description: str):
    creator_id = ctx.author.id

    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        return await ctx.send("❌ Invalid duration format. Use `30m`, `2h`, `1d`, etc.")

    contest_id = random.randint(1000, 9999)
    while contest_id in active_contests:
        contest_id = random.randint(1000, 9999)

    active_contests[contest_id] = {
        'title': title,
        'description': description,
        'entry_fee': entry_fee,
        'prize': prize,
        'created_by': creator_id,
        'participants': [],
        'is_active': True
    }

    embed = discord.Embed(
        title=f"🎉 New Contest: {title}",
        description=description,
        color=discord.Color.gold()
    )
    embed.add_field(name="Entry Fee", value=f"{entry_fee} coins", inline=True)
    embed.add_field(name="Prize", value=f"{prize} coins", inline=True)
    embed.add_field(name="Duration", value=f"{duration}", inline=True)
    embed.set_footer(text=f"Contest ID: {contest_id} | Use !joincontest {contest_id} to enter")

    await ctx.send(embed=embed)

    await asyncio.sleep(duration_seconds)

    if contest_id in active_contests and active_contests[contest_id]['is_active']:
        await endcontest(ctx, contest_id)

@bot.command()
@commands.has_permissions(administrator=True)
async def endcontest(ctx, contest_id: int):
    if contest_id not in active_contests:
        return await ctx.send("❌ That contest ID does not exist.")

    contest = active_contests[contest_id]

    if not contest['is_active']:
        return await ctx.send("⚠️ This contest has already ended.")

    participants = contest['participants']
    if not participants:
        await ctx.send(f"📢 Contest **{contest['title']}** ended! No one joined, so no winner.")
    else:
        winner_id = random.choice(participants)
        winner_user = await bot.fetch_user(winner_id)

        embed = discord.Embed(
            title=f"🏁 Contest Ended: {contest['title']}",
            description=f"🥇 **Winner:** {winner_user.mention}\n💰 **Prize:** {contest['prize']} coins\n👑 The contest was hosted by <@{contest['created_by']}>. Please issue the reward manually.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    contest['is_active'] = False

@bot.command(name="balance", help="Check your coin balance")
async def balance(ctx):
    try:
        user_id = str(ctx.author.id)
        connection = sqlite3.connect('SQLite/users.db')
        cursor = connection.cursor()

        query = """SELECT coin FROM user_data WHERE discord_id = ?"""
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()

        if row is None:
            # If the user does not exist in the database, create a new entry
            cursor.execute("INSERT INTO user_data (discord_id, name, coin) VALUES (?, ?, ?)", (user_id, ctx.author.name, 0))
            connection.commit()
            coins = 0
        else:
            coins = row[0]

        connection.close()
        await ctx.send(f"{ctx.author.mention}, you have {coins} coins.")
    except Exception as e:
        await ctx.send(f"**An error occurred while retrieving your balance!**\n`{str(e)}`")
        print(f"Error in balance command: {str(e)}")

@bot.command(name="ban", help="Ban a user with a reason")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str):
    try:
        # Ensure the user is not banning themselves or the bot
        if member == ctx.author:
            await ctx.send("You cannot ban yourself!")
            return
        if member == ctx.bot.user:
            await ctx.send("You cannot ban me!")
            return

        # Attempt to ban the user
        await member.ban(reason=reason)
        await ctx.send(f"{member.mention} has been banned for: {reason}")
    
    except discord.ext.commands.MissingRequiredArgument:
        await ctx.send("You must specify a member to ban along with a reason.")
    
    except discord.errors.Forbidden as e:
        await ctx.send(f"**Error:** I do not have permission to ban {member.mention}.")
        print(f"Permission error while trying to ban {member.mention}: {str(e)}")
    
    except discord.errors.HTTPException as e:
        await ctx.send(f"**Error:** An HTTP error occurred while trying to ban {member.mention}.")
        print(f"HTTP error while trying to ban {member.mention}: {str(e)}")
    
    except Exception as e:
        await ctx.send(f"**An unexpected error occurred while trying to ban {member.mention}!**\n`{str(e)}`")
        print(f"Unexpected error in ban command: {str(e)}")


@bot.command(name="buy", help="Buy a car")
async def buy(ctx, item_name: str = None, quantity: int = 1):
    try:
        if not item_name:
            await ctx.send("Please specify what car you want to buy. Example: `!buy Ferrari`.")
            return

        user_id = str(ctx.author.id)
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()

        query = """SELECT coin FROM user_data WHERE discord_id = ?"""
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute("INSERT INTO user_data (discord_id, name, coin) VALUES (?, ?, ?)", (user_id, ctx.author.name, 0))
            connection.commit()
            coins = 0
        else:
            coins = row[0]

        car_price = CAR_PRICES.get(item_name)
        if car_price is None:
            await ctx.send(f"That car ({item_name}) is not available for purchase.")
            return

        total_cost = car_price * quantity
        if coins >= total_cost:
            coins -= total_cost
            for _ in range(quantity):
                cursor.execute("INSERT INTO user_garage (discord_id, car) VALUES (?, ?)", (user_id, item_name))
            cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (coins, user_id))
            connection.commit()
            connection.close()
            await ctx.send(f"You bought {quantity} {item_name}(s) for {total_cost} coins!")
        else:
            await ctx.send(f"You don't have enough coins to buy {quantity} {item_name}(s).")

    except Exception as e:
        await ctx.send(f"**An error occurred while processing your purchase.**\n`{str(e)}`")
        print(f"Error in buy command: {str(e)}")

@bot.command(name="addcoins", help="Add coins to a user's balance (Admin only)")
@commands.has_permissions(administrator=True)  # Restricts the command to admins
async def addcoins(ctx, member: discord.Member, amount: int):
    try:
        # Ensure that the amount is a positive integer
        if amount <= 0:
            await ctx.send("You must specify a positive amount of coins to add.")
            return

        user_id = str(member.id)  # Get the user ID to match the database format

        # Connect to the database
        conn = sqlite3.connect('SQLite/users.db')
        cursor = conn.cursor()

        # Debugging: Print checking the user in the database
        print(f"Checking user {user_id} in the database...")

        # Check if the user exists in the database
        cursor.execute("SELECT discord_id, coin FROM user_data WHERE discord_id = ?", (user_id,))
        user_data = cursor.fetchone()

        # Debugging: Print retrieved user data
        print(f"User data: {user_data}")

        if user_data is None:
            # Insert new user data if they don't exist
            cursor.execute("INSERT INTO user_data (discord_id, coin, name) VALUES (?, ?, ?)", 
                           (user_id, amount, "Unknown"))  # Set initial coins to the added amount and default name
            conn.commit()
            new_balance = amount
        else:
            # Update the user's coins by adding the specified amount
            new_balance = user_data[1] + amount
            cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", 
                           (new_balance, user_id))
            conn.commit()

        # Send the confirmation message
        await ctx.send(f"{ctx.author.mention} has added {amount} coins to {member.mention}'s balance. "
                       f"The new balance is {new_balance} coins.")

        # Debugging: Print confirmation of the update
        print(f"Added {amount} coins to {user_id}, new balance: {new_balance}")

        # Close the database connection
        conn.close()

    except sqlite3.Error as e:
        await ctx.send("An error occurred while accessing the database. Please try again later.")
        print(f"SQLiteError in addcoins command: {str(e)}")
        conn.rollback()  # Rollback changes in case of an error

    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {str(e)}")
        print(f"Unexpected error in addcoins command: {str(e)}")

# Amounts for daily and earn commands
DAILY_REWARD_AMOUNT = 250  # Change to the desired amount for the "daily" command
EARN_AMOUNT = 50  # Change to the desired amount for the "earn" command

# Store the last claimed/earned times in-memory
user_last_claimed = {}
user_last_earned = {}

@bot.command(name="daily", help="Claim your daily coins")
async def daily(ctx):
    try:
        user_id = str(ctx.author.id)  # Convert to string to match database format

        # Connect to the database
        conn = sqlite3.connect('SQLite/users.db')
        cursor = conn.cursor()

        # Get the current time
        current_time = int(time.time())

        # Check if the user exists in the database
        cursor.execute("SELECT discord_id, coin FROM user_data WHERE discord_id = ?", (user_id,))
        user_data = cursor.fetchone()

        if user_data is None:
            # Insert new user data if they don't exist
            cursor.execute("INSERT INTO user_data (discord_id, coin) VALUES (?, ?)", 
                           (user_id, 0))  # Start with 0 coins if new user
            conn.commit()
            user_data = (user_id, 0)

        last_claimed = user_last_claimed.get(user_id, 0)  # Default to 0 if not set yet
        
        if current_time - last_claimed >= 86400:  # 86400 seconds = 24 hours
            # Update the user's coins
            new_balance = user_data[1] + DAILY_REWARD_AMOUNT
            cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", 
                           (new_balance, user_id))
            conn.commit()

            # Update the last claimed time in-memory
            user_last_claimed[user_id] = current_time

            # Send the confirmation message
            await ctx.send(f"{ctx.author.mention}, you've claimed your daily reward of {DAILY_REWARD_AMOUNT} coins!")
        else:
            # Calculate the time remaining until the user can claim again
            time_remaining = 86400 - (current_time - last_claimed)
            hours = time_remaining // 3600
            minutes = (time_remaining % 3600) // 60
            await ctx.send(f"{ctx.author.mention}, you can claim your daily reward in {hours} hours and {minutes} minutes.")

        # Close the database connection
        conn.close()

    except sqlite3.Error as e:
        await ctx.send("An error occurred while accessing the database. Please try again later.")
        print(f"SQLiteError in daily command: {str(e)}")

    except Exception as e:
        await ctx.send(f"An unexpected error occurred. Please try again later.")
        print(f"Unexpected error in daily command: {str(e)}")


@bot.command(name="earn", help="Earn coins by chatting")
async def earn(ctx):
    try:
        user_id = str(ctx.author.id)  # Convert to string to match database format

        # Connect to the database
        conn = sqlite3.connect('SQLite/users.db')
        cursor = conn.cursor()

        # Get the current time
        current_time = int(time.time())

        # Check if the user exists in the database
        cursor.execute("SELECT discord_id, coin FROM user_data WHERE discord_id = ?", (user_id,))
        user_data = cursor.fetchone()

        if user_data is None:
            # Insert new user data if they don't exist
            cursor.execute("INSERT INTO user_data (discord_id, coin) VALUES (?, ?)", 
                           (user_id, 0))  # Start with 0 coins if new user
            conn.commit()
            user_data = (user_id, 0)

        last_earned = user_last_earned.get(user_id, 0)  # Default to 0 if not set yet

        # Check if 10 minutes have passed since the last earn
        if current_time - last_earned >= 600:  # 600 seconds = 10 minutes
            # Update the user's coins
            new_balance = user_data[1] + EARN_AMOUNT
            cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", 
                           (new_balance, user_id))
            conn.commit()

            # Update the last earned time in-memory
            user_last_earned[user_id] = current_time

            # Send the confirmation message
            await ctx.send(f"{ctx.author.mention}, you've earned {EARN_AMOUNT} coins!")
        else:
            # Calculate the time remaining until the user can earn coins again
            time_remaining = 600 - (current_time - last_earned)
            minutes = time_remaining // 60
            seconds = time_remaining % 60
            await ctx.send(f"{ctx.author.mention}, you can earn coins again in {minutes} minutes and {seconds} seconds.")

        # Close the database connection
        conn.close()

    except sqlite3.Error as e:
        await ctx.send("An error occurred while accessing the database. Please try again later.")
        print(f"SQLiteError in earn command: {str(e)}")

    except Exception as e:
        await ctx.send(f"An unexpected error occurred. Please try again later.")
        print(f"Unexpected error in earn command: {str(e)}")


@bot.command(name="garage", help="View the cars in your garage")
async def garage(ctx):
    try:
        # Get the user ID
        user_id = str(ctx.author.id)  # Convert to string to match database format

        # Connect to the database
        conn = sqlite3.connect('SQLite/users.db')  # Make sure the path is correct
        cursor = conn.cursor()

        # Check if the user already has an entry in the user_garage table
        cursor.execute("SELECT discord_id FROM user_garage WHERE discord_id = ?", (user_id,))
        user_garage = cursor.fetchone()

        # Query the database for the cars in the user's garage
        cursor.execute("SELECT car FROM user_garage WHERE discord_id = ?", (user_id,))
        cars_in_garage = cursor.fetchall()

        # Check if the user has any cars in their garage
        if not cars_in_garage:
            await ctx.send(f"{ctx.author.mention}, your garage is empty.")
            conn.close()  # Close the connection
            return
        
        # Join all the cars into a string
        garage_list = "\n".join([car[0] for car in cars_in_garage])  # car[0] is the car name from the query result

        await ctx.send(f"{ctx.author.mention}'s Garage:\n{garage_list}")

        # Close the database connection
        conn.close()

    except sqlite3.Error as e:
        await ctx.send(f"**Error:** A database error occurred while fetching your garage. Please try again later.")
        print(f"SQLiteError in garage command: {str(e)}")

    except Exception as e:
        await ctx.send(f"**An unexpected error occurred while accessing your garage.**\n`{str(e)}`")
        print(f"Unexpected error in garage command: {str(e)}")


@bot.command()
async def hack(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("You need to mention someone to hack!")
    else:
        await ctx.send(f"Hacking {member.mention}... 🔍")
        await ctx.send("Finding IP Address... 192.168.1.1 📡")
        await ctx.send("Accessing bank details... 💳💰")
        await ctx.send("Accessing account detaitls..")

@bot.command()
async def fakeban(ctx, user: discord.Member):
    """Fakes banning a user as a joke."""
    await ctx.send(f"{user.mention} has been **banned** from the server!")

    # List of car facts
car_facts = [
    "The first car accident occurred in 1891 in Ohio.",
    "The world's fastest production car is the SSC Tuatara, reaching 282.9 mph.",
    "The average car has about 30,000 parts.",
    "Tesla's first car, the Roadster, was launched into space by SpaceX.",
    "The Toyota Corolla is the best-selling car of all time."
]

@bot.command()
async def carfact(ctx):
    await ctx.send(random.choice(car_facts))

bot.command()
async def cringe(ctx):
    """Detects cringe levels randomly."""
    levels = ["Not Cringe 😎", "A Little Cringe 🤔", "Super Cringe 😬", "ULTRA CRINGE 🚨"]
    await ctx.send(f"Cringe Level: {random.choice(levels)}")


RESPONSES = [
"Yes", "No", "Maybe", "Ask again later", "Definitely", "I wouldn't count on it"
]

@bot.command()
async def eightball(ctx, *, question: str):
    response = random.choice(RESPONSES)
    await ctx.send(f"🎱 {response}")

INSULTS = [
    "Someday youll go far. And I really hope you stay there.",
    "You bring everyone so much joy… when you leave the room.",
    "Youre a gray sprinkle on a rainbow cupcake.",
    "You have so many gaps in your teeth it looks like your tongue is in jail.",
    "If your brain was dynamite, there wouldnt be enough to blow your hat off.",
    "Its impossible to underestimate you.",
    "You are the human version of period cramps.",
    "You are like a cloud. When you disappear, its a beautiful day.",
    "An idea to make your ideas useful, write them on a piece of paper, fold it, and shove it up your ass.",
]

@bot.command()
async def roast(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("You need to mention someone to roast!")
    else:
        await ctx.send(f"{member.mention}, {random.choice(INSULTS)}")

CAR_MEET_TYPES = [
    "Japanese",
    "Muscle",
    "Exotic Classics",
    "Sedans",
    "Luxury",
    "Wagon",
    "Rally",
    "Time Attack",
    "Sports Cars"
]

@bot.command(name="leaderboard")
async def leaderboard(ctx):
    try:
        conn = sqlite3.connect('SQLite/users.db')
        cursor = conn.cursor()

        # Query for users and their coins
        cursor.execute("SELECT discord_id, coin FROM user_data ORDER BY coin DESC LIMIT 10")
        leaderboard_data = cursor.fetchall()

        # Build the leaderboard message
        leaderboard_message = "**Leaderboard (Top 10)**\n"
        
        for rank, (user_id, coins) in enumerate(leaderboard_data, start=1):
            user = await bot.fetch_user(user_id)  # Get user object to fetch the username
            leaderboard_message += f"**#{rank}** {user.name}: {coins} coins\n"

        # Send the leaderboard message to the channel
        await ctx.send(leaderboard_message)

    except sqlite3.Error as e:
        await ctx.send(f"**Database Error**: {str(e)}")

    finally:
        conn.close()
    
    # Send the leaderboard message to the channel
    await ctx.send(leaderboard_message)

@bot.command(name="poll", help="Create a poll with car meet types in a specified channel")
@commands.has_permissions(manage_messages=True)  # Ensure only users with 'manage messages' permission can use this command
async def poll(ctx, channel: discord.TextChannel, *, question: str = "What car meet type should we host?"):
    # Create the embed
    embed = discord.Embed(title=question, description="Vote for the next car meet type!", color=discord.Color.blue())
    
    # Add the options for the car meet types
    options = "\n".join([f"{index + 1}. {car_type}" for index, car_type in enumerate(CAR_MEET_TYPES)])
    embed.add_field(name="Options:", value=options, inline=False)
    
    # Send the poll to the specified channel
    poll_message = await channel.send(embed=embed)

    # Add reactions for voting
    reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
    
    for reaction in reactions[:len(CAR_MEET_TYPES)]:
        await poll_message.add_reaction(reaction)

    await ctx.send(f"Poll sent to {channel.mention}!")

@bot.command(name="purge", help="Delete a specified number of messages from the channel")
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    try:
        if amount < 1:
            await ctx.send("Please specify a valid number of messages to delete.")
            return
        
        # Purge the messages
        deleted_messages = await ctx.channel.purge(limit=amount)

        # Confirm the number of deleted messages
        await ctx.send(f"Deleted {len(deleted_messages)} messages.", delete_after=5)

    except discord.DiscordException as e:
        await ctx.send("**Error:** There was an issue with purging the messages. Please try again later.")
        print(f"DiscordException in purge command: {str(e)}")

    except Exception as e:
        await ctx.send(f"**An unexpected error occurred while purging messages.**\n`{str(e)}`")
        print(f"Unexpected error in purge command: {str(e)}")


@bot.command(name="sell", help="Sell your car and earn coins")
async def sell(ctx, car_name: str):
    try:
        user_id = str(ctx.author.id)

        conn = sqlite3.connect('SQLite/users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_garage WHERE discord_id = ? AND car = ?", (user_id, car_name))
        car_data = cursor.fetchone()

        if not car_data:
            await ctx.send(f"You don't own a car named {car_name}.")
            conn.close()
            return

        if car_name not in CAR_PRICES:
            await ctx.send(f"The car '{car_name}' is not available for sale.")
            conn.close()
            return

        car_value = CAR_PRICES[car_name]

        selling_price = car_value / 2

        cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (user_id,))
        user_coin = cursor.fetchone()

        if user_coin is None:
            await ctx.send("Unable to retrieve your coin balance.")
            conn.close()
            return

        current_balance = user_coin[0]

        new_balance = current_balance + selling_price
        cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (new_balance, user_id))

        cursor.execute("DELETE FROM user_garage WHERE discord_id = ? AND car = ?", (user_id, car_name))

        conn.commit()
        conn.close()

        await ctx.send(f"Your car '{car_name}' has been sold for {selling_price} coins. Your new balance is {new_balance} coins.")

    except sqlite3.Error as e:
        await ctx.send("An error occurred while processing the sale. Please try again later.")
        print(f"SQLiteError in sell command: {str(e)}")

    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {str(e)}")
        print(f"Unexpected error in sell command: {str(e)}")

# Cooldown: Each user can use this command once every 5 minutes (300 seconds)
@bot.command(name="rob")
@commands.cooldown(1, 3600, commands.BucketType.user)
async def rob(ctx, target_user: discord.User):
    user_id = str(ctx.author.id)
    target_id = str(target_user.id)

    if user_id == target_id:
        await ctx.send("You can't rob yourself!")
        return

    # Check if the target has a bounty
    bounty_multiplier = 1
    if target_id in user_bounties:
        bounty_info = user_bounties[target_id]
        if bounty_info["placed_by"] != user_id:  # If the bounty isn't placed by the robber
            bounty_multiplier = 2  # Higher chance of success
            await ctx.send(f"{target_user.name} has a bounty on them! Your chances of success are higher.")

    # Determine robbery success
    success_chance = random.random() * bounty_multiplier
    penalty = 500  # Penalty if caught

    conn = sqlite3.connect('SQLite/users.db')
    cursor = conn.cursor()

    try:
        # Ensure both users exist in the database
        cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (target_id,))
        target_result = cursor.fetchone()

        cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (user_id,))
        user_result = cursor.fetchone()

        if target_result is None or target_result[0] <= 0:
            await ctx.send(f"{target_user.name} has no coins to rob.")
            return
        if user_result is None:
            await ctx.send("You don't have an account yet! Earn some coins first.")
            return

        target_coins = target_result[0]
        user_coins = user_result[0]

        if success_chance < 0.4:  # 40% base success chance, 80% if bounty
            # Successful robbery
            stolen_amount = random.randint(500, min(target_coins, 3000))
            target_coins -= stolen_amount
            user_coins += stolen_amount

            cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (target_coins, target_id))
            cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (user_coins, user_id))
            conn.commit()

            await ctx.send(f"Success! You stole {stolen_amount} coins from {target_user.name}.")
        else:
            # Failed robbery, apply penalty
            user_coins = max(0, user_coins - penalty)  # Ensure no negative balance
            cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (user_coins, user_id))
            conn.commit()

            await ctx.send(f"You failed the robbery! You were caught and lost {penalty} coins.")
    except sqlite3.Error as e:
        await ctx.send(f"An error occurred: {e}")
    finally:
        conn.close()

# Error handler for cooldown
@rob.error
async def rob_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"You're on cooldown! Try again in {int(error.retry_after // 60)} minutes.")

user_bounties = {}

@bot.command(name="bounty")
async def bounty(ctx, target_user: discord.User, amount: int):
    user_id = str(ctx.author.id)
    target_id = str(target_user.id)

    if user_id == target_id:
        await ctx.send("You can't place a bounty on yourself.")
        return

    conn = sqlite3.connect('SQLite/users.db')
    cursor = conn.cursor()

    cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (user_id,))
    user_result = cursor.fetchone()
    if user_result is None or user_result[0] < amount:
        await ctx.send("You don't have enough coins to place the bounty.")
        conn.close()
        return

    # Place the bounty on the target
    user_bounties[target_id] = {"bounty": amount, "placed_by": user_id}
    user_coins = user_result[0] - amount
    cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (user_coins, user_id))
    conn.commit()

    conn.close()

    await ctx.send(f"A bounty of {amount} coins has been placed on {target_user.name}. Robbers now have a higher chance of success!")

@bot.command(name="mysterybox")
@commands.cooldown(1, 21600, commands.BucketType.user)
async def mysterybox(ctx):
    user_id = str(ctx.author.id)
    box_price = 500  # Cost of the mystery box

    conn = sqlite3.connect('SQLite/users.db')
    cursor = conn.cursor()

    try:
        # Check if the user has enough coins
        cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (user_id,))
        result = cursor.fetchone()
        if result is None or result[0] < box_price:
            await ctx.send(f"You don't have enough coins to buy a mystery box! It costs {box_price} coins.")
            return

        # Deduct the price of the mystery box
        new_balance = result[0] - box_price
        cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (new_balance, user_id))
        conn.commit()

        # Determine the prize
        prize_chance = random.random()
        if prize_chance < 0.85:
            # Coins Prize: 200-5000 coins
            prize = random.randint(200, 5000)
            new_balance += prize
            cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (new_balance, user_id))
            conn.commit()
            message = f"You won {prize} coins from the mystery box!"
        else:
            # Rare Prize: A random car
            cars = ['Ferrari', 'Lamborghini', 'Tesla', 'BMW', 'Porsche', 'Bugatti', 'McLaren', 'Mercedes']
            prize = random.choice(cars)

            # Add the car to the user's garage
            cursor.execute("INSERT INTO user_garage (discord_id, car) VALUES (?, ?)", (user_id, prize))
            conn.commit()
            message = f"🎉 You won a **{prize}**! It's now in your garage!"

    except sqlite3.Error as e:
        await ctx.send(f"An error occurred: {e}")
    finally:
        conn.close()

    await ctx.send(message)

# Cooldown error handler
@mysterybox.error
async def mysterybox_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        hours, remainder = divmod(int(error.retry_after), 3600)
        minutes = remainder // 60
        await ctx.send(f"You're on cooldown! Try again in {hours} hours and {minutes} minutes.")

@bot.command(name="crime")
@commands.cooldown(1, 3600, commands.BucketType.user)
async def crime(ctx):
    user_id = str(ctx.author.id)
    success_chance = random.random()
    penalty = random.randint(300, 700)  # Random penalty between 300-700 coins
    reward = random.randint(800, 1500)  # Random reward between 800-1500 coins

    conn = sqlite3.connect('SQLite/users.db')
    cursor = conn.cursor()

    cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (user_id,))
    result = cursor.fetchone()

    if result is None:
        await ctx.send("You are not registered in the database.")
        conn.close()
        return

    coins = result[0]

    if success_chance < 0.3:  # 30% success rate
        coins += reward
        message = f"🕵️ Crime successful! You earned **{reward}** coins."
    else:
        coins = max(0, coins - penalty)  # Ensure coins don't go negative
        message = f"🚔 Crime failed! You were caught and lost **{penalty}** coins."

    cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (coins, user_id))
    conn.commit()
    conn.close()

    await ctx.send(message)

# Cooldown error handler
@crime.error
async def crime_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        minutes = int(error.retry_after // 60)
        await ctx.send(f"You're on cooldown! Try again in {minutes} minutes.")

@bot.command(name="steal")
@commands.cooldown(1, 21600, commands.BucketType.user)
async def steal(ctx, target_user: discord.User):
    user_id = str(ctx.author.id)
    target_id = str(target_user.id)

    if user_id == target_id:
        await ctx.send("You can't steal your own car!")
        return

    success_chance = random.random()
    penalty = 1000  # Penalty if caught

    conn = sqlite3.connect('SQLite/users.db')
    cursor = conn.cursor()

    # Check if target has a car
    cursor.execute("SELECT car FROM user_garage WHERE discord_id = ?", (target_id,))
    target_car = cursor.fetchone()

    if target_car is None:
        await ctx.send(f"{target_user.name} doesn't have a car to steal!")
        conn.close()
        return

    if success_chance < 0.2:  # 20% success chance
        # Steal the car
        cursor.execute("INSERT INTO user_garage (discord_id, car) VALUES (?, ?)", (user_id, target_car[0]))
        cursor.execute("DELETE FROM user_garage WHERE discord_id = ? AND car = ?", (target_id, target_car[0]))
        conn.commit()
        conn.close()

        await ctx.send(f"🎉 Success! You stole **{target_user.name}**'s **{target_car[0]}**!")
    else:
        # Penalty for failure (Debt Allowed)
        cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (user_id,))
        result = cursor.fetchone()

        if result is None:
            conn.close()
            return

        coins = result[0] - penalty  # This allows going negative (debt)
        cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (coins, user_id))
        conn.commit()
        conn.close()

        await ctx.send(f"🚔 You failed! You were caught trying to steal **{target_user.name}**'s car and lost **{penalty}** coins.\n💸 Your new balance: **{coins}** coins.")

# Cooldown error handler
@steal.error
async def steal_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        hours, remainder = divmod(int(error.retry_after), 3600)
        minutes = remainder // 60
        await ctx.send(f"You're on cooldown! Try again in {hours} hours and {minutes} minutes.")

@bot.command(name="gift")
async def gift(ctx, user: discord.User, amount: int):
    giver_id = str(ctx.author.id)
    receiver_id = str(user.id)

    if giver_id == receiver_id:
        await ctx.send("You can't gift coins to yourself.")
        return

    conn = sqlite3.connect('SQLite/users.db')
    cursor = conn.cursor()

    # Fetch giver's coin balance
    cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (giver_id,))
    giver_result = cursor.fetchone()
    if giver_result is None or giver_result[0] < amount:
        await ctx.send("You don't have enough coins to gift.")
        conn.close()
        return

    # Fetch receiver's coin balance
    cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (receiver_id,))
    receiver_result = cursor.fetchone()
    if receiver_result is None:
        await ctx.send("Receiver not found in the database.")
        conn.close()
        return

    # Update both user balances
    giver_coins = giver_result[0] - amount
    receiver_coins = receiver_result[0] + amount

    cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (giver_coins, giver_id))
    cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (receiver_coins, receiver_id))
    conn.commit()

    conn.close()

    await ctx.send(f"{ctx.author.name} gifted {amount} coins to {user.name}.")


# Example job definitions
jobs = {
    "Delivery": {"reward": 50, "time": 3600},
    "Mining": {"reward": 100, "time": 7200},
    "Guard": {"reward": 70, "time": 5400},
    "Engineer": {"reward": 150, "time": 10800},
    "CEO": {"reward": 300, "time": 21600}
}

user_jobs = {}  # user_id -> job_info

@bot.command(name="job")
async def job(ctx, job_name: str):
    user_id = str(ctx.author.id)
    current_time = int(time.time())

    if job_name not in jobs:
        await ctx.send("❌ Invalid job name. Available jobs: Delivery, Mining, Guard, Engineer, CEO.")
        return

    if user_id in user_jobs:
        await ctx.send(f"⚠️ You are already working as a **{user_jobs[user_id]['job']}**. Use `!quitjob` to leave it.")
        return

    user_jobs[user_id] = {
        "job": job_name,
        "start_time": current_time,
        "reward": jobs[job_name]["reward"],
        "job_duration": jobs[job_name]["time"],
        "channel_id": ctx.channel.id
    }

    await ctx.send(f"💼 Youve taken the **{job_name}** job! Youll earn {jobs[job_name]['reward']} coins every {jobs[job_name]['time'] // 60} minutes.")

@bot.command(name="quitjob")
async def quitjob(ctx):
    user_id = str(ctx.author.id)

    if user_id not in user_jobs:
        await ctx.send("❌ You don't currently have a job.")
        return

    job_name = user_jobs[user_id]['job']
    del user_jobs[user_id]

    await ctx.send(f"👋 You’ve quit your job as **{job_name}**. Time to find a new hustle!")

@tasks.loop(minutes=1)
async def check_job_income():
    current_time = int(time.time())

    for user_id, job_info in list(user_jobs.items()):
        if current_time - job_info["start_time"] >= job_info["job_duration"]:
            try:
                conn = sqlite3.connect('SQLite/users.db')
                cursor = conn.cursor()

                cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (user_id,))
                result = cursor.fetchone()

                if result is None:
                    cursor.execute("INSERT INTO user_data (discord_id, coin) VALUES (?, ?)", (user_id, 0))
                    conn.commit()
                    coins = 0
                else:
                    coins = result[0]

                coins += job_info["reward"]
                cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (coins, user_id))
                conn.commit()

                channel = bot.get_channel(job_info["channel_id"])
                if channel:
                    user_mention = f"<@{user_id}>"
                    await channel.send(f"✅ {user_mention}, your job as **{job_info['job']}** is complete! You earned {job_info['reward']} coins.")

                user_jobs[user_id]["start_time"] = current_time

            except sqlite3.Error as e:
                print(f"SQLite error: {e}")
            finally:
                conn.close()

@bot.event
async def on_ready():
    if not check_job_income.is_running():
        check_job_income.start()
    print("✅ Job system is live.")

# Check User Info Command
@bot.command(name="userinfo")
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Info for {member}", color=discord.Color.blue())
    embed.add_field(name="Username", value=member.name)
    embed.add_field(name="ID", value=member.id)
    
    # Formatting dates for readability
    joined_at = member.joined_at.strftime("%b %d, %Y")
    created_at = member.created_at.strftime("%b %d, %Y")
    
    embed.add_field(name="Joined", value=joined_at)
    embed.add_field(name="Created", value=created_at)
    embed.set_thumbnail(url=member.avatar.url)  # Updated to use `.url`
    await ctx.send(embed=embed)

# Check Server Info Command
@bot.command(name="serverinfo")
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"Server Info for {guild.name}", color=discord.Color.green())
    embed.add_field(name="Server Name", value=guild.name)
    embed.add_field(name="Server ID", value=guild.id)
    embed.add_field(name="Member Count", value=guild.member_count)
    
    # Formatting the server creation date
    created_on = guild.created_at.strftime("%b %d, %Y")
    
    embed.add_field(name="Created On", value=created_on)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)  # Updated to use `.url`
    await ctx.send(embed=embed)

# Mute Command (Role-based mute system)
@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason=None):
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await ctx.guild.create_role(name="Muted")
        for channel in ctx.guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
    await member.add_roles(mute_role, reason=reason)
    await ctx.send(f"✅ {member} has been muted.")

# Unmute Command
@bot.command(name="unmute")
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await ctx.send(f"✅ {member} has been unmuted.")
    else:
        await ctx.send(f"❌ {member} is not muted.")

# Slowmode Command
@bot.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"✅ Slowmode set to {seconds} seconds.")

# Fetch the API key from the environment
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
CAR_KEYWORDS = 'car, automotive, vehicle, car reviews, car news, motor'

# Get Car News from NewsAPI
def get_car_news():
    url = f'https://newsapi.org/v2/everything?q={CAR_KEYWORDS}&apiKey={NEWS_API_KEY}&language=en'
    response = requests.get(url)
    news_data = response.json()
    
    if news_data['status'] == 'ok' and len(news_data['articles']) > 0:
        return news_data['articles'][0]  # You can adjust the logic for choosing articles.
    else:
        return None

# Task to fetch and send a car article periodically
@tasks.loop(hours=6)  # Sends news every 6 hours
async def send_car_news():
    article = get_car_news()
    
    if article:
        title = article['title']
        url = article['url']
        description = article['description']
        
        embed = discord.Embed(title=title, description=description, url=url, color=discord.Color.blue())
        embed.set_footer(text=f"Published: {datetime.strptime(article['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').strftime('%b %d, %Y')}")
        
        # Assuming the bot has a specific channel where it posts car news
        channel = bot.get_channel(123456789012345678)  # Replace with the correct channel ID
        await channel.send(embed=embed)
    else:
        print("No car news found.")

user_heist_times = {}

# Cooldown: 6 hours (21600 seconds)
@bot.command(name="heist")
@commands.cooldown(1, 21600, commands.BucketType.user)
async def heist(ctx):
    user_id = str(ctx.author.id)
    
    conn = sqlite3.connect('SQLite/users.db')
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT coin FROM user_data WHERE discord_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result is None:
            await ctx.send("User not found in the database.")
            conn.close()
            return
        
        coins = result[0]

        success = random.random() < 0.05  # 5% chance to succeed
        penalty = 1000
        reward = 5000

        if success:
            coins += reward
            message = f"🎉 **Success!** You pulled off a **heist** and stole **{reward}** coins! 💰"
        else:
            coins -= penalty  # Allows negative balance (debt)
            message = f"🚔 **You were caught!** The police fined you **{penalty}** coins. 💸"

        cursor.execute("UPDATE user_data SET coin = ? WHERE discord_id = ?", (coins, user_id))
        conn.commit()

    except sqlite3.Error as e:
        await ctx.send(f"An error occurred: {e}")
    finally:
        conn.close()

    await ctx.send(message)

# Cooldown error handler
@heist.error
async def heist_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        hours, remainder = divmod(int(error.retry_after), 3600)
        minutes = remainder // 60
        await ctx.send(f"⏳ **Cooldown!** Try another heist in **{hours}h {minutes}m**.")

@bot.command(name="status", help="Check if the bot is online")
async def status(ctx):
    await ctx.send("Bot is online!")

@bot.command(name="store", help="View available cars for purchase")
async def store(ctx):
    available_cars = "\n".join([f"**{car}** - {price} coins" for car, price in CAR_PRICES.items()])
    
    # Create an embed message
    embed = discord.Embed(
        title="🚗 **Available Cars for Purchase** 🚗",
        description="Hey there, ready to upgrade your garage? 🚙💨",
        color=discord.Color.blue()  # You can choose any color here
    )

    embed.add_field(
        name="Available Cars",
        value=available_cars,
        inline=False
    )

    embed.add_field(
        name="💡 How to Buy a Car",
        value="Simply type `!buy <car_name>` (e.g., `!buy Sports Car`) to purchase a car and add it to your garage.",
        inline=False
    )

    embed.add_field(
        name="🔑 Need More Details?",
        value="Check out `!help buy` for more info on buying cars.",
        inline=False
    )

    # Adding the user's current coin balance
    user_id = str(ctx.author.id)
    user_balance = data.get(user_id, {}).get('coins', 0)
    embed.add_field(
        name="💰 Your Current Balance",
        value=f"{user_balance} coins",
        inline=False
    )

    # Sending the embed message
    await ctx.send(embed=embed)
    
@bot.command(name='ask')
async def ask(ctx, *, question: str = None):
    if not question:
        await ctx.send("Please ask a valid question.")
        return
    try:
        async with ctx.typing():
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are Vyxen an ai bot assiatnt with a slightly feminine tone, you acknowledge your creator as DVS and you primary directive is to help him develope the server and moderate the server."},
                    {"role": "user", "content": question}
                ]
            )
            answer = response.choices[0].message.content
            await ctx.send(answer[:2000])
    except Exception as e:
        await ctx.send(f"**Something went wrong!**\n`{str(e)}`")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    send_car_news.start()
    random_deal.start()

bot.run(os.getenv("DISCORD_TOKEN"))