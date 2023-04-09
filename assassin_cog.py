from typing import Optional
import datetime
import pickle
import logging
import os.path

import discord
from discord.ext import commands, tasks
import pytz
import numpy as np

import model

TIMEZONE = datetime.timezone(datetime.timedelta(hours=-7))


class AssassinCog(commands.Cog):
    def __init__(self, bot: commands.Bot, save_path: str):
        self.bot = bot
        self.gamestate = model.GameState({}, 0)
        self._save_path = save_path
    
    def cog_unload(self):
        self.midnight_update.cancel()
        self.morning_update.cancel()
        self.half_hourly_update.cancel()
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.midnight_update.start()
        self.morning_update.start()
        self.half_hourly_update.start()
    
    @commands.command(name='join')
    async def join(self, ctx, name: str):
        if not self.gamestate.players:
            points = 1
        else:
            points = max(1, round(
                np.percentile([player.points for player in self.gamestate.players.values()],
                25
            )))
        
        self.gamestate.players[name.lower()] = model.Player(name.lower(), points)
        await ctx.send(f'{name} was added to the leaderboard with {points} point{"s" if points != 1 else ""}')

    

    @tasks.loop(time=datetime.time(0, tzinfo=TIMEZONE))
    async def midnight_update(self):
        pass
    
    @tasks.loop(time=datetime.time(4, tzinfo=TIMEZONE))
    async def morning_update(self):
        pass
    
    @tasks.loop(time=[datetime.time(n // 2, 30 * (n % 2), tzinfo=TIMEZONE) for n in range(48)])
    async def half_hourly_update(self):
        pass

    def try_read_state(self) -> Optional[model.GameState]:
        if not os.path.isdir(self._save_path):
            logging.error(f'Save directory does not exist: {self._save_path}')
            return
        
        try:
            with open(self._save_path + 'state.pickle', 'rb') as pickle_file:
                return pickle.load(pickle_file)

        except pickle.PicklingError:
            logging.warn(f'Could not read pickle file at \'{self._save_path}\'')
        
        return None
    
    def write_state(self):
        if not os.path.isdir(self._save_path):
            logging.error(f'Save directory does not exist: {self._save_path}')
            return

        with open(self._save_path + 'state.pickle', 'wb') as pickle_file:
            pickle.dump(self.gamestate, pickle_file)
        
        with open(self._save_path + 'state_bak.pickle', 'wb') as pickle_file:
            pickle.dump(self.gamestate, pickle_file)
    
    def get_leaderboard():
        name_points = [(player.name, player.points) for player in self.gamestate.players]
        name_points.sort(key=lambda row: row[1], reverse=True)

        message = ""
        for person in name_points:
            message += f"`{person[0].upper() : <10} | {person[1]:>10.2f}`\n"

        return message

        
async def register(bot: commands.Bot, save_path: str):
    await bot.add_cog(AssassinCog(bot, save_path))