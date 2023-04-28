import asyncio
import discord
from discord.ext import commands
import configparser
import logging
import assassin_cog
import model


def launch(config: configparser.ConfigParser):
    logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

    intents = discord.Intents.default()
    intents.message_content = True

    game_config = model.AssassinConfig(
        config['DEFAULT']['SavePath'], 
        set(map(int, config['DEFAULT']['DebugAllow'].split(','))),
        int(config['DEFAULT']['AssassinChannel']),
        int(config['DEFAULT']['Operator'])
    )

    bot = commands.Bot(command_prefix="$", intents=intents, case_insensitive=True)
    cog = asyncio.run(assassin_cog.register(bot, game_config))

    bot.run(config['DEFAULT']['ApiKey'], log_handler=None)

    # Perhaps not the best way to store state on shutdown, but better then nothing.
    cog.write_state()