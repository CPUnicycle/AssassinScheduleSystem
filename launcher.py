import asyncio
import discord
from discord.ext import commands, tasks
import configparser
import logging
import assassin_cog
import model

def launch(config: configparser.ConfigParser):
    logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    game_config = model.AssassinConfig(
        save_path = config['DEFAULT']['SavePath'],
        debug_allow = set(map(int, config['DEFAULT']['DebugAllow'].split(','))),
        channel = int(config['DEFAULT']['AssassinChannel']),
        operator = int(config['DEFAULT']['Operator']),
        bluerole = int(config['DEFAULT']['BlueShellID']),
        playerrole = int(config['DEFAULT']['PlayerID']),
        pauserole = int(config['DEFAULT']['PauseID'])
    )

    bot = commands.Bot(command_prefix='$', intents=intents, case_insensitive=True)
    cog = asyncio.run(assassin_cog.register(bot, game_config))
    bot.run(config['DEFAULT']['ApiKey'], log_handler=None)

    cog.write_state()

