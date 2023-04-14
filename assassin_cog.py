import datetime
import logging
import os.path
import pickle
import random
from typing import Optional

import discord
from discord.ext import commands, tasks
import numpy as np
import pytz

import model

TIMEZONE = datetime.timezone(datetime.timedelta(hours=-7))
START_MESSAGE = "Welcome to the San Luis Unicycle Team's Spring Quarter Uni Assassin Competition Kickoff. Good luck and have fun!"


class AssassinCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: model.AssassinConfig):
        self.bot = bot
        self._config = config

        self.gamestate = self.try_read_state()
        if self.gamestate is None:
            self.gamestate = model.GameState(model.CaseInsensitiveDict(dict()), 0)
        else:
            logging.info('State recovered on startup.')
        
        self.bot.remove_command('help')

    
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
    async def join(self, ctx, name):
        if not self.gamestate.players:
            points = 1
        else:
            points = max(1, round(
                np.percentile([player.points for player in self.gamestate.players.values()],
                25
            )))

        self.gamestate.players[name] = model.Player(name, points)
        await ctx.send(f'{name} was added to the leaderboard with {points} point{"s" if points != 1 else ""}')


    @commands.command(name='join_dont_abuse')
    async def join_dont_abuse(self, ctx, name, points):
        if not points.isdigit():
            await ctx.send(f'Points must be a non-negative number.')
        
        points = int(points)

        if name in self.gamestate.players:
            await ctx.send(f'{name} is already on the leaderboard.')

        elif points < 0:
            await ctx.send('Why do you want negative points? Pick a positive number (or zero).')

        else:
            self.gamestate.players[name] = model.Player(name, points)
            await ctx.send(f'CUSTOM: {name} was added to the leaderboard with {points} point{"s" if points > 1 else ""}')


    @commands.command(name='pause')
    async def pause(self, ctx, name):
        if name not in self.gamestate.players:
            await ctx.send(f'It looks like {name} isn\'t currently on the leaderboard, so they can\'t pause their game.')

        else:
            self.gamestate.players[name].paused = True
            await ctx.send(f'{name} will not be participating in uni assassin today. They will be elegible to gain/lose points again at midnight')
    

    @commands.command(name='remove')
    async def remove(self, ctx, name):
        if name not in self.gamestate.players:
            await ctx.send(f'{name} doesn\'t seem to be participating so they couldn\'t be removed.')

        else:
            self.gamestate.players.pop(name)
            await ctx.send(f'Removed {name} from the leaderboard.')


    @commands.command(name='points')
    async def points(self, ctx, name1, verb, name2):
        if name1 not in self.gamestate.players or self.gamestate.players[name1].paused:
            await ctx.send(f'{name1} doesn\'t seem to be participating? That\'s probably your name. How did that happen?')
            return

        if name2 not in self.gamestate.players or self.gamestate.players[name2].paused:
            await ctx.send(f'{name2} doesn\'t seem to be participating? That\'s probably your name. How did that happen?')
            return

        if name1.lower() == name2.lower():
            await ctx.send('Hey! No free points!')
            return
        
        pts1 = self.gamestate.players[name1].points
        pts2 = self.gamestate.players[name2].points
        

        # hitting someone with more points (or equal to) than you gives you 1 + half the difference
        # hitting someone with less points than you gives you the ratio of your points divided by their points
        if pts1 <= pts2:
            point_calc = 1 + (pts2 - pts1) * 0.5
        else:
            point_calc = max(pts2/pts1, 0.2)
        
        self.gamestate.players[name1].points += point_calc

        # when you get hit by someone lower than you, you lose one point
        # when you get hit by someone higher than you, you lose the ratio of your points divided by their points, or .2
        if pts1 <= pts2:
            pts_lost = 1
        else:
            pts_lost = max(pts2/pts1, .2)

        self.gamestate.players[name2].points = max(
            0, self.gamestate.players[name2].points - pts_lost)

        await ctx.send(self.get_leaderboard())
    

    @commands.command(name='scores')
    async def scores(self, ctx):
        await ctx.send(self.get_leaderboard())
    

    @commands.command(name='stats')
    async def stats(self, ctx):
        # omg aj
        pass


    @commands.command(name='help')
    async def help(self, ctx):
        await ctx.send("Here's a list of things you can do:\n$join <name> | Add participants to the game\n$points <name1> got/tagged/hit <name2> | Earn some points by stealing them from someone else!\n$pause <name> | Temporarily stop yourself (or someone else) from earning or losing points\n$remove <name> | Remove yourself (or someone else) from the game entirely\n$stats <name> | Show statistics of any player in the game (runs slowly)\n$scores | print scoreboard without making any changes to the points in the game")


    @commands.command(name='debug')
    async def debug(self, ctx, *args):
        if ctx.message.author.id not in self._config.debug_allow:
            await ctx.send('Sorry, but you cannot access debug commands. :(')
            return
        
        if not args:
            await ctx.send('Congratulations, you can run debug commands. Now give me a command next time.')
            return
        
        if args[0] == 'info':
            await ctx.send(f'Players: {repr(self.gamestate.players)}\nRandom day: [REDACTED]')
            return
        
        # Add a non-negative integer of points.
        if args[0] == 'add_points':
            if len(args) < 3 or not args[2].isdigit():
                await ctx.send('Usage: `$debug add_points <player> <points>`')
                return
            
            name = args[1]
            if name not in self.gamestate.players:
                await ctx.send(f'Player \'{name}\' not found.')
                return
            
            self.gamestate.players[name].points += int(args[2])
            await ctx.send(f'Added {args[2]} points to \'{name}\'')
            return
        
        # Set points to a non-negative integer.
        if args[0] == 'set_points':
            if len(args) < 3 or not args[2].isdigit():
                await ctx.send('Usage: `$debug set_points <player> <points>`')
                return
            
            name = args[1]
            if name not in self.gamestate.players:
                await ctx.send(f'Player \'{name}\' not found.')
                return
            
            self.gamestate.players[name].points = int(args[2])
            await ctx.send(f'Set points to be {args[2]} for \'{name}\'')
            return
        
        # Goofy secret funny code. (ples dont remove, aj) <- OK <- Thank you
        if args[0] == 'lenny':
            await ctx.send('( ͡° ͜ʖ ͡°)')
            return
        

        if args[0] == 'reset_game':
            self.gamestate = model.GameState(
                model.CaseInsensitiveDict({}), 
                random.choice([1, 2, 3, 4, 5]))
            await ctx.send("Game has been reset, all scores and players cleared, and a new random day has been selected.")
            await ctx.send(START_MESSAGE)
            return
        
        if args[0] == 'scare':
            channel = self.bot.get_channel(self._config.channel)
            await channel.send('Hello, I am a bot')
            return

        if args[0] == 'randomize_day':
            self.gamestate.assassin_day = random.choice([1, 2, 3, 4, 5])
            await ctx.send('Random day has been set.')
            logging.info(f'Random day has been manually randomized to: {self.gamestate.assassin_day}')
            return
        
        await ctx.send(f'Unrecognized debug command: {args[1]}')

     
    @tasks.loop(time=datetime.time(0, 0, tzinfo=TIMEZONE))
    async def midnight_update(self):
        channel = self.bot.get_channel(self._config.channel)

        # Unpause everyone.
        for player in self.gamestate.players:
            if self.gamestate.players[player].paused:
                await channel.send(f'{player.capitalize()} is back in the game!')
            self.gamestate.players[player].paused = False

        # On Sunday, select assassin day.
        if datetime.datetime.now(TIMEZONE).isoweekday() == 7:
            self.gamestate.assassin_day = random.choice([1, 2, 3, 4, 5])
            logging.info(f'Assassin day set for {self.gamestate.assassin_day}')
            await channel.send('I know what day Uni Assassin will be this week...')
    

    @tasks.loop(time=datetime.time(4, tzinfo=TIMEZONE))
    async def morning_update(self):
        channel = self.bot.get_channel(self._config.channel)

        if datetime.datetime.now(TIMEZONE).isoweekday() == self.gamestate.assassin_day:
            await channel.send('<@&1091978707406704682> Prepare yourself! They are coming to get you all day.')


    @tasks.loop(time=[datetime.time(n // 2, 30 * (n % 2), tzinfo=TIMEZONE) for n in range(48)])
    async def half_hourly_update(self):
        channel = self.bot.get_channel(self._config.channel)
        current_time = datetime.datetime.now(TIMEZONE)

        self.write_state()

        if (current_time.hour in range(7, 21)) and \
            (current_time.isoweekday() in range(1, 6)) and \
            (current_time.isoweekday() != self.gamestate.assassin_day) and not \
            (current_time.isoweekday() == 1 and current_time.hour in range(18, 21)):

            x = current_time.hour + ((current_time.minute // 30) / 2)
            time_probability = 0.50 * ((pow(np.e, -0.5 * pow(
            ((x - 14) / 5.6), 2))) / (5.6 * np.sqrt(2 * np.pi)))
            rand_value = random.random()

            logging.info(f'Rolling for assassin half hour: Needed->{time_probability} Got->{rand_value}')
            if (rand_value < time_probability):
                logging.info('Starting assassin hald hour.')
                await channel.send("<@&1091978707406704682> Prepare yourself! They are coming to get you for the next half-hour.")


    def try_read_state(self) -> Optional[model.GameState]:
        if not os.path.isfile(self._config.save_path + 'state.pickle'):
            logging.error(f'Save file does not exist: {self._config.save_path}')
            return
        
        try:
            with open(self._config.save_path + 'state.pickle', 'rb') as pickle_file:
                return pickle.load(pickle_file)

        except pickle.PicklingError:
            logging.warn(f'Could not read pickle file at \'{self._config.save_path}\'')
        
        return None

 
    def write_state(self):
        if not os.path.isdir(self._config.save_path):
            logging.error(f'Save directory does not exist: {self._config.save_path}')
            return
        
        logging.info('State saved.')

        with open(self._config.save_path + 'state.pickle', 'wb') as pickle_file:
            pickle.dump(self.gamestate, pickle_file)
        
        with open(self._config.save_path + 'state_bak.pickle', 'wb') as pickle_file:
            pickle.dump(self.gamestate, pickle_file)
    

    def get_leaderboard(self):
        name_points = [(player.name, player.points) for player in self.gamestate.players.values()]
        name_points.sort(key=lambda row: row[1], reverse=True)

        message = "Leaderboard:\n"
        for person in name_points:
            message += f"`{person[0].upper() : <10} | {person[1]:>10.2f}`\n"

        return message


async def register(bot: commands.Bot, config: model.AssassinConfig):
    cog = AssassinCog(bot, config)
    await bot.add_cog(cog)
    return cog