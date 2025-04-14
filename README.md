# AssassinScheduleSystem
A discord bot for the annual Uni Assassin game played by friends who coincidentally met though the unicycle club CPUC

### Usage/Syntax:
- *Be gentle* - Too many commands too quickly can cause a delay in the bot's response time. 
- Join the game by selecting the Player role in #game-control. Leave the game by unselecting the Player role.
- $points <@tagger> - Tell the bot that you tagged someone for points.
- $help - Print out a list of commands you can use with the bot.
- $stats <@player> - Get the statistics for a given player. Not implemented 

### Rules:
0. If you have the player role, you may tag a runner, whether you react to the message or not. Reacting to the message only puts you in the drawing to be selected for a run.
1. You can only tag another player if you are mounted on a unicycle, and the game is active.
2. Don't ride inside of acedemic buildings. This helps maintain reputation points so we can be a menace outside.
3. Report tags as soon as possible to the bot to allow for proper points to be awarded
4. The game will conclude itself at 5:45pm on the last day: May 16th, 2025.

### The Nerdy Details:
1. 30 minute rounds are calculated so the highest probability occurs at 2pm, and the lowest probability occurs at 7am and 9pm. The bot will only go off between 8:55am and 6pm. The expected value of 30 minute intervals in a given week is around 5.
2. 30 minute intervals can only start on the hh:55. The actual routes and runner will be revealed on the following hh:00.
3. There will be one day per week when the times are announced prior to the run. This day will not be revealed. 
4. Points are calculated by the basic rule of 5 points for a successful run, 2 points for a successful tag, and if the runner is blocked out for their full 30 minutes, all players earn 1 point.
5. New in 2024, your ranking at the end of the week will be used to calculate a cumulative weekly ranking. The last place player earns 0 points, the next highest earns one, then two, and so on. This is the ranking that matters, so play every week!
