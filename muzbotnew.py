import os
import json
import asyncio
from datetime import datetime
import discord
from discord.ext import commands
import yt_dlp as youtube_dl



ROOT = os.path.dirname(__file__)
def get_token(token_name):
    auth_file = open(os.path.join(ROOT, 'auth.json'))
    auth_data = json.load(auth_file)
    token = auth_data[token_name]
    return token

intents = discord.Intents.default()
intents.message_content = True

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_playing = False
        self.is_paused = False
        self.music_queue = []
        self.voice_client = None

        self.ydl_options = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(ROOT, 'yt', '%(extractor)s-%(id)s-%(title)s.%(ext)s'),
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
        }

        self.ffmpeg_options = {
            'options': '-vn'
        }
        self.voice_client = None
    def load_queue(self):
        try:
            with open(os.path.join(ROOT, 'queue.json'), 'r') as queue_file:
                self.music_queue = json.load(queue_file)
        except:
            print('Starting from an empty queue.')

    def save_queue(self):
        with open(os.path.join(ROOT, 'queue.json'), 'w') as queue_file:
            json.dump(self.music_queue, queue_file, indent=4)

    def search_yt(self, item):
        with youtube_dl.YoutubeDL(self.ydl_options) as ydl:
            try:
                info = ydl.extract_info(item, download=True)

                if 'entries' in info:
                    info = info['entries'][0]
                    source = info['formats'][0]['url']
                else:
                    source = info['url']

                filename = ydl.prepare_filename(info)
            except:
                print('Something went wrong.')

        return {
            'source': source,
            'title': info['title'],
            'filename': filename
        }

    def play_next(self):
        if len(self.music_queue) > 0:
            self.is_playing = True
            filepath = self.music_queue[0]['filename']
            self.music_queue.pop(0)
            self.save_queue()

            self.voice_client.play(discord.FFmpegPCMAudio(filepath, **self.ffmpeg_options),
                                after=lambda e: self.play_next())
        else:
            self.is_playing = False

    async def play_music(self, ctx):
        if len(self.music_queue) > 0:
            self.is_playing = True
            channel = ctx.author.voice.channel

            filepath = self.music_queue[0]['filename']
            await ctx.send(f'Now playing: {self.music_queue[0]["title"]}')

            if self.voice_client == None or not self.voice_client.is_connected():
                self.voice_client = await channel.connect()

                if self.voice_client == None:
                    await ctx.send('Could not connect to the voice channel.')
                    return
            else:
                await self.voice_client.move_to(channel)

            self.music_queue.pop(0)
            self.save_queue()
            self.voice_client.play(discord.FFmpegPCMAudio(filepath, **self.ffmpeg_options),
                                after=lambda e: self.play_next())
        else:
            self.is_playing = False


    @commands.hybrid_command(name='play',
                             brief='Plays a song in the voice channel. Usage: !play <song>')
    async def play(self, ctx, *, song):
        channel = ctx.author.voice.channel
        print(f'User is in voice channel: {channel is not None}')

        if channel is None:
            await ctx.send('You\'re not connected to a voice channel.')
        elif self.is_paused:
            print('Resuming playback...')
            self.voice_client.resume()
        else:
            async with ctx.typing():
                print(f'Searching for song: {song}')
                result = self.search_yt(song)
                if type(result) == type(True):
                    print('Oops, something went wrong.')
                    await ctx.send('Oops, something went wrong.')
                else:
                    print(f'Adding {result["title"]} to the queue.')
                    self.music_queue.append(result)
                    self.save_queue()

                if not self.is_playing:
                    print('Starting playback...')
                    await self.play_music(ctx)
                    await asyncio.sleep(1)  # Добавляем задержку
                    print('After awaiting play_music')
                else:
                    await ctx.send(f'Added {result["title"]} to the queue.')

    async def play_music(self, ctx):
        print('Inside play_music method')
        if len(self.music_queue) > 0:
            self.is_playing = True
            filepath = self.music_queue[0]['filename']
            self.music_queue.pop(0)
            self.save_queue()

            print(f'Playing audio from file: {filepath}')

            try:
                self.voice_client.play(discord.FFmpegPCMAudio(filepath, **self.ffmpeg_options),
                                            after=lambda e: asyncio.create_task(self.play_next()))
            except Exception as e:
                print(f'Error playing audio: {e}')

        else:
            self.is_playing = False

    def play_next(self):
        if len(self.music_queue) > 0:
            self.is_playing = True
            filepath = self.music_queue[0]['filename']
            self.music_queue.pop(0)
            self.save_queue()

            self.voice_client.play(discord.FFmpegPCMAudio(filepath, **self.ffmpeg_options), after=lambda e: asyncio.create_task(self.play_next()))
        else:
            self.is_playing = False

    @commands.hybrid_command(name='pause', brief='Pause the currently playing song')
    async def pause(self, ctx):
        if self.is_playing:
            self.is_playing = False
            self.is_paused = True
            self.voice_client.pause()
        elif self.is_paused:
            self.is_paused = False
            self.is_playing = True
            self.voice_client.resume()

        await ctx.send('')

    @commands.hybrid_command(name='resume', brief='Resume the paused song')
    async def resume(self, ctx):
        if self.is_paused:
            self.is_paused = False
            self.is_playing = True
            self.voice_client.resume()
        await ctx.send('')

    @commands.hybrid_command(name='skip', brief='Skips the current song and plays the next one in the queue.')
    async def skip(self, ctx):
        if self.voice_client != None and self.voice_client:
            self.voice_client.stop()
            await self.play_music()
            await ctx.send('')

    @commands.hybrid_command(name='queue', brief='Displays the entire current music playlist.')
    async def queue(self, ctx):
        result = ''
        for q in self.music_queue:
            result += q['title'] + '\n'

        if result != '':
            await ctx.send(result)
        else:
            await ctx.send('Queue is empty.')

    @commands.hybrid_command(name='clear', brief='It forces you to clear the entire music playlist.')
    async def clear_queue(self, ctx):
        if ctx.guild.me.guild_permissions.add_reactions:
            await ctx.message.add_reaction("👍")
        else:
            print("Bot doesn't have permission to add reactions.")

        if self.voice_client is not None and self.is_playing:
            self.voice_client.stop()

        self.music_queue = []
        self.save_queue()

        await ctx.send('Queue cleared.')

    @commands.hybrid_command(name='clearchat',
                            brief='Forces to clear the specified number of messages in the current channel where the command was sent.')
    async def clear_chat(self, ctx, amount: int):
        if "kote" not in ctx.author.name.lower() or "Глава" not in [role.name for role in ctx.author.roles]:
            await ctx.send("You don't have the necessary permissions to use this command.")
            return

        if ctx.author.guild_permissions.manage_messages:
            await ctx.message.delete()
            deleted_messages = await ctx.channel.purge(limit=amount)
            await ctx.send(f'Cleared {len(deleted_messages)} messages.', delete_after=5)
        else:
            await ctx.send("You don't have the necessary permissions to manage messages.")

    @commands.hybrid_command(name='join',
                            brief='Bot enters the current discord channel of the teams author.')
    async def join(self, ctx):
        channel = ctx.author.voice.channel
        print(f'Current voice client status: {self.voice_client}')
        print(f'Attempting to join channel: {channel}')

        try:
            if channel is not None:
                if self.voice_client is None or not self.voice_client.is_connected():
                    print('Connecting to voice channel...')
                    self.voice_client = await channel.connect()
                    await ctx.send(f'Joined {channel.name}')
                    print('Successfully connected to the voice channel.')
                else:
                    await ctx.send('I am already connected to a voice channel.')
                    print('Already connected to a voice channel.')
            else:
                await ctx.send('You are not connected to a voice channel.')
                print('User is not connected to a voice channel.')

        except Exception as e:
            print(f'An error occurred while connecting to the voice channel: {e}')

    @commands.hybrid_command(name='leave', brief='Bot to exit the current discord voice channel.')
    async def leave(self, ctx):
        async with ctx.typing():
            if self.voice_client is not None and self.voice_client.is_connected():
                self.is_playing = False
                self.is_paused = False
                await self.voice_client.disconnect()
                await ctx.send('Left the voice channel.')
            else:
                await ctx.send('I am not connected to a voice channel.')
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or('!'),
    description='A music bot. Prefix ! + command',
    intents=intents)
@bot.event
async def on_member_remove(member):
    guild_id = 292344953911377922
    guild = bot.get_guild(guild_id)
    channel_id = 123456789012345678

    if guild:
        print(f'{member.name} left the server at {datetime.now()}')
        channel = guild.get_channel(channel_id)
        if channel:
            timestamp = datetime.now().strftime("%d.%m.%Y, в %H:%M")
            await channel.send(f'{member.mention} вышел {timestamp}.')
        else:
            print(f'Channel with ID {channel_id} not found.')

@bot.event
async def on_member_join(member):
    guild_id = 292344953911377922
    guild = bot.get_guild(guild_id)
    channel_id = 123456789012345678

    if guild:
        print(f'{member.name} joined the server at {datetime.now()}')
        channel = guild.get_channel(channel_id)
        if channel:
            timestamp = datetime.now().strftime("%d.%m.%Y, в %H:%M")
            await channel.send(f'{member.mention} зашёл {timestamp}.')
        else:
            print(f'Channel with ID {channel_id} not found.')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    # Remove the unnecessary code here

async def on_shutdown():
    print("Bot is shutting down. Cleaning up...")
    await bot.close()

bot.add_listener(on_shutdown, "on_shutdown")

async def main():
    async with bot:
        await bot.add_cog(MusicCog(bot))
        await bot.start(get_token('discord-token'))

if __name__ == "__main__":
    asyncio.run(main())