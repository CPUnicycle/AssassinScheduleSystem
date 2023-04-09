import asyncio
import discord
from discord.ext import commands
import configparser
import assassin_cog
import logging

def launch(config: configparser.ConfigParser):
    logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="$", intents=intents, case_insensitive=True)
    asyncio.run(assassin_cog.register(bot, config['DEFAULT']['SavePath']))

    bot.run(config['DEFAULT']['ApiKey'], log_handler=None)