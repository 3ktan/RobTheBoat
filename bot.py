import asyncio
import os
import random
import subprocess
import sys
import time

import aiohttp
import psutil
import pyping
from discord.ext import commands

from utils import checks
from utils.bootstrap import Bootstrap
from utils.buildinfo import *
from utils.channel_logger import Channel_Logger
from utils.config import Config
from utils.logger import log
from utils.mysql import *
from utils.opus_loader import load_opus_lib
from utils.sharding import shard_count
from utils.sharding import shard_id
from utils.tools import *

start_time = time.time()

# Initialize the logger first so the colors and shit are setup
log.init()  # Yes I could just use __init__ but I'm dumb

Bootstrap.run_checks()

config = Config()
if config.debug:
    log.enableDebugging()  # pls no flame
bot = commands.Bot(command_prefix=config.command_prefix,
                   description="A multipurposed bot with a theme for the furry fandom. Contains nsfw, info, weather, music and much more.",
                   shard_id=shard_id, shard_count=shard_count, pm_help=True)
channel_logger = Channel_Logger(bot)
aiosession = aiohttp.ClientSession(loop=bot.loop)
lock_status = config.lock_status

extensions = ["commands.fuckery", "commands.information", "commands.moderation", "commands.configuration",
              "commands.nsfw", "commands.music", "commands.weather", "commands.gw2", "commands.netflix"]

# Thy changelog
change_log = [
    "you'll never see shit"
]


async def _restart_bot():
    await bot.logout()
    subprocess.call([sys.executable, "bot.py"])


async def _shutdown_bot():
    try:
        aiosession.close()
        await bot.cogs["Music"].disconnect_all_voice_clients()
    except:
        pass
    await bot.logout()


async def set_default_status():
    if not config.enable_default_status:
        return
    type = config.default_status_type
    game = config.default_status_name
    try:
        type = discord.Status(type)
    except:
        type = discord.Status.online
    if game is not None:
        if config.default_status_type == "stream":
            if config.default_status_name is None:
                log.critical("If the status type is set to \"stream\" then the default status game must be specified")
                os._exit(1)
            game = discord.Game(name=game, url="http://twitch.tv/robingall2910", type=1)
        else:
            game = discord.Game(name="Shard {} of {} // {} guilds on this shard".format(str(shard_id), str(shard_count),
                                                                                        len(bot.servers)))
        await bot.change_presence(status=type, game=game)
    else:
        await bot.change_presence(status=type)


@bot.event
async def on_resumed():
    log.info("\nResumed connectivity!")


@bot.event
async def on_ready():
    print("\n")
    print("Logged in as:\n{}/{}#{}\n----------".format(bot.user.id, bot.user.name, bot.user.discriminator))
    print("Bot version: {}\nAuthor(s): {}\nCode name: {}\nBuild date: {}".format(BUILD_VERSION, BUILD_AUTHORS,
                                                                                 BUILD_CODENAME, BUILD_DATE))
    log.debug("Debugging enabled!")
    await set_default_status()
    for extension in extensions:
        try:
            bot.load_extension(extension)
        except Exception as e:
            log.error("Failed to load extension {}\n{}: {}".format(extension, type(e).__name__, e))
    if config.enableMal:
        try:
            bot.load_extension("commands.myanimelist")
            log.info("The MyAnimeList module has been enabled!")
        except Exception as e:
            log.error("Failed to load the MyAnimeList module\n{}: {}".format(type(e).__name__, e))
    if config.enableOsu:
        log.info("The osu! module has been enabled in the config!")
    if config._dbots_token:
        log.info("Updating DBots Statistics...")
        r = requests.post("https://bots.discord.pw/api/bots/{}/stats".format(bot.user.id),
                          json={"shard_id": shard_id, "shard_count": shard_count, "server_count": len(bot.servers)},
                          headers={"Authorization": config._dbots_token})
        if r.status_code == 200:
            log.info("Discord Bots Server count updated.")
        elif r.status_code == 401:
            log.error("Woah, unauthorized?")
    if os.path.isdir("data/music"):
        try:
            bot.cogs["Music"].clear_cache()
            log.info("The music cache has been cleared!")
        except:
            log.warning("Failed to clear the music cache!")
    load_opus_lib()


@bot.event
async def on_command_error(error, ctx):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(ctx.channel, discord.abc.PrivateChannel):
        await ctx.channel.send("Command borked. If this is in a PM, do it in the server. Try to report this with "
                               "{}notifydev.".format(config.command_prefix))
        return

    # In case the bot failed to send a message to the channel, the try except pass statement is to prevent another error
    try:
        await ctx.channel.send(error)
    except:
        pass
    log.error("An error occured while executing the command named {}: {}".format(ctx.command.qualified_name, error))


@bot.event
async def on_command(command, ctx):
    if isinstance(ctx.channel, discord.abc.PrivateChannel):
        server = "Private Message"
    else:
        server = "{}/{}".format(ctx.message.guild.id, ctx.message.guild.name)
    print("[{} at {}] [Command] [{}] [{}/{}]: {}".format(time.strftime("%m/%d/%Y"), time.strftime("%I:%M:%S %p %Z"),
                                                         server, ctx.message.author.id, ctx.message.author,
                                                         ctx.message.content))


@bot.event
async def on_message(message):
    if isinstance(message.author, discord.Member):
        if discord.utils.get(message.author.roles, name="Dragon Ignorance"):
            return
    if message.author.bot:
        return
    if message.author.id == 117678528220233731:
        f = open('markovrobin.txt', 'r+')
        f.write(message.clean_content + "\n")
        print("[Markov] Added entry: " + message.clean_content)
    if getblacklistentry(message.author.id) is not None:
        return

    await bot.process_commands(message)


"""
@bot.event
async def on_server_update(before:discord.Server, after:discord.Server):
    if before.name != after.name:
        await channel_logger.mod_log(after, "Server name was changed from `{}` to `{}`".format(before.name, after.name))
    if before.region != after.region:
        await channel_logger.mod_log(after, "Server region was changed from `{}` to `{}`".format(before.region, after.region))
    if before.afk_channel != after.afk_channel:
        await channel_logger.Channel_logg.mod_log(after, "Server afk channel was changed from `{}` to `{}`".format(before.afk_channel.name, after.afk_channel.name))
    if before.afk_timeout != after.afk_timeout:
        await channel_logger.mod_log(after, "Server afk timeout was changed from `{}` seconds to `{}` seconds".format(before.afk_timeout, after.afk_timeout))
    if before.icon != after.icon:
        await channel_logger.mod_log(after, "Server icon was changed from {} to {}".format(before.icon_url, after.icon_url))
    if before.mfa_level != after.mfa_level:
        if after.mfa_level == 0:
            mfa = "enabled"
        else:
            mfa = "disabled"
        await channel_logger.mod_log(after, "Server two-factor authentication requirement has been `{}`".format(mfa))
    if before.verification_level != after.verification_level:
        await channel_logger.mod_log(after, "Server verification level was changed from `{}` to `{}`".format(before.verification_level, after.verification_level))
    if before.owner != after.owner:
        await channel_logger.mod_log(after, "Server ownership was transferred from `{}` to `{}`".format(before.owner, after.owner))
"""


@bot.event
async def on_member_join(member: discord.Member):
    join_message = read_data_entry(member.guild.id, "join-message")
    if join_message is not None:
        join_message = join_message.replace("!USER!", member.mention).replace("!SERVER!", member.guild.name)
    join_leave_channel_id = read_data_entry(member.guild.id, "join-leave-channel")
    if join_leave_channel_id is not None:
        join_leave_channel = discord.utils.get(member.guild.channels, id=join_leave_channel_id)
        if join_leave_channel is None:
            update_data_entry(member.guild.id, "join-leave-channel", None)
    else:
        join_leave_channel = None
    join_role_id = read_data_entry(member.guild.id, "join-role")
    if join_role_id is not None:
        join_role = discord.utils.get(member.guild.roles, id=join_role_id)
        if join_role is None:
            update_data_entry(member.guild.id, "join-role", None)
    else:
        join_role = None
    if join_leave_channel is not None and join_message is not None:
        try:
            await join_leave_channel.send(join_message)
        except:
            pass
    if join_role is not None:
        try:
            await member.add_roles(join_role)
        except:
            pass


@bot.event
async def on_member_remove(member: discord.Member):
    leave_message = read_data_entry(member.guild.id, "leave-message")
    if leave_message is not None:
        leave_message = leave_message.replace("!USER!", member.mention).replace("!SERVER!", member.guild.name)
    join_leave_channel_id = read_data_entry(member.guild.id, "join-leave-channel")
    if join_leave_channel_id is not None:
        join_leave_channel = discord.utils.get(member.guild.channels, id=join_leave_channel_id)
        if join_leave_channel is None:
            update_data_entry(member.guild.id, "join-leave-channel", None)
    else:
        join_leave_channel = None
    if join_leave_channel is not None and leave_message is not None:
        try:
            await join_leave_channel.send(leave_message)
        except:
            pass


@bot.command(hidden=True)
@checks.is_dev()
async def debug(ctx, *, shit: str):
    """This is the part where I make 20,000 typos before I get it right"""
    # "what the fuck is with your variable naming" - EJH2
    # seth seriously what the fuck - Robin
    try:
        rebug = eval(shit)
        if asyncio.iscoroutine(rebug):
            rebug = await rebug
        await ctx.send(py.format(rebug))
    except Exception as damnit:
        await ctx.send(py.format("{}: {}".format(type(damnit).__name__, damnit)))


"""@bot.command(hidden=True, pass_context=True)
@checks.is_dev()
async def eval(ctx, self):
    await bot.say("Eval enabled. Insert the code you want to evaluate. If you don't want to, type `quit` to exit.")
    if death = await bot.wait_for_message(author=ctx.message.author, content=quit):
        return
    else:
        to_the_death = await bot.wait_for_message(author=ctx.message.author)
        try:
            ethan_makes_me_suffer = eval(to_the_death)
            if asyncio.iscoroutine(ethan_makes_me_suffer):
                ethan_makes_me_suffer = await ethan_makes_me_suffer
            await bot.say(py.format(ethan_makes_me_suffer))
        except Exception as why_do_you_do_this_to_me:
            await bot.say(py.format("{}: {}".format(type(why_do_you_do_this_to_me).__name__, why_do_you_do_this_to_me)))
            """


@bot.command(hidden=True)
@checks.is_owner()
async def rename(ctx, *, name: str):
    """Renames the bot"""
    await bot.user.edit(username=name)
    await ctx.send("How dare you change my name to {}".format(name))


@bot.command(hidden=True)
@checks.is_dev()
async def shutdown(ctx):
    """Shuts down the bot"""
    await ctx.send("I'm leaving you, it's over. See me in magistrate court tomorrow for our divorce.")
    log.warning("{} has shut down the bot!".format(ctx.message.author))
    await _shutdown_bot()


@bot.command(hidden=True)
@checks.is_dev()
async def restart(ctx):
    """Restarts the bot"""
    await ctx.send("I'm gonna leave because I'm mad at you, and then I'll come back. See you.")
    log.warning("{} has restarted the bot!".format(ctx.message.author))
    await _restart_bot()


@bot.command(hidden=True)
@checks.is_owner()
async def setavatar(ctx, *, url: str = None):
    """Changes the bot's avatar"""
    if ctx.message.attachments:
        url = ctx.message.attachments[0]["url"]
    elif url is None:
        await ctx.send("u didn't fuken include a url or a picture retardese")
        return
    try:
        with aiohttp.Timeout(10):
            async with aiosession.get(url.strip("<>")) as image:
                await bot.user.edit(avatar=await image.read())
    except Exception as e:
        await ctx.send("Unable to change avatar: {}".format(e))
    await ctx.send(":eyes:")


@bot.command()
async def notifydev(ctx, *, message: str):
    """Sends a message to the developers"""
    if isinstance(ctx.channel, discord.abc.PrivateChannel):
        server = "`Sent via PM, not a server`"
    else:
        server = "`{}` / `{}`".format(ctx.message.server.id, ctx.message.server.name)
    msg = make_message_embed(ctx.message.author, 0xCC0000, message, formatUser=True)
    owner =bot.get_user(config.owner_id)
    await owner.send("New message! The user's ID is `{}` Server: {} Shard: `{}`".format(ctx.message.author.id,
                                                                                        server, str(shard_id)),
                     embed=msg)
    for id in config.dev_ids:
        person = bot.get_user(id)
        await person.send("New message! The user's ID is `{}` Server: {} Shard: `{}`".format(ctx.message.author.id,
                                                                                                  server,
                                                                                                  str(shard_id)),
                          embed=msg)
    await ctx.author.send("Hey, the following message has been sent to the developers: `{}` PS: Yes you idiot, "
                          "this actually does work. I'm not kidding. Be aware lol".format(
                               message))
    await ctx.send("Completed the quest.")


@bot.command(hidden=True)
@checks.is_dev()
async def blacklist(ctx, id: str, *, reason: str):
    """Blacklists a user, BOT OWNER ONLY."""
    await ctx.channel.trigger_typing()
    user = bot.get_user(id)
    if user is None:
        await ctx.send("Can't find anyone with `{}`".format(id))
        return
    if getblacklistentry(id) is not None:
        await ctx.send("`{}` is already blacklisted, stop trying.".format(user))
        return
    blacklistuser(id, user.name, user.discriminator, reason)
    await ctx.send("Ok, blacklisted `{}` Reason: `{}`".format(user, reason))
    try:
        await user.send("You've been blacklisted. We aren't supposed to talk. Sorry. `{}` Reason: `{}`".format(
                                   ctx.message.author, reason))
    except:
        log.debug("Couldn't send a message to a user with an ID of \"{}\"".format(id))
        # await channel_logger.log_to_channel(":warning: `{}` blacklisted `{}`/`{}` Reason: `{}`".format
        # (ctx.message.author, id, user, reason))


@bot.command(hidden=True)
@checks.is_dev()
async def unblacklist(ctx, id: str):
    """Unblacklists a user"""
    entry = getblacklistentry(id)
    user = bot.get_user(id)
    if entry is None:
        await ctx.send("No one's found with the ID of `{}`".format(id))
        return
    try:
        unblacklistuser(id)
    except:
        await ctx.send("Can't find the blacklisted user `{}`".format(id))  # Don't ask pls
        return
    await ctx.send("Gave freedom once more to `{}#{}`".format(entry.get("name"), entry.get("discrim")))
    try:
        await user.send("You're unblacklisted you titty. You were unblacklisted by `{}`".format(
                                   ctx.message.author))
    except:
        log.debug("Can't send msg to \"{}\"".format(id))
        # await channel_logger.log_to_channel(":warning: `{}` unblacklisted `{}`/`{}#{}`".format(ctx.message.author,
        # id, entry.get("name"), entry.get("discrim")))


@bot.command()
async def showblacklist(ctx):
    """Shows the list of users that are blacklisted from the bot"""
    blacklist = getblacklist()
    count = len(blacklist)
    if blacklist == []:
        blacklist = "No blacklisted users! Congratulations."
    else:
        blacklist = "\n".join(blacklist)
    await ctx.send(xl.format("Total blacklisted users: {}\n\n{}".format(count, blacklist)))


@bot.command(hidden=True)
@checks.is_owner()
async def lockstatus(ctx):
    """Toggles the lock on the status"""
    global lock_status
    if lock_status:
        lock_status = False
        await ctx.send("Unlocked.")
    else:
        lock_status = True
        await ctx.send("Locked.")


@bot.command()
async def stream(ctx, *, name: str):
    """Sets the status for the bot stream mode. Advertise your twitch and shit if you'd like."""
    if lock_status:
        await ctx.send("The status is currently locked.")
        return
    await bot.change_presence(game=discord.Game(name=name, type=1, url="https://www.twitch.tv/robingall2910"))
    await ctx.send("Streaming `{}`".format(name))


@bot.command()
async def changestatus(ctx, status: str, *, name: str = None):
    """Changes the bot status to a certain status type and game/name/your shitty advertisement/seth's
    life story/your favorite beyonce lyrics and so on"""
    if lock_status:
        await ctx.send("Status is locked. Don't try.")
        return
    game = None
    if status == "invisible" or status == "offline":
        await ctx.send("You can not use the status type `{}`".format(status))
        return
    try:
        statustype = discord.Status(status)
    except ValueError:
        await ctx.send(
            "`{}` is not a valid status type, valid status types are `online`, `idle`, `do_not_disurb`, and `dnd`".format(
                status))
        return
    if name != "":
        game = discord.Game(name=name)
    await bot.change_presence(game=game, status=statustype)
    if name is not None:
        await ctx.send("Changed game name to `{}` with a(n) `{}` status type".format(name, status))
        # await channel_logger.log_to_channel(":information_source: `{}`/`{}` Changed game name to `{}` with a(n)
        # `{}` status type".format(ctx.message.author.id, ctx.message.author, name, status))
    else:
        await ctx.send("Changed status type to `{}`".format(status))
        # await channel_logger.log_to_channel(":information_source: `{}`/`{}` has changed the status type to
        # `{}`".format(ctx.message.author.id, ctx.message.author, status))


@bot.command(hidden=True)
@checks.is_dev()
async def terminal(ctx, *, command: str):
    """Runs terminal commands and shows the output via a message. Oooh spoopy!"""
    try:
        await ctx.channel.trigger_typing()
        await ctx.send(xl.format(os.popen(command).read()))
    except:
        await ctx.send("I broke.")


@bot.command(hidden=True)
@checks.is_dev()
async def uploadfile(ctx, *, path: str):
    """Uploads any file on the system. What is this hackery?"""
    await ctx.channel.trigger_typing()
    try:
        await ctx.channel.send(file=discord.File(path))
    except FileNotFoundError:
        await ctx.send("File doesn't exist.")


@bot.command()
async def changelog(ctx):
    """The latest changelog"""
    await ctx.send(
        "For command usages and a list of commands go to https://dragonfire.me/robtheboat/info.html or do `{0}help` "
        "(`{0}help command` for a command usage)\n{1}".format(
            bot.command_prefix, diff.format("\n".join(map(str, change_log)))))


@bot.command()
async def version(ctx):
    """Get the bot's current version"""
    await ctx.send("Bot version: {}\nAuthor(s): {}\nCode name: {}\nBuild date: {}".format(BUILD_VERSION, BUILD_AUTHORS,
                                                                                         BUILD_CODENAME, BUILD_DATE))


@bot.command(hidden=True)
@checks.is_dev()
async def dm(ctx, somethingelse: int, *, message: str):
    """DMs a user"""
    user = bot.get_user(somethingelse)
    owner = bot.get_user(config.owner_id)
    msg = make_message_embed(ctx.message.author, 0xE19203, message, formatUser=True)
    try:
        await user.send("You have a new message from the devs!", embed=msg)
        await owner.send(
                               "`{}` has replied to a recent DM with `{}#{}`, an ID of `{}`, and Shard ID `{}`.".format(
                                   ctx.message.author, user.name, user.discriminator, somethingelse, str(shard_id)),
                               embed=make_message_embed(ctx.message.author, 0xCC0000, message))
        for fuck in config.dev_ids:
            xd = bot.get_user(fuck)
            await xd.send("`{}` has replied to a recent DM with `{}#{}` an ID of `{}`, and Shard ID `{}`.".format(
                          ctx.message.author, user.name, user.discriminator, somethingelse, str(shard_id)),
                          embed=make_message_embed(ctx.message.author, 0xCC0000, message))
    except Exception as e:
        await ctx.send("Error: " + str(e))

"""
@bot.command(hidden=True)
@checks.is_dev()
async def wt(ctx, id: str, *, message: str):
    await ctx.send("Sent the message to ID " + id + ".")
    await bot.send_message(discord.Object(id=id), message) # There's no good rw replacement
"""


@bot.command()
async def uptime(ctx):
    """Displays how long the bot has been online for"""
    second = time.time() - start_time
    minute, second = divmod(second, 60)
    hour, minute = divmod(minute, 60)
    day, hour = divmod(hour, 24)
    week, day = divmod(day, 7)
    await ctx.send(
        "I've been online for %d weeks, %d days, %d hours, %d minutes, %d seconds" % (week, day, hour, minute, second))


@bot.command(hidden=True)
@checks.is_dev()
async def reload(ctx, *, extension: str):
    """Reloads an extension"""
    extension = "commands.{}".format(extension)
    if extension in extension:
        await ctx.send("Reloading {}...".format(extension))
        bot.unload_extension(extension)
        bot.load_extension(extension)
        await ctx.send("Reloaded {}!".format(extension))
    else:
        await ctx.send("Extension isn't available.")


@bot.command(hidden=True)
@checks.is_dev()
async def disable(ctx, *, extension: str):
    """Disables an extension"""
    extension = "commands.{}".format(extension)
    if extension in extension:
        await ctx.send("Disabling {}...".format(extension))
        bot.unload_extension(extension)
        await ctx.send("Disabled {}.".format(extension))
    else:
        await ctx.send("Extension isn't available.")


@bot.command(hidden=True)
@checks.is_dev()
async def enable(ctx, *, extension: str):
    """Disables an extension"""
    extension = "commands.{}".format(extension)
    if extension in extension:
        await ctx.send("Loading {}...".format(extension))
        bot.load_extension(extension)
        await ctx.send("Enabled {}.".format(extension))
    else:
        await ctx.send("Extension isn't available.")


@bot.command()
async def joinserver(ctx):
    """Sends the bot's OAuth2 link"""
    await ctx.author.send("Want a link to invite me into your server? Here you go. `http://inv.rtb.dragonfire.me`")


@bot.command()
async def invite(ctx):
    """Sends an invite link to the bot's server"""
    await ctx.author.send("Here's the invite for some bot help: `https://discord.gg/vvAKvaG` "
                          "Report with {}notifydev if there's an issue with the link.".format(
                              bot.command_prefix))


@bot.command()
async def ping(ctx):
    """Pings the bot"""
    pingtime = time.time()
    memes = random.choice(
        ["pinging server...", "hmu on snapchat", "is \"meming\" a thing?", "sometimes I'm scared of furries myself.",
         "You might not understand, but this is gross.", "***0.0 secs***", "hi", "u h h h h h h h h h h h h h",
         "instagram live is lit asf", "SHOW THAT ASS MY NIG",
         "fucking furries...", "fucking maxie", "AAAAAAAAAAAAAAAAAA",
         "why the fuck am I even doing this for you?", "but....", "meh.", "...",
         "Did you really expect something better?", "kek", "I'm killing your dog next time.",
         "Give me a reason to live.", "anyway...", "porn is good.", "I'm edgy.",
         "Damn it seth, why does your internet have to be slow?", "EJ pls.", "Go check out ViralBot today! It's lit.",
         "pink floyd", "how do u feel, how do u feel now, aaaaaaaaaaaaa?", "alan's psychadelic breakfast",
         "Oh.. er.. me flakes.. scrambled eggs.. bacon.. sausages.. tomatoes.. toast.. coffee.. marmalade. I like "
         "marmalade.. yes.. porridge is nice, any cereal.. I like all cereals..",
         "so, how's was trumps bullshit on executive orders?", "don't sign the I-407 in the airport", "hi",
         "hi can i get a  uh h hh h h h ", "stop pinging me", "go away nerd", "i secretly love you", "owo", "uwu",
         "google blobs are the best", "lets keep advertising viralbot more!", "napstabot isn't good :^)"])
    topkek = memes
    pingms = await ctx.send(topkek)
    ping = time.time() - pingtime
    r = pyping.ping('dragonfire.me')
    # await bot.edit_message(pingms, topkek + " // ***{} ms***".format(str(ping)[3:][:3]))
    await pingms.edit(topkek + " // ***{} ms***".format(r.avg_rtt))


@bot.command()
async def website(ctx):
    """Gives the link to the bot docs"""
    await ctx.send(
        "My official website can be found here: https://dragonfire.me/robtheboat/info.html - Please be aware its outdated.")


@bot.command()
async def github(ctx):
    """Gives the link to the github repo"""
    await ctx.send(
        "My official github repo can be found here: https://github.com/robingall2910/RobTheBoat - This is running the ***dragon*** branch.")


@bot.command(hidden=True)
async def sneaky(ctx, *, server: str):
    hax = await discord.utils.get(bot.guilds, name=server).create_invite()
    await ctx.send("here bitch. " + str(hax))


@bot.command(hidden=True)
async def revokesneaky(ctx, *, invite: str):
    await bot.delete_invite(invite)
    await ctx.send("Deleted invite.")


@bot.command(pass_context=True)
async def stats(ctx):
    """Grabs bot statistics."""
    if ctx.message.guild is None:
        SID = shard_id
        musage = psutil.Process().memory_full_info().uss / 1024 ** 2
        uniqueonline = str(sum(1 for m in bot.get_all_members() if m.status != discord.Status.offline))
        sethsfollowers = str(sum(len(s.members) for s in bot.servers))
        sumitup = str(int(len(bot.servers)) * int(shard_count))
        sumupmembers = str(int(str(sethsfollowers)) * int(shard_count))
        sumupuni = str(int(str(uniqueonline)) * int(shard_count))
        em = discord.Embed(description="\u200b", color=ctx.message.guild.me.color)
        em.title = bot.user.name + "'s Help Server"
        em.url = "https://discord.gg/vvAKvaG"
        em.set_thumbnail(url=bot.user.avatar_url)
        # c&p is a good feature
        em.add_field(name='Creators', value='based robin#0052 and Seth#0051', inline=True)
        em.add_field(name='Support Team', value='Skoonk & Xeoda#3835 and Owlotic#0278', inline=True)
        em.add_field(name='Bot Version', value="v{}".format(BUILD_VERSION), inline=True)
        em.add_field(name='Bot Version Codename', value="\"{}\"".format(BUILD_CODENAME))
        em.add_field(name="Build Date", value=BUILD_DATE, inline=True)
        # em.add_field(name='Shard ID', value="Shard " + str(SID), inline=True)
        em.add_field(name='Voice Connections', value=str(len(bot.voice_clients)) + " servers.", inline=True)
        em.add_field(name='Servers', value=sumitup, inline=True)
        em.add_field(name='Members', value=sumupuni + " ***online*** out of " + sumupmembers, inline=True)
        em.add_field(name="Shard Server Count", value=str(len(bot.guilds)), inline=True)
        em.add_field(name='Memory Usage & Shard Number', value='{:.2f} MiB - Shard {}'.format(musage, str(SID)),
                     inline=True)
        await ctx.send(embed=em)
    else:
        SID = shard_id
        musage = psutil.Process().memory_full_info().uss / 1024 ** 2
        uniqueonline = str(sum(1 for m in bot.get_all_members() if m.status != discord.Status.offline))
        sethsfollowers = str(sum(len(s.members) for s in bot.servers))
        sumitup = str(int(len(bot.guilds)) * int(shard_count))
        sumupmembers = str(int(str(sethsfollowers)) * int(shard_count))
        sumupuni = str(int(str(uniqueonline)) * int(shard_count))
        em = discord.Embed(description="\u200b")
        em.title = bot.user.name + "'s Help Server"
        em.url = "https://discord.gg/vvAKvaG"
        em.set_thumbnail(url=bot.user.avatar_url)
        em.add_field(name='Creators', value='based robin#0052 and Seth#0051', inline=True)
        em.add_field(name='Support Team', value='Skoonk & Xeoda#3835 and Owlotic#0278', inline=True)
        em.add_field(name='Bot Version', value="v{}".format(BUILD_VERSION), inline=True)
        em.add_field(name='Bot Version Codename', value="\"{}\"".format(BUILD_CODENAME))
        em.add_field(name="Build Date", value=BUILD_DATE, inline=True)
        # em.add_field(name='Shard ID', value="Shard " + str(SID), inline=True)
        em.add_field(name='Voice Connections', value=str(len(bot.voice_clients)) + " servers.", inline=True)
        em.add_field(name='Servers', value=sumitup, inline=True)
        em.add_field(name='Members', value=sumupuni + " ***online*** out of " + sumupmembers, inline=True)
        em.add_field(name="Shard Server Count", value=str(len(bot.guilds)), inline=True)
        em.add_field(name='Memory Usage & Shard Number', value='{:.2f} MiB - Shard {}'.format(musage, str(SID)),
                     inline=True)
        await ctx.send(embed=em)


bot.run(config._token)