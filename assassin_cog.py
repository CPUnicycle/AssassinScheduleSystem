import datetime
import logging
import pickle
import os.path
import random
import asyncio
import model
import typing
import numpy as np
import discord
import re
from discord.ext import commands, tasks
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

#TODO:
#   - Push to github

# AssBot 2.0
#   Store all players as an object that can be tied to a discord ID - Done
#   Remove $join and replace with just selecting a role - Done
#   Create message and event for the game to start - Done
#   Better random intervals - Done
#   Moving blue shells - Done
#   Weekly leaderboard - Done
#   Interact with Instagram API to post updates

# Updates:
#   Features:
#       Undo/Redo in $debug
#       Randomized messages
#       Website - scoreboard, rules, interaction simulator, statistics, source code
#       Instagram

# Launch List:
#   Change messages back to the ominous/sassy ones - Done
#   Change Icon and Color to iconic - Done
#   Change half hourly update to only weekdays (range(1, 6) - Done
#   Allow random selecting of weekdays again - Done
#   Allow getting bored for only 9, 17, rather than 7, 21 - Done
#   Change moving blueshell probability back to 1 in 60 - Done

TIMEZONE = datetime.timezone(datetime.timedelta(hours=-7))
GAME_START = datetime.date(2024, 4, 1)
GAME_END = datetime.date(2024, 5, 3)
START_MESSAGE = 'Welcome to the San Luis Unicycle Team\'s Quarterly Uni Assassin Competition Kickoff. Good luck and have fun! I\'ll be watching...'
# START_MESSAGE = 'Start message redacted'


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
    async def on_member_update(self, before, after):
        channel = self.bot.get_channel(self._config.channel)
        control_channel = self.bot.get_channel(self._config.controlchan)
        player_role = before.guild.get_role(self._config.playerrole)
        blue_role = before.guild.get_role(self._config.bluerole)
        pause_role = before.guild.get_role(self._config.pauserole)
        name = after.display_name
        
        # When someone changes display name - updates their Player() object, and scoreboard
        if (str(before.display_name) != str(after.display_name)) and \
                (str(before.display_name) in self.gamestate.players):
            self.gamestate.players[name] = model.Player(discID=after.id, name=name, points=self.gamestate.players[before.display_name].points)
            self.gamestate.players.pop(before.display_name)
        # When a blueshell role is taken by a non-player
        if blue_role in after.roles and player_role not in after.roles:
            await after.remove_roles(blue_role)
        # When a pause role is taken by a non-player
        if pause_role in after.roles and player_role not in after.roles:
            await after.remove_roles(pause_role)
        # Make a recon channel for everyone that joins as a player.
        #   Visible to only players, and not the person that just joined
        if player_role not in before.roles and player_role in after.roles:
            shared_with = {
                channel.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                player_role: discord.PermissionOverwrite(read_messages=True),
                after: discord.PermissionOverwrite(read_messages=False)
                }
            await channel.guild.create_text_channel(after.display_name, overwrites=shared_with)
            points = 1 - random.random()*.001
            self.gamestate.players[name] = model.Player(discID=after.id, name=name, points=points)
            await channel.send(f'<@{before.id}> has joined the game as {name}')
        # If a player leaves - remove blueshell and pauses
        elif player_role in before.roles and player_role not in after.roles:
            await before.remove_roles(blue_role)
            await before.remove_roles(pause_role)
            self.gamestate.players.pop(before.display_name)
        # if a player changes their blueshell state
        elif (blue_role in after.roles) != (blue_role in before.roles):
            if (blue_role in after.roles) != self.gamestate.players[name].blueshelled:
                cheater = await before.guild.fetch_member(before.id)
                if self.gamestate.players[name].blueshelled:
                    await cheater.add_roles(blue_role)
                    await channel.send(f'<@{before.id}> tried to remove their blueshell! You\'re a lazy cheater.')
                else:
                    await cheater.remove_roles(blue_role)
                    await channel.send(f'<@{before.id}> tried to *give* themself a blueshell for some reason. Weirdo.')
        # When players pause
        elif (pause_role in after.roles) and (pause_role not in before.roles):
            self.gamestate.players[name].paused = (pause_role in after.roles)
            await channel.send(f'Paused <@{after.id}> until midnight. This cannot be undone.')
        # If someone tries to unpause
        elif (pause_role not in after.roles) and (pause_role in before.roles):
            if self.gamestate.players[name].paused:
                cheater = await after.guild.fetch_member(after.id)
                await cheater.add_roles(pause_role)
                await channel.send(f'<@{after.id}> tried to unpause themself early! You\'re a lazy cheater.>')
        else:
            pass
        # update scoreboard on any of these changes
        scores = await control_channel.fetch_message(self.gamestate.score_msg)
        await scores.edit(content=f'{self.get_leaderboard()}---\n{self.get_weekly_leaderboard()}')

    @commands.command(name='points')
    async def points(self, ctx, tag1, verb, tag2, *args):
        id1 = ''.join(filter(str.isdigit, tag1))
        id2 = ''.join(filter(str.isdigit, tag2))
        mem_1 = await ctx.guild.fetch_member(id1)
        name1 = mem_1.display_name
        mem_2 = await ctx.guild.fetch_member(id2)
        name2 = mem_2.display_name

        first_i = self.get_first_places()
        channel = self.bot.get_channel(self._config.channel)
        control_channel = self.bot.get_channel(self._config.controlchan)
        blue_role = ctx.guild.get_role(self._config.bluerole)
        # Due to cursed statistics implementations - some verbs must be banned
        if verb.__contains__('Statistic') or \
                verb.__contains__('tagger=') or \
                verb.__contains__('person=') or \
                verb.__contains__('verb=') or \
                verb.__contains__('point_i=') or \
                verb.__contains__('point_f=') or \
                verb.__contains__('blueshelled=') or \
                verb.__contains__('on_blueshell=') or \
                verb.__contains__('date=datetime.datetime'):
            await ctx.send('Nope. Can\'t use that word here. Re-enter points.')
            await ctx.send('Forgive me python gods for I have sinned.\n-AJ')
            # These return statements are structural. Break out of points()
            return
        if name1 not in self.gamestate.players or self.gamestate.players[name1].paused:
            await ctx.send(f'{tag1} isn\'t playing at the moment. Shouldn\'t that be you? How did that happen?')
            return
        if name2 not in self.gamestate.players or self.gamestate.players[name2].paused:
            await ctx.send(f'{tag2} doesn\'t seem to be participating. Let\'s avoid terrorizing random students.')
            return
        if name1.lower() == name2.lower():
            await ctx.send('Hey! No free points!')
            return
        valid_tags = []
        penalty = 0
        for word in args:
            try:
                tag = ''.join(filter(str.isdigit, word))
                mem = await ctx.guild.fetch_member(tag)
                name = mem.display_name
            except:
                tag = 'nope'
                name = 'not_player'
            if name in self.gamestate.players:
                if name == name1:
                    await ctx.send('Hey! No free points!')
                elif self.gamestate.players[name].paused:
                    await ctx.send(f'{name} is paused, so they will not be receiving points. They will count towards your team size as a penalty for cheating.')
                    penalty += 1
                else:
                    valid_tags.append(name)
        report_addendum = ''
        for name in valid_tags:
            if self.gamestate.players[name2].points != 0:
                self.gamestate.players[name].points += 1/(len(valid_tags)+1+penalty)
            else:
                self.gamestate.players[name].points += 0.2
            report_addendum += f"{name} now has {self.gamestate.players[name].points:.2f} points!\n"

        pts1 = self.gamestate.players[name1].points
        pts2 = self.gamestate.players[name2].points
        points_calc = 0
        # Hitting someone with more points than you gives 1 + 3/8*difference
        # Hitting someone with less points than you gives you 0.2 or 1 points
        # Getting tagged loses you the larger of 1 point or 1 + 1/8*difference
        if pts1 <= pts2:
            points_calc = 1 + ((pts2-pts1)*0.375)
        else:
            if pts2 == 0:
                points_calc = 0.2
            else: 
                points_calc = 1
        self.gamestate.players[name1].points += points_calc
        self.gamestate.players[name2].points = max(0, self.gamestate.players[name2].points - (1+max(pts2-pts1,0)*0.125))
        if points_calc != 0:
            # Things to do if points were actually scored
            # Reset game clock to 0
            self.gamestate.tag_clock = 0
            # update player data
            # Appends string form of Statistic() to player.stat_list.
            #   A future developer could implement this with tuples and that should work
            #       Lists won't though. Immutable data types only in Player() objects
            self.gamestate.players[name1].stat_list += str(model.Statistic(
                True,
                name2,
                verb,
                pts1,
                self.gamestate.players[name1].points,
                self.gamestate.players[name1].blueshelled,
                self.gamestate.players[name2].blueshelled,
                datetime.datetime.now()
                )
            )
            self.gamestate.players[name2].stat_list += str(model.Statistic(
                False,
                name1,
                verb,
                pts2,
                self.gamestate.players[name2].points,
                self.gamestate.players[name1].blueshelled,
                self.gamestate.players[name2].blueshelled,
                datetime.datetime.now()
                )
            )
            
            # In the case of a lead change, fix blueshells
            # announce fixed blueshells
            first_f = self.get_first_places()
            scores = await control_channel.fetch_message(self.gamestate.score_msg)
            await scores.edit(content=f'{self.get_leaderboard()}---\n{self.get_weekly_leaderboard()}')
            await channel.send(f'Points!\n{name1} now has {self.gamestate.players[name1].points:.2f} points!\n{name2} now has {self.gamestate.players[name2].points:.2f} points!\n'+report_addendum)
            if first_i != first_f:
                for name in first_f:
                    self.gamestate.players[name].blueshelled = True
                    tag = self.gamestate.players[name].discID
                    new_leader = await ctx.guild.fetch_member(tag)
                    await new_leader.add_roles(blue_role)
                    await ctx.send(f'Lead Change!\n<@{tag}> can now be blueshelled!')
            fuck_i = self.is_blueshelled()
            unfuck_i = self.is_not_blueshelled()
            to_save = self.clear_blueshell()
            fuck_f = self.is_blueshelled()
            unfuck_f = self.is_not_blueshelled()
            safe, unsafe = self.blueshell_update(fuck_i, fuck_f, unfuck_i, unfuck_f)
            for message in safe:
                await channel.send(message)
            for person in to_save:
                disc_id = person.discID
                saved = await ctx.guild.fetch_member(disc_id)
                await saved.remove_roles(blue_role)

    # report scores, could be deleted if not used in 2024 game
    @commands.command(name='scores')
    async def scores(self, ctx):
        await ctx.send(self.get_leaderboard() + '---\n' + self.get_weekly_leaderboard()) 

    # reports statistics on either the whole game, or a specific player
    @commands.command(name='stats')
    async def stats(self, ctx, tag=None):
        # omg aj <- A reminder of how bad this ~~used to be~~ is
        if tag is None:
            #most_lost = 0
            loser_dic = {}
            gainer_dic = {}
            much_blueshell_dic = {}
            many_tags_dic = {}
            blueshell_hunter_dic = {}
            jesse_num_dic = {}
            for player in self.gamestate.players:
                times = []
                points = []
                loser_dic.update({player: 0})
                gainer_dic.update({player: 0})
                much_blueshell_dic.update({player: 0})
                many_tags_dic.update({player: 0})
                blueshell_hunter_dic.update({player: 0})
                jesse_num_dic.update({player: 0})
                num_tags = 0.0001
                for stat in self.read_stats(self.gamestate.players[player].stat_list):
                    if stat.point_i - stat.point_f > loser_dic[player]:
                        loser_dic[player] = stat.point_i - stat.point_f
                    if stat.point_f - stat.point_i > gainer_dic[player]:
                        gainer_dic[player] = stat.point_f - stat.point_i
                    if stat.on_blueshell and not stat.tagger:
                        much_blueshell_dic[player] += 1
                    if stat.tagger:
                        many_tags_dic[player] += 1
                        jesse_num_dic[player] += stat.point_f - stat.point_i
                        num_tags += 1
                    if stat.tagger and stat.on_blueshell:
                        blueshell_hunter_dic[player] += 1
                    times.append(matplotlib.dates.date2num(stat.date))
                    points.append(stat.point_f)
                for person in jesse_num_dic:
                    jesse_num_dic[person] = jesse_num_dic[person] / num_tags
                times.append(matplotlib.dates.date2num(datetime.datetime.now()))
                points.append(self.gamestate.players[player].points)
                times.insert(0, matplotlib.dates.date2num(GAME_START))
                points.insert(0, 1)
                plt.plot(times, points, label=player)
            plt.xlabel('Days since start of game')
            plt.ylabel('points')
            plt.legend(bbox_to_anchor=(1.04, 1), loc='upper left')
            plt.savefig('graph.png', bbox_inches='tight')
            loser = max(loser_dic, key=loser_dic.get)
            gainer = max(gainer_dic, key=gainer_dic.get)
            lost_pts = loser_dic[loser]
            gain_pts = gainer_dic[gainer]
            much_blueshell = max(much_blueshell_dic, key=much_blueshell_dic.get)
            many_tags = max(many_tags_dic, key=many_tags_dic.get)
            blueshell_hunter = max(blueshell_hunter_dic, key=blueshell_hunter_dic.get)
            jesse_stat = max(jesse_num_dic, key=jesse_num_dic.get)
            stats_msg = f'The person who lost the most points in one go is {loser}, losing {lost_pts:.2f} points to {gainer}, who gained {gain_pts:.2f} points.\nThe person with the hightest Jesse statistic is {jesse_stat} with {jesse_num_dic[jesse_stat]} points/tag.\nThe person who got hit while blueshelled the most times is {much_blueshell} ({much_blueshell_dic[much_blueshell]} times).\nThe person who tagged the most people is {many_tags} ({many_tags_dic[many_tags]} tags).\nThe person who tagged the most blueshelled players is {blueshell_hunter} ({blueshell_hunter_dic[blueshell_hunter]} tags)'
            await ctx.send(stats_msg, file=discord.File('graph.png'))
        else:
            disc_id = ''.join(filter(str.isdigit, tag))
            mem = await ctx.guild.fetch_member(disc_id)
            name = mem.display_name
            if name in self.gamestate.players:
            # Want stats on:
            #   - number tags
            #   - times tagged
            #   - biggest antagonist
            #   - most common victim
            #   - Jesse Stat
            #   - KDR
            #   - Graphs
                num_tags = 0
                num_tagged = 0
                tagged_by = ''
                tagged_most = ''
                jesse_num = 0
                on_blue_tags = 0
                blueshell_count = 0
                blue_tags = 0
                bad_tags = 0
                statlist = self.read_stats(self.gamestate.players[name].stat_list)
                tags_dic = {}
                tagged_by_dic = {}
                time_tag = []
                for stat in statlist:
                    time_tag.append(stat.date.hour)
                    if stat.tagger:
                        num_tags += 1
                        jesse_num += (stat.point_f - stat.point_i)
                        if stat.person in tags_dic:
                            tags_dic[stat.person] += 1
                        else:
                            tags_dic.update({stat.person: 1})
                        if stat.on_blueshell:
                            on_blue_tags += 1
                        if stat.blueshelled:
                            blue_tags += 1
                    else:
                        num_tagged += 1
                        if stat.person in tagged_by_dic:
                            tagged_by_dic[stat.person] += 1
                        else:
                            tagged_by_dic.update({stat.person: 1})
                        if stat.blueshelled:
                            bad_tags += 1
                        if stat.on_blueshell:
                            blueshell_count += 1
                # you know what? It works. Deal with it.
                jesse_stat = jesse_num / (num_tags+.00001)
                kdr = num_tags / (num_tagged+.00001)
                try: 
                    best_victim = max(tags_dic, key=tags_dic.get) 
                except: 
                    best_victim = 'Nobody, yet...'
                try: 
                    best_antagonist = max(tagged_by_dic, key=tagged_by_dic.get) 
                except: 
                    best_antagonist = 'Nobody, yet...'
                stat_msg = f'Tagged by {best_antagonist} the most\nMost common victim: {best_victim}\nTagged others: {num_tags} times\nGot tagged: {num_tagged} times\nJesse Stat: {jesse_stat:.2f} (avg pts/tag)\nTagged a bluesheller: {on_blue_tags} times\nGot blueshelled: {blueshell_count} times\nTags while blueshelled: {blue_tags} times\nTagged by a bluesheller: {bad_tags} times'
                if len(time_tag) >= 1:
                    plt.hist(time_tag, bins=range(min(time_tag), max(time_tag)+1,1), color='orange')
                    plt.xlabel('Hour of day')
                    plt.ylabel('Number of interactions (tagged or was tagged)')
                    plt.savefig('graph.png')

                    await ctx.send(f'Statistics for {name}:\n-\n{stat_msg}', file=discord.File('graph.png'))
                else:
                    await ctx.send(f'Statistics for {name}:\n-\n{stat_msg}\n-\nDo something interesting and you\'ll get a plot')
            else:
                await ctx.send(f'{name} doesn\'t appear to be playing. ')


    @commands.command(name='help')
    async def help(self, ctx):
        channel = self.bot.get_channel(self._config.channel)
        pause_id = self._config.pauserole
        await ctx.send(f'Here\'s a list of things you can do:\n* $points <name1> verb <name2> with <name3> <name4> | Report a tag!\n* $stats <name> | Show statistics of any player in the game \n* $scores | print scoreboard \n\nYou can join/leave the game in <#1187158394373673071>, or pause.\n\nSelecting the <@&{pause_id}> role will temporarily (but irreversibly) remove you from the game until midnight. You can **not** be unblueshelled if you are paused.')


    # TODO:
    #   - undo game events
    @commands.command(name='debug')
    async def debug(self, ctx, *args):
        blue_role = ctx.guild.get_role(self._config.bluerole)
        player_role = ctx.guild.get_role(self._config.playerrole)
        player_id = self._config.playerrole
        pause_role = ctx.guild.get_role(self._config.pauserole)
        channel = ctx.guild.get_channel(self._config.channel)
        control_channel = ctx.guild.get_channel(self._config.controlchan)
        if ctx.message.author.id not in self._config.debug_allow:
            await ctx.send('You can\'t use that command. Have you tried being someone else?')
        elif not args:
            await ctx.send('Well you *could* send commands. Give me one next time.')
        elif args[0].lower() == 'info':
            for player in self.gamestate.players:
                            await ctx.send('created channel?')
        elif args[0].lower() == 'restart_game':
            if datetime.datetime.now().isoweekday()%7 >= 5:
                chosen_day = random.choice(range(1, 6))
            else: 
                chosen_day = random.choice(range((datetime.datetime.now().isoweekday()%7)+1,6))
            self.gamestate = model.GameState(
                model.CaseInsensitiveDict({}),
                chosen_day
                )
            self.gamestate.game_over = True
            for member in player_role.members:
                # Add each of these players to the game
                name = str(member.display_name)
                points = 1 - random.random()*.001
                self.gamestate.players[name] = model.Player(discID=member.id, name=name, points=points)
                await member.remove_roles(blue_role)
            await ctx.channel.send(START_MESSAGE + f'\n\n<@&{player_id}> I have added you to the game. You can leave by unselecting the <@&{player_id}> role at any time. New players can join the game by selecting the <@&{player_id}> role at any time.\n\nBasic Commands:\n* \'$points <@Player1> tagged <@Player2> with <@Player3> ... <@PlayerN>\' | Report tags to me as soon as possible\n* \'$scores\' | Ask me to print an updated scoreboard\n* \'$help\' | Get a more complete list of commands\n\nImmediately below this message is a pinned scoreboard message (or use \'$scores\', but that\'s kinda annoying).\n\nRules Summary:\n1. If you are mounted on a unicycle and the game is active, you can tag any player who is **not** mounted on a unicycle.\n2. The player in first place is *blueshelled* and can be tagged even if they are on a unicycle.\n3. If the game gets too boring, I will *blueshell* more players until a tag happens.\n4. You can only tag the same person once every 30 minutes.\n5. When you are tagged, you must count to 10 before you can tag back.\n6. I will activate the game once per week, and for 30-minute intervals throughout the week. Tags can only happen while the game is active, and points are transferred **immediately**.\n\nMore rules can be found on [github.com](https://github.com/CPUnicycle/AssassinScheduleSystem) along with source code and more details.')
            scorebrd = await control_channel.send(self.get_leaderboard() + '---\n' + self.get_weekly_leaderboard())
            await scorebrd.pin()
            self.gamestate.score_msg = scorebrd.id
        elif args[0].lower() == 'add_points':
            # Add args[2] points to player args[1]
            try:
                num_pts = float(args[2])
                player_id = ''.join(filter(str.isdigit, args[1]))
                mem = await ctx.guild.fetch_member(player_id)
                name = mem.display_name
            except:
                num_pts = str(args[2])
                name = 'not_player'
            if len(args) < 3 or not (type(num_pts) is float):
                await ctx.send('Usage: \'$debug add_points <person> <points>\'')
            else:
                self.gamestate.players[name].points += num_pts
                await ctx.send(f'{args[1]} has received {args[2]} points. They now have {self.gamestate.players[name].points} points')
                scores = await control_channel.fetch_message(self.gamestate.score_msg)
                await scores.edit(content=f'{self.get_leaderboard()}---\n{self.get_weekly_leaderboard()}')
        elif args[0].lower() == 'set_points':
            # Add args[2] points to player args[1]
            try:
                num_pts = float(args[2])
                player_id = ''.join(filter(str.isdigit, args[1]))
                mem = await ctx.guild.fetch_member(player_id)
                name = mem.display_name
            except:
                num_pts = str(args[2])
                name = 'not_player'
            if len(args) < 3 or not (type(num_pts) is float):
                await ctx.send('Usage: \'$debug set_points <person> <points>\'')
            else:
                self.gamestate.players[name].points = num_pts
                await ctx.send(f'{args[1]} now has {self.gamestate.players[name].points} points')
                scores = await control_channel.fetch_message(self.gamestate.score_msg)
                await scores.edit(content=f'{self.get_leaderboard()}---\n{self.get_weekly_leaderboard()}')
        elif args[0].lower() == 'reset_game':
            if datetime.datetime.now().isoweekday()%7 >= 5:
                chosen_day = random.choice(range(1, 6))
            else: 
                chosen_day = random.choice(range((datetime.datetime.now().isoweekday()%7)+1,6))
            saved_scores = self.gamestate.score_msg
            self.gamestate = model.GameState(
                model.CaseInsensitiveDict({}),
                chosen_day
            )
            self.gamestate.score_msg = saved_scores

            await ctx.send('Game has been reset, all players removed, and a random day was selected\n -')
            for member in player_role.members:
                # Add each of these players to the game
                name = str(member.display_name)
                points = 1 - random.random()*.001
                self.gamestate.players[name] = model.Player(discID=member.id, name=name, points=points)
                await ctx.send(f'<@{member.id}> has joined the game as {name}')

            await ctx.send(START_MESSAGE)
            scores = await control_channel.fetch_message(self.gamestate.score_msg)
            await scores.edit(content=f'{self.get_leaderboard()}---\n{self.get_weekly_leaderboard()}')
            self.gamestate.game_over = True
        elif args[0].lower() == 'randomize_day':
            if datetime.datetime.now().isoweekday()%7 >= 5:
                chosen_day = random.choice(range(1, 6))
            else: 
                chosen_day = random.choice(range((datetime.datetime.now().isoweekday()%7)+1,6))
            self.gamestate.assassin_day = chosen_day
            await ctx.send(f'New day has been selected.')
        elif args[0].lower() == 'unpause':
            try:
                player_id = ''.join(filter(str.isdigit, args[1]))
                mem = await ctx.guild.fetch_member(player_id)
                name = mem.display_name
            except:
                name = 'not_player'
            if len(args) < 2 or name == 'not_player':
                await ctx.send('Usage: \'$unpause <person>')
            elif name in self.gamestate.players:
                unpausee = await ctx.guild.fetch_member(self.gamestate.players[name].discID)
                old = self.gamestate.players[name].paused
                self.gamestate.players[name].paused = False
                new = self.gamestate.players[name].paused
                await unpausee.remove_roles(pause_role)
            else:
                await ctx.send(f'{name} is not playing right now, so they can\'t be unpaused')
        elif args[0].lower() == 'blueshell':
            try:
                player_id = ''.join(filter(str.isdigit, args[1]))
                mem = await ctx.guild.fetch_member(player_id)
                name = mem.display_name
            except:
                name = 'not_player'
            if len(args) < 2 or name == 'not_player':
                await ctx.send('Usage: \'$unpause <person>')
            elif name in self.gamestate.players:
                self.gamestate.players[name].blueshelled = True
                new_shelled = await ctx.guild.fetch_member(player_id)
                await new_shelled.add_roles(blue_role)
            else:
                await ctx.send(f'{name} is not playing right now, so they can\'t be blueshelled')
        elif args[0].lower() == 'unblueshell':
            try:
                player_id = ''.join(filter(str.isdigit, args[1]))
                mem = await ctx.guild.fetch_member(player_id)
                name = mem.display_name
            except:
                name = 'not_player'
            if len(args) < 2 or name == 'not_player':
                await ctx.send('Usage: \'$unpause <person>')
            elif name in self.gamestate.players:
                self.gamestate.players[name].blueshelled = False 
                new_shelled = await ctx.guild.fetch_member(player_id)
                await new_shelled.remove_roles(blue_role)
            else:
                await ctx.send(f'{name} is not playing right now, so they can\'t be unblueshelled')
        elif args[0].lower() == 'set_weekly_points':
            # Add args[2] points to player args[1]
            try:
                num_pts = float(args[2])
                player_id = ''.join(filter(str.isdigit, args[1]))
                mem = await ctx.guild.fetch_member(player_id)
                name = mem.display_name
            except:
                num_pts = str(args[2])
                name = 'not_player'
            if len(args) < 3 or not (type(num_pts) is float):
                await ctx.send('Usage: \'$debug set_points <person> <points>\'')
            else:
                self.gamestate.players[name].week_points = num_pts
                await ctx.send(f'{args[1]} now has {self.gamestate.players[name].week_points} points')
                scores = await control_channel.fetch_message(self.gamestate.score_msg)
                await scores.edit(content=f'{self.get_leaderboard()}---\n{self.get_weekly_leaderboard()}')
        elif args[0].lower() == 'add_weekly_points':
            # Add args[2] points to player args[1]
            try:
                num_pts = float(args[2])
                player_id = ''.join(filter(str.isdigit, args[1]))
                mem = await ctx.guild.fetch_member(player_id)
                name = mem.display_name
            except:
                num_pts = str(args[2])
                name = 'not_player'
            if len(args) < 3 or not (type(num_pts) is float):
                await ctx.send('Usage: \'$debug set_points <person> <points>\'')
            else:
                self.gamestate.players[name].week_points += num_pts
                await ctx.send(f'{args[1]} now has {self.gamestate.players[name].week_points} points')
                scores = await control_channel.fetch_message(self.gamestate.score_msg)
                await scores.edit(content=f'{self.get_leaderboard()}---\n{self.get_weekly_leaderboard()}')
        elif args[0].lower() == 'clear_stats':
            try:
                player_id = ''.join(filter(str.isdigit, args[1]))
                mem = await ctx.guild.fetch_member(player_id)
                name = mem.display_name
            except:
                name = 'not_player'
            if len(args) < 2 or name == 'not_player':
                await ctx.send('Usage: \'$debug clear_stats <person>')
            elif name in self.gamestate.players:
                self.gamestate.players[name].stat_list = ''
                await ctx.send(f'{name}\'s statistics have been reset')
            else:
                await ctx.send(f'{name} is not playing right now, so their stats can\'t be cleared')

        else:
            await ctx.send('I don\'t know what you want from me.')
            

    @tasks.loop(time=datetime.time(0, tzinfo=TIMEZONE))
    async def midnight_update(self):
        channel = self.bot.get_channel(self._config.channel)
        control_channel = self.bot.get_channel(self._config.controlchan)
        player_id = self._config.playerrole
        player_role = channel.guild.get_role(player_id)
        blue_role = channel.guild.get_role(self._config.bluerole)
        pause_role = channel.guild.get_role(self._config.pauserole)
        if datetime.datetime.now().isoweekday() != self.gamestate.assassin_day:
            self.gamestate.day_game_active = False

        # Unpause everyone.
        for player in self.gamestate.players:
            tag = self.gamestate.players[player].discID
            pausee = await channel.guild.fetch_member(tag)
            self.gamestate.players[player].paused = False
            await pausee.remove_roles(pause_role)

        # On Saturday (Friday night), update weekly leaders
        if (datetime.datetime.now().isoweekday() == 6) and not self.gamestate.game_over:
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
            await scores.edit(content=f'{self.get_leaderboard()}---\n{self.get_weekly_leaderboard()}')
            await channel.send("For those who participated this week, you have been rewarded.")

        # On Sunday, select assassin day.
        if datetime.datetime.now().isoweekday() == 7:
            self.gamestate.assassin_day = random.choice(range(1, 6))
            # logging.info(f'Assassin day set for {self.gamestate.assassin_day}')
            # await channel.send('assassin day selected')
            await channel.send('I know what day Uni Assassin will be this week...')
        # On the first day, start the game.
        if (datetime.datetime.now().month == GAME_START.month) and (datetime.datetime.now().day == GAME_START.day):
            if datetime.datetime.now().isoweekday()%7 >= 5:
                chosen_day = random.choice(range(1, 6))
            else: 
                chosen_day = random.choice(range((datetime.datetime.now().isoweekday()%7)+1,6))
            self.gamestate = model.GameState(
                model.CaseInsensitiveDict({}),
                chosen_day
                )
            self.gamestate.game_over = False
            for member in player_role.members:
                # Add each of these players to the game
                name = str(member.display_name)
                points = 1 - random.random()*.001
                self.gamestate.players[name] = model.Player(discID=member.id, name=name, points=points)
                await member.remove_roles(blue_role)
            await channel.send(START_MESSAGE + f'\n\n<@&{player_id}> I have added you to the game. You can leave by unselecting the <@&{player_id}> role at any time. New players can join the game by selecting the <@&{player_id}> role at any time.\n\nBasic Commands:\n* \'$points <@Player1> tagged <@Player2> with <@Player3> ... <@PlayerN>\' | Report tags to me as soon as possible\n* \'$scores\' | Ask me to print an updated scoreboard\n* \'$help\' | Get a more complete list of commands\n\nImmediately below this message is a pinned scoreboard message (or use \'$scores\', but that\'s kinda annoying).\n\nRules Summary:\n1. If you are mounted on a unicycle and the game is active, you can tag any player who is **not** mounted on a unicycle.\n2. The player in first place is *blueshelled* and can be tagged even if they are on a unicycle.\n3. If the game gets too boring, I will *blueshell* more players until a tag happens.\n4. You can only tag the same person once every 30 minutes.\n5. When you are tagged, you must count to 10 before you can tag back.\n6. I will activate the game once per week, and for 30-minute intervals throughout the week. Tags can only happen while the game is active, and points are transferred **immediately**.\n\nMore rules can be found on [github.com](https://github.com/CPUnicycle/AssassinScheduleSystem) along with source code and more details.')
            scorebrd = await control_channel.send(self.get_leaderboard() + '---\n' + self.get_weekly_leaderboard())
            await scorebrd.pin()
            self.gamestate.score_msg = scorebrd.id


    @tasks.loop(time=datetime.time(5, 45, tzinfo=TIMEZONE))
    async def endgame_update(self):
        channel = self.bot.get_channel(self._config.channel)
        player_role = channel.guild.get_role(self._config.playerrole)
        blue_role = channel.guild.get_role(self._config.bluerole)
        if (datetime.datetime.now().month == GAME_END.month) and (datetime.datetime.now().day == GAME_END.day):
            # Send end message and scoreboard.
            name_list = self.get_first_places()
            self.gamestate.day_game_active = False
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
            await channel.send(f'This concludes Uni Assassin {datetime.datetime.now().year}! Here are the final scores:\n\n' + self.get_leaderboard() + f'\n\nI have removed all <@&{self._config.bluerole}> and <@&{self._config.playerrole}> roles. Thanks for playing everyone, and I\'ll be back next year...')
            for member in blue_role.members:
                self.gamestate.players[str(member)].blueshelled = False
                await member.remove_roles(blue_role)
            for member in player_role.members:
                await member.remove_roles(player_role)


    @tasks.loop(time=datetime.time(4, tzinfo=TIMEZONE))
    async def morning_update(self):
        channel = self.bot.get_channel(self._config.channel)
        player_role = self._config.playerrole
        day = self.gamestate.assassin_day
        if (datetime.datetime.now().isoweekday() == day and \
                not self.gamestate.game_over) or \
                (datetime.datetime.now().day == GAME_START.day and \
                datetime.datetime.now().month == GAME_START.month) or \
                (datetime.datetime.now().day == GAME_END.day and \
                datetime.datetime.now().month == GAME_END.month):
            self.gamestate.day_game_active = True
            # await channel.send(f'<@&{player_role}> start full day round')
            await channel.send(f'<@&{player_role}> Prepare yourself! They are coming to get you all day.')


    @tasks.loop(time=[datetime.time(n // 60, n % 60) for n in range(1440)])
    async def half_hourly_update(self, do_round=False):
        current_time = datetime.datetime.now()
        channel = self.bot.get_channel(self._config.channel)
        player_role = self._config.playerrole

        self.write_state()

        if (current_time.hour in range(7, 21)) and \
            (not self.gamestate.game_over) and \
            (current_time.minute in range(40, 60)) and \
            (not self.gamestate.thirty_game_active) and \
            (not self.gamestate.day_game_active) and \
            (current_time.isoweekday() in range(1, 6)) and not \
            (current_time.isoweekday() == 3 and current_time.hour in range(18, 21)):

            x = current_time.hour + ((current_time.minute // 30) / 2)
            time_probability = 0.50 * ((pow(np.e, -0.5 * pow(
            ((x - 14) / 5.6), 2))) / (5.6 * np.sqrt(2 * np.pi)))
            # Was *1 for 2023 = 2/hour, now it's 20/hour
            rand_value = 1 * random.random() * 10

            if (rand_value < time_probability or do_round):
                max_player = max(self.gamestate.players.values(), key=lambda player: player.points)
                logging.info('Starting assassin half hour.')
                self.gamestate.thirty_game_active = True
                # await channel.send(f'<@&{player_role}> start 30 minute round')
                await channel.send(f'<@&{player_role}> Prepare yourself! They are coming to get you for the next half-hour.')


    @tasks.loop(seconds=60)
    async def game_clock(self):
        channel = self.bot.get_channel(self._config.channel)
        control_channel = self.bot.get_channel(self._config.controlchan)
        blue_role = channel.guild.get_role(self._config.bluerole)
        if (self.gamestate.thirty_game_active or self.gamestate.day_game_active) and \
                (not self.gamestate.game_over):
            if self.gamestate.thirty_game_active:
                self.gamestate.thirty_game_clock += 60
            if self.gamestate.thirty_game_clock >= 1800:
                self.gamestate.thirty_game_active = False
                self.gamestate.thirty_game_clock = 0
                # await channel.send('end 30 minute round')
                await channel.send(f'30 minute round is over. You\'re safe for now...')
            if datetime.datetime.now().hour in range(9, 17):
                # Change this back to (9, 17) IRL
                self.gamestate.tag_clock += 60
                # If it goes 2h without a tag, blue shell may move =7200 seconds
                if self.gamestate.tag_clock in range(7200, 7259):
                    # await channel.send('starting move blueshell rolls and points drain')
                    await channel.send("I'm getting bored...")
                if (self.gamestate.tag_clock > 7200) and (self.gamestate.thirty_game_active or self.gamestate.day_game_active):
                    # remove some points from every blueshelled player
                    # Find points of highest non-blueshelled player
                    max_pts = 0
                    for player in self.gamestate.players:
                        if (not self.gamestate.players[player].blueshelled) and (self.gamestate.players[player].points > max_pts):
                            max_pts = self.gamestate.players[player].points
                    for player in self.gamestate.players:
                        if self.gamestate.players[player].blueshelled:
                            init_pts = self.gamestate.players[player].points
                            drained_pts = (init_pts-max_pts)*np.e**(-.005) + max_pts
                            self.gamestate.players[player].points = min(drained_pts, init_pts)
                    scores = await control_channel.fetch_message(self.gamestate.score_msg)
                    await scores.edit(content=f'{self.get_leaderboard()}---\n{self.get_weekly_leaderboard()}')
    
                    # roll die every minute, with an expected wait time of 60m
                    move_shell_die = random.random()
                    print(f'rolling for move blueshell: {move_shell_die}')
                    if move_shell_die < .01667 * 1:
                        shelled = self.move_blueshell()
                        for person in shelled:
                            tag = self.gamestate.players[person].discID
                            new_shelled = await channel.guild.fetch_member(tag)
                            await new_shelled.add_roles(blue_role)
                            # await channel.send(f'<@{tag}> is now blueshelled')
                            await channel.send(f'I got bored. <@{tag}> is now blueshelled. Have fun with that :)')


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
        print(not self.gamestate.game_over)

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
        names = []
        max_pts = name_points[0][1]
        for person in name_points:
            if person[1] == max_pts:
                names.append(person[0])
        return names
    

    def is_blueshelled(self):
        fucked = []
        for player in self.gamestate.players:
            if self.gamestate.players[player].blueshelled:
                fucked.append(player)
        return fucked


    def is_not_blueshelled(self):
        unfucked = []
        for player in self.gamestate.players:
            if not self.gamestate.players[player].blueshelled:
                unfucked.append(player)
        return unfucked


    def blueshell_update(self, fuck_i, fuck_f, unfuck_i, unfuck_f):
        channel = self.bot.get_channel(self._config.channel)
        safe_list = []
        danger_list = []
        for player in list(set(unfuck_f).difference(unfuck_i)):
            tag = self.gamestate.players[player].discID
            safe_list.append(f"<@{tag}> is safe... for now :)")
            # safe_list.append(f'<@{tag}> is no longer blueshelled')
        for player in list(set(fuck_f).difference(fuck_i)):
            tag = self.gamestate.players[player].discID
            danger_list.append(f"Good luck! <@{tag}> is now blueshelled.")
            # danger_list.append(f'<@{tag}> is now blueshelled')
        return safe_list, danger_list


    def move_blueshell(self):
        name_points = [(player.name, player.points, player.blueshelled) for player in self.gamestate.players.values()]
        name_points.sort(key=lambda row: row[1], reverse=True)
        moved_yet = False
        fucked = []
        point_tier = -1
        for person in name_points:
            if person[2]:
                pass
            elif not moved_yet:
                point_tier = person[1]
                moved_yet = True
            if person[1] == point_tier:
                self.gamestate.players[person[0]].blueshelled = True
                fucked.append(person[0])
        return fucked


    def clear_blueshell(self):
        name_points = [(player.name, player.points, player.blueshelled) for player in self.gamestate.players.values()]
        name_points.sort(key=lambda row: row[1], reverse=True)
        max_pts = self.gamestate.players[name_points[0][0]].points
        # Anyone not tied for first gets cleared.
        safe = []
        for person in name_points:
            if person[1] == max_pts or self.gamestate.players[person[0]].paused:
                pass
            else:
                self.gamestate.players[person[0]].blueshelled = False
                safe.append(self.gamestate.players[person[0]])
        return safe

    # OH MY GOD AFTER 3 HOURS OF WORK I REMEMBERED THAT TUPLES EXIST. Thanks Sean!
    def read_stats(self, stat_str):
        stats = stat_str.split('Statistic')
        statlist = []
        for stat in stats:
            if len(str(stat)) >= 1:
                tagger = re.findall('tagger=(.*), person=', stat)[0].__contains__('True')
                person = re.findall('person=(.*), verb=', stat)[0]
                verb = re.findall('verb=(.*), point_i=', stat)[0]
                point_i = float(re.findall('point_i=(.*), point_f=', stat)[0])
                point_f = float(re.findall('point_f=(.*), blueshelled=', stat)[0])
                blueshelled = re.findall('blueshelled=(.*), on_blueshell=', stat)[0].__contains__('True')
                on_blueshell = re.findall('on_blueshell=(.*), date=datetime.datetime\(', stat)[0].__contains__('True')
                time = re.findall('date=datetime.datetime\((.*)\)\)', stat)[0]
                date = datetime.datetime.strptime(time, '%Y, %m, %d, %H, %M, %S, %f')
                statlist.append(model.Statistic(
                    tagger, person, verb, point_i, point_f, blueshelled, on_blueshell, date)
                    )
        return statlist


async def register(bot: commands.Bot, config: model.AssassinConfig):
    cog = AssassinCog(bot, config)
    await bot.add_cog(cog)
    return cog
