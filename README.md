# AssassinScheduleSystem
A discord bot for the annual Uni Assassin game played by friends who coincidentally met though the unicycle club found at a polytechnic university in San Luis Obispo, CA.

### Usage/Syntax:
- Join the game by selecting the Player role in #game-control. Leave the game by unselecting the Player role.
- Pause yourself by selecting the Pause role in #game-control. You cannot unpause yourself.
- $points <@tagger> <verb> <@tagee> <Optional proposition> <Optional @colab1> <Optional @colab2> ... <@colabN> - Tell the bot that you tagged someone for points. If you had help from an alliance, give them some credit so they can earn some points too!
- $scores - Print out the scoreboard as a message. This still works, but really just check the pinned scoreboard message instead.
- $help - Print out a list of commands you can use with the bot.
- $stats - Get the statistics for a given player. Not currently functional.

### Definitions:
1. *Blueshelled* - Players who can be tagged even while mounted on a unicycle (as long as the game is active). This is always the player in first, plus some others sometimes.
2. *Academic Building* - Buildings where classes are held. This is different from residential buildings like apartments or dorms
3. *30 Minute Round* - One method of getting an active game. These last from the time the bot notifies players that a round has started, to the time the bot notifies players that the round has ended.
4. *Full Day Round* - The other method of getting an active game. These last from the time the bot notifies players that a round has started, until midnight that night.
5. *Paused* - Take yourself out of the game until midnight. You cannot be tagged, but you also cannot tag, and if you are *blueshelled*, you will not be un*blueshelled*. You cannot unpause yourself.

### Rules:
1. You can only tag another player if you are mounted on a unicycle, and the game is active.
2. You can only be tagged by another player if you are a) not mounted, or b) *Blueshelled*
3. No tags may happen inside *academic buildings*.
4. Unicycle practice and commuting to unicycle practice is a safe zone from *full day rounds* but **NOT** from *30 minute rounds*.
5. Report tags as soon as possible to the bot to allow for proper point bonuses to be awarded.
6. You can only tag the same person once every 30 minutes.
7. If you are tagged, you must count to 10 before you can tag back.
8. After a tag, points are transferred **Immediately**. If that means the tagger is *blueshelled*, that happens whether the bot knows about the tag yet or not. If that means that you are *unblueshelled*, that also takes place immediately. To keep the other players up to date, this means rule 5 is especially important.
9. Paused players cannot be listed as contributors to an alliance. If you attempt this it will count against the bonus points awarded to alliance contributors.

### The Nerdy Details:
1. 30 minute intervals are calculated so the highest probability occurs at 2pm, and the lowest probability occurs at 7am and 9pm. The probability follows a gaussian distribution, with $\mu = 14$ and $\sigma = $ hours. The bot will only go off between 7am and 9pm. The expected value of 30 minute intervals in a given week is around 2.5.
2. 30 minute intervals can happen any minute between hh:40 and hh:00. Ex: 7:40 to 8:00. A 30 minute interval will not happen on a full game day.
3. Full day rounds are selected at the beginning of the week, so there will be one full day round per week. In addition, the first and final days of the game are also full day rounds.
4. Blueshells will be tracked by the bot, and displayed to players in the form of roles in the official Discord server.
5. If two hours of active game time occur with no tags, then the bot starts draining points from any blueshelled players. This is exponential decay towards the highest non-blueshelled player. It won't cause any lead changes, but it will sting if you have a big lead. This drain stops when any player tags any other player.
6. If two hours of active game time occur with no tags, then the bot has a small chance of blueshelling the highest non-blueshelled player every minute. The expected wait time before someone new gets blueshelled is one hour. This then means that points decay towards the new highest non-blueshelled player.
