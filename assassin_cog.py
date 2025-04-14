import datetime
import re
import logging
import pickle
import os.path
import random
import asyncio
import model
import typing
import numpy as np
import discord
from discord.ext import commands, tasks

## start select full day


### Game 2025
## Don't lose the goals:
# Club visibility (people with swords and unicycles, all over the place)
# Be fun, be adrenaline
## What does game look like? Starting location, ending location, did you get tagged on route?

### RULES
## On the 55, every hour between 8:54 and 17:56 (bell curve), assbot may start a round
## React to the message fast enough and you may be selected to make a run from A to B
    # Store gamestart message
    # Get list of poeple reacted to message
## If a run is successful, runner gets MANY points, if tagged, tagger gets many point, all defenders get *some* points

## Full day: Assbot picks a day and times at the beginning of the week. tell us times
## On that day, those two runs are guaranteed.

### Game run flow:
# in the morning, if it is not game day: pick randomly what times the game will happen
# At every 55, if it was selected, notify the players
# At every 00, if the 55 is running, select a reacted player
# at every 30, calculate points



TIMEZONE = datetime.timezone(datetime.timedelta(hours=-7))
GAME_START = datetime.date(2025, 4, 14)
GAME_END = datetime.date(2025, 5, 16)
START_MESSAGE = 'Welcome to the San Luis Unicycle Team\'s Quarterly Uni Assassin Competition Kickoff. Good luck and have fun! I\'ll be watching...'
#START_MESSAGE = 'Start message redacted'
LOCATIONS = ['architecture building (bottom)',
             'Dexter lawn',
             'UU plaza',
             'YTT lawn',
             'PCV plaza',
             'business building lawn',
             'Baker lawn',
             'the track',
             'North Mountain lawn',
             'Polywall lawn',
             'aglish cow'
             ]

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
        self.game_clock.cancel()
        self.endgame_update.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        self.midnight_update.start()
        self.morning_update.start()
        self.half_hourly_update.start()
        self.game_clock.start()
        self.endgame_update.start()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, react_event):
        runners = list(self.gamestate.players_running)
        if react_event.message_id == self.gamestate.round_msg and \
                self.gamestate.game_waiting:
            if react_event.member.id not in runners and react_event.member.display_name in self.gamestate.players:
                runners.append(react_event.member.id)
        self.gamestate.players_running = tuple(runners)
        print('react added')

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, react_event):
        runners = list(self.gamestate.players_running)
        if react_event.message_id == self.gamestate.round_msg and \
                self.gamestate.game_waiting:
            if react_event.member.id in runners and react_event.member.display_name in self.gamestate.players:
                runners.remove(react_event.member.id)
        self.gamestate.players_running = tuple(runners)
        print('react removed')


    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        channel = self.bot.get_channel(self._config.channel)
        control_channel = self.bot.get_channel(self._config.controlchan)
        player_role = before.guild.get_role(self._config.playerrole)
        name = str(after.display_name)
        
        # When someone changes display name - updates their Player() object, and scoreboard
        if (str(before.display_name) != str(after.display_name)) and \
                (str(before.display_name) in self.gamestate.players):
            self.gamestate.players[name] = model.Player(discID=after.id, name=name, points=self.gamestate.players[before.display_name].points)
            self.gamestate.players.pop(before.display_name)
        # Make a recon channel for everyone that joins as a player.
        #   Visible to only players, and not the person that just joined
        if player_role not in before.roles and player_role in after.roles:
            points = float(0)
            self.gamestate.players[name] = model.Player(discID=after.id, name=name, points=points)
            await channel.send(f'<@{before.id}> has joined the game as {name}')
        elif player_role in before.roles and player_role not in after.roles:
            self.gamestate.players.pop(before.display_name)
        else:
            pass
        # update scoreboard on any of these changes
        scores = await control_channel.fetch_message(self.gamestate.score_msg)
        await scores.edit(content=f'{self.get_leaderboard()}\n---\n{self.get_weekly_leaderboard()}')

    @commands.command(name='points')
    async def points(self, ctx, tag1):
        ### Usage: $points @AJKJ
        channel = self.bot.get_channel(self._config.channel)
        control_channel = self.bot.get_channel(self._config.controlchan)
        if self.gamestate.game_active:
            channel = self.bot.get_channel(self._config.channel)
            player_role = self._config.playerrole
            # case for when points person is not a runner.
            pointser_id = int("".join(re.findall(r"\d", tag1)))
            member = await ctx.guild.fetch_member(pointser_id)
            name = member.display_name
            if name not in self.gamestate.players:
                await ctx.send(f'{name} doesn\'t seem to be playing, let\'s try to avoid chasing random students.')
            if pointser_id != self.gamestate.runner:
                self.gamestate.players[name].points += 2
            if pointser_id == self.gamestate.runner:
                self.gamestate.players[name].points += 5
            self.gamestate.game_active = False
            self.gamestate.game_clock = 0
            await ctx.send('Points have been awarded and the round has ended. Until next time...')
        else:
            await ctx.send('Nope. Not fast enough (or WAY too early)')
        scores = await control_channel.fetch_message(self.gamestate.score_msg)
        await scores.edit(content=f'{self.get_leaderboard()}\n---\n{self.get_weekly_leaderboard()}')



    # reports statistics on either the whole game, or a specific player
    @commands.command(name='stats')
    async def stats(self, ctx, tag=None):
        # omg aj <- A reminder of how bad this ~~used to be~~ is
        pass

    @commands.command(name='help')
    async def help(self, ctx):
        channel = self.bot.get_channel(self._config.channel)
        await ctx.send(f'Here\'s a list of things you can do:\n* $points <name> | Report a tag!\n* $stats <name> | Not implemented. Sorry. \n\nYou can join/leave the game in <#1187158394373673071>')


    # TODO:
    #   - undo game events
    @commands.command(name='debug')
    async def debug(self, ctx, *args):
        pass


    @tasks.loop(time=datetime.time(0, 0, tzinfo=TIMEZONE))
    async def midnight_update(self):
        channel = self.bot.get_channel(self._config.channel)
        control_channel = self.bot.get_channel(self._config.controlchan)
        player_id = self._config.playerrole
        player_role = channel.guild.get_role(player_id)
        if datetime.datetime.now().isoweekday() != self.gamestate.assassin_day:
            pass

        # On Saturday (Friday night), update weekly leaders
        if (datetime.datetime.now().isoweekday() == 5) and not self.gamestate.game_over:
            name_points = [(player.name, player.points) for player in self.gamestate.players.values()]
            name_points.sort(key=lambda row: row[1], reverse=True)
            rank = 1
            prev_pts = 0
            prev_rank = 0
            # first place person gets number of players - rank
            # second place person gets number of players - rank
            # if second == first then person gets 
            for nam_pts in name_points:
                name = nam_pts[0]
                if abs(self.gamestate.players[name].points - prev_pts) < .002:
                    self.gamestate.players[name].week_points += len(name_points) - prev_rank
                else:
                    self.gamestate.players[name].week_points += len(name_points) - rank
                    prev_pts = self.gamestate.players[name].points
                    prev_rank = rank
                rank += 1

            for player in self.gamestate.players:
                self.gamestate.players[player].points = 0

            scores = await control_channel.fetch_message(self.gamestate.score_msg)
            await scores.edit(content=f'{self.get_leaderboard()}\n---\n{self.get_weekly_leaderboard()}')
            await channel.send("For those who participated this week, you have been rewarded!")

        # On the first day, start the game.
        if (datetime.datetime.now().month == GAME_START.month) and (datetime.datetime.now().day == GAME_START.day):
            chosen_day = random.choice(range(1, 6))
            self.gamestate = model.GameState(
                model.CaseInsensitiveDict({}),
                chosen_day
                )
            self.gamestate.game_over = False
            for member in player_role.members:
                # Add each of these players to the game
                name = str(member.display_name)
                points = 0
                self.gamestate.players[name] = model.Player(discID=member.id, name=name, points=points)
            await channel.send(START_MESSAGE + f'\n\n<@&{player_id}> I have added you to the game. You can leave by unselecting the <@&{player_id}> role at any time. New players can join the game by selecting the <@&{player_id}> role at any time.\n\nBasic Commands:\n* \'$points <@Player1> \' | Report tags to me as soon as possible\n* \'$help\' | Get a more complete list of commands\n\nImmediately below this message is a pinned scoreboard message. \n\n Expect some bugs. Just let AJ know with any you find ASAP. \n\nMore rules can be found on [github.com](https://github.com/CPUnicycle/AssassinScheduleSystem) along with source code and more details.')
            scorebrd = await control_channel.send(self.get_leaderboard() + '---\n' + self.get_weekly_leaderboard())
            await scorebrd.pin()
            self.gamestate.score_msg = scorebrd.id
        
        # On Monday (Sunday night) (1), select assassin day.
        if datetime.datetime.now().isoweekday() == 1 and not self.gamestate.game_over:
            self.gamestate.assassin_day = random.choice(range(1, 6))
            # select two random times
            announced_times = [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
            random.shuffle(announced_times)
            self.gamestate.times_selected = (announced_times)
            indexes = [i for i, x in enumerate(announced_times) if x]
            await channel.send(f'Be ready at {indexes[0]+9}:00 and {indexes[1]+9}:00 this week! There will be one day where a run will happen at both these times.')


    @tasks.loop(time=datetime.time(17, 45, tzinfo=TIMEZONE))
    async def endgame_update(self):
        channel = self.bot.get_channel(self._config.channel)
        control_channel = self.bot.get_channel(self._config.controlchan)
        player_role = channel.guild.get_role(self._config.playerrole)
        if (datetime.datetime.now().month == GAME_END.month) and (datetime.datetime.now().day == GAME_END.day):
            # Send end message and scoreboard.
            name_points = [(player.name, player.points) for player in self.gamestate.players.values()]
            name_points.sort(key=lambda row: row[1], reverse=True)
            rank = 1
            prev_pts = None
            prev_rank = None
            for nam_pts in name_points:
                name = nam_pts[0]
                if self.gamestate.players[name].points == prev_pts:
                    self.gamestate.players[name].week_points += len(name_points) - prev_rank
                else:
                    self.gamestate.players[name].week_points += len(name_points) - rank
                prev_rank = rank
                prev_pts = self.gamestate.players[name].points
                rank += 1

            scores = await control_channel.fetch_message(self.gamestate.score_msg)
            await scores.edit(content=f'{self.get_weekly_leaderboard()}')

            name_list = self.get_first_places()
            self.gamestate.thirty_game_active = False
            self.gamestate.game_over = True
            if len(name_list) > 1:
                await channel.send(f'I\'m proud to announce that the {datetime.datetime.now().year} co-S.L.U.T.Q.U.A.C.K.s are:')
                for name in name_list:
                    name_id = self.gamestate.players[name].discID
                    await channel.send(f'<@{name_id}>')
            else:
                name_id = self.gamestate.players[name_list[0]].discID
                await channel.send(f'I\'m proud to announce that the {datetime.datetime.now().year} S.L.U.T.Q.U.A.C.K is <@{name_id}>')
            await channel.send(f'This concludes Uni Assassin {datetime.datetime.now().year}! Here are the final scores:\n\n' + f'{self.get_weekly_leaderboard()}\n\nI have removed all <@&{self._config.playerrole}> roles. Thanks for playing everyone, and I might be back next year...')

            players = player_role.members
            for member in players:
                await member.remove_roles(player_role)


    @tasks.loop(time=datetime.time(4, 0, tzinfo=TIMEZONE))
    async def morning_update(self):
        channel = self.bot.get_channel(self._config.channel)
        player_role = self._config.playerrole
        day = self.gamestate.assassin_day
        prob_thresholds = self.gamestate.time_probabilities
        self.gamestate.today_selected = False
        if datetime.datetime.now().isoweekday() in range(1, 6) and \
                datetime.datetime.now().isoweekday() != day:
            # if it is a fully random day: in the morning roll for what times will be played
            today_times = []
            for i in range (0, 10):
                today_times.append(random.random()*.22 < prob_thresholds[i])
            self.gamestate.temp_times_selected = tuple(today_times)
            self.gamestate.today_selected = True
            print('times selected')

        if datetime.datetime.now() == day:
            self.gamestate.temp_times_selected = self.gamestate.times_selected
            self.gamestate.today_selected = True


    @tasks.loop(time=[datetime.time(n // 60, n % 60) for n in range(1440)])
    async def half_hourly_update(self):
        current_time = datetime.datetime.now()
        channel = self.bot.get_channel(self._config.channel)
        player_role = self._config.playerrole

        # check what hour it is, and translate that to an index to check against
        # if self.gamestate.today_selected and current_time.hour in range(8, 18) and current_time.minute == 55:
        if current_time.minute == 55:
            if self.gamestate.temp_times_selected[current_time.hour-8]:
                current_game_msg = await channel.send(f'<@&{player_role}> Prepare yourself! React to this message if you want to earn a LOT of points in 5 minutes!')
                self.gamestate.round_msg = current_game_msg.id
                self.gamestate.game_waiting = True
            else:
                self.gamestate.round_msg = 0
        self.write_state()



    @tasks.loop(seconds=60)
    async def game_clock(self):
        print('waiting/running')
        channel = self.bot.get_channel(self._config.channel)
        control_channel = self.bot.get_channel(self._config.controlchan)
        if (self.gamestate.game_active) and (not self.gamestate.game_over):
            if self.gamestate.game_active:
                self.gamestate.game_clock += 60
            if self.gamestate.game_clock >= 1860:
                self.gamestate.game_active = False
                self.gamestate.game_clock = 0
                for player in self.gamestate.players:
                    self.gamestate.players[player].points += 1
                member = await channel.guild.fetch_member(self.gamestate.runner)
                name = member.display_name
                self.gamestate.players[name].points = max(0, self.gamestate.players[name].points - 1)
                await channel.send(f'Good job defending! All defenders earned one point!')
                scores = await control_channel.fetch_message(self.gamestate.score_msg)
                await scores.edit(content=f'{self.get_leaderboard()}\n---\n{self.get_weekly_leaderboard()}')

        if self.gamestate.game_waiting and (not self.gamestate.game_over):
            if self.gamestate.game_waiting:
                self.gamestate.wait_clock += 60
            if self.gamestate.wait_clock >= 300:
                self.gamestate.game_waiting = False
                self.gamestate.wait_clock = 0
                self.gamestate.game_active = True
                a_to_b = random.sample(LOCATIONS, k=2)
                if self.gamestate.players_running == ():
                    await channel.send('Y\'all need to stop slacking and earn some points!')
                    self.gamestate.game_active = False
                    self.gamestate.game_clock = 0
                else:
                    runner = random.choice(self.gamestate.players_running)
                    self.gamestate.runner = runner
                    await channel.send(f'<@{runner}> must make it from {a_to_b[0]} to {a_to_b[1]} without being caught. Good luck!')
                self.gamestate.players_running = ()


    def try_read_state(self) -> typing.Union[model.GameState, None]:
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
            message += f"`{person[0].upper() : <15} | {person[1]:>10.2f}`\n"
        return message


    def get_weekly_leaderboard(self):
        name_points = [(player.name, player.week_points) for player in self.gamestate.players.values()]
        name_points.sort(key=lambda row: row[1], reverse=True)
        message = "Weekly Leaderboard:\n"
        for person in name_points:
            message += f"`{person[0].upper() : <15} | {person[1]:>10.2f}`\n"
        return message
    
    
    def get_first_places(self):
        name_points = [(player.name, player.points) for player in self.gamestate.players.values()]
        name_points.sort(key=lambda row: row[1], reverse=True)
        if name_points == []:
            return []
        names = []
        max_pts = name_points[0][1]
        for person in name_points:
            if person[1] == max_pts:
                names.append(person[0])
        return names

    def get_second_places(self):
        name_points = [(player.name, player.points) for player in self.gamestate.players.values()]
        name_points.sort(key=lambda row: row[1], reverse=True)
        names = []
        max_pts = name_points[0][1]
        second_points = []
        for person in name_points:
            if person[1] != max_pts:
                second_points.append(person)
        if second_points == []:
            return []
        seconds = []
        max_pts = second_points[0][1]
        for person in second_points:
            if person[1] == max_pts:
                seconds.append(person[0])
        return seconds
        # throw out anyone who has max_pts. 
        # recalculate max_pts
        # return people who have equal to that max_pts

    def get_third_places(self):
        name_points = [(player.name, player.points) for player in self.gamestate.players.values()]
        name_points.sort(key=lambda row: row[1], reverse=True)
        names = []
        max_pts = name_points[0][1]
        second_points = []
        for person in name_points:
            if person[1] != max_pts:
                second_points.append(person)
        if second_points == []:
            return []
        seconds = []
        max_pts = second_points[0][1]
        for person in second_points:
            if person[1] != max_pts:
                seconds.append(person)
        max_pts = seconds[0][1]
        thirds = []
        for person in seconds:
            if person[1] == max_pts:
                thirds.append(person[0])
        return thirds
        

    # OH MY GOD AFTER 3 HOURS OF WORK I REMEMBERED THAT TUPLES EXIST. Thanks Sean!
    def read_stats(self, stat_tup):
        pass


async def register(bot: commands.Bot, config: model.AssassinConfig):
    cog = AssassinCog(bot, config)
    await bot.add_cog(cog)
    return cog
