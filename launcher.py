import asyncio
import discord
from discord.ext import commands
import configparser


class TestCog(commands.Cog):
    def __init__(self, bot):
        self.state = 0
        self.bot = bot
    
    @commands.command(name='ping')
    async def ping(self, ctx, *args):
        self.state += 1
        await ctx.send(f'Pong! {self.state}')


async def register_cogs(bot):
    await bot.add_cog(TestCog(bot))


def launch(config: configparser.ConfigParser):
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="$", intents=intents, case_insensitive=True)
    asyncio.run(register_cogs(bot))
    
    bot.run(config['DEFAULT']['ApiKey'])