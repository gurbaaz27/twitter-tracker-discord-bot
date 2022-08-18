import uuid
import sys
import json
import logging
import requests
import pytz
import locale
from decouple import config
import discord
from discord.ext import commands, tasks
from sqlalchemy import BigInteger, create_engine, Column, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID


locale.setlocale(locale.LC_ALL, "")

headers = {"Authorization": f"Bearer {config('BEARER_TOKEN')}"}
TITLE = "Twitter Tracker 🔎"
TARGET_URL = "https://twitter.com/"
COLOR = discord.Color.blue()
MAX_ALLOWED_LINES = 8
CROP_LENGTH = 25
est = pytz.timezone("US/Eastern")
utc = pytz.utc
fmt = "%Y-%m-%d %H:%M:%S %Z%z"

engine = create_engine(
    config("DATABASE_URL").replace("postgres", "postgresql"), echo=False
)
Base = declarative_base()


class Following(Base):
    __tablename__ = "following"

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    twitter_id = Column("twitter_id", BigInteger)
    name = Column("name", String)
    username = Column("username", String)
    followers = relationship("Follower")


class Follower(Base):
    __tablename__ = "follower"

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    twitter_id = Column("twitter_id", BigInteger)
    following_id = Column(UUID(as_uuid=True), ForeignKey("following.uuid"))
    name = Column("name", String)
    username = Column("username", String)


Base.metadata.create_all(bind=engine)


def init_session():
    Session = sessionmaker(bind=engine)
    session = Session()
    return session


log = logging.getLogger()
log.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)s - %(asctime)s\n%(message)s")
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)
log.addHandler(stdout_handler)
file_handler = logging.FileHandler(f"{config('ENVIRONMENT')}.log")
file_handler.setFormatter(formatter)
log.addHandler(file_handler)


bot = commands.Bot("t.")


async def regular_update(ctx: discord.TextChannel):
    log.info("⚡ regular_update called!")

    try:
        session = init_session()

        log.info("⏰ Daily cycle repeats!")
        #    await ctx.send("⏰ Fetching new information!")
        change = False
        change_list = []

        update_message = (
            "| **{}** |  ─── just followed ─── > | **{}** (https://twitter.com/{}) |"
        )

        log.info("📙 Fetcher function called!")

        TARGET_API = f"https://api.twitter.com/2/users/{config('USER_ID')}/following"

        response = requests.get(TARGET_API, headers=headers)

        if response.status_code != 200:
            log.info("😔 Oh no! There was some error fetching the data.")
            #        await ctx.send(f"""😔 Oh no! There was some error fetching the data. Too many requests!""")
            return

        data = json.loads(response.content)
        log.info(f"Size of following of burner account: {data['meta']['result_count']}")

        # itr = 0

        for entry in data["data"]:
            new_friend = False

            if session.query(
                session.query(Following.uuid)
                .filter(Following.twitter_id == entry["id"])
                .exists()
            ).scalar():
                following = session.query(Following).filter(
                    Following.twitter_id == entry["id"]
                )[0]
                log.info(f"{following.twitter_id} is an old friend")
            else:
                following = Following(
                    twitter_id=entry["id"],
                    name=entry["name"],
                    username=entry["username"],
                )
                session.add(following)
                session.commit()
                log.info(f"{following.twitter_id} new friend added")
                new_friend = True

            # itr += 1
            # if itr==2:
            #     break
            # pagination_token = ""

            # itr = 0

            # while True:
            # if itr == 0:
            #     TARGET_API = f"https://api.twitter.com/2/users/{following.twitter_id}/following"
            # else:
            #     TARGET_API = f"https://api.twitter.com/2/users/{following.twitter_id}/following?pagination_token={pagination_token}"
            # itr += 1

            TARGET_API = (
                f"https://api.twitter.com/2/users/{following.twitter_id}/following"
            )

            try:
                response = requests.get(TARGET_API, headers=headers)
            except Exception as e:
                log.info(str(e))

            if response.status_code != 200:
                log.info("😔 Oh no! There was some error fetching the data.")
                #            await ctx.send(f"""😔 Oh no! There was some error fetching the data. Too many requests!""")
                return

            data_ = json.loads(response.content)

            for d in data_["data"]:
                if session.query(
                    session.query(Follower.uuid)
                    .filter(
                        Follower.twitter_id == d["id"],
                        Follower.following_id == following.uuid,
                    )
                    .exists()
                ).scalar():
                    break
                else:
                    follower = Follower(
                        twitter_id=d["id"],
                        following_id=following.uuid,
                        name=d["name"],
                        username=d["username"],
                    )
                    session.add(follower)
                    session.commit()
                    # log.info("Line 156: Friends new friend")
                    if not new_friend:
                        change = True
                        change_list.append(
                            [
                                following.name,
                                # following.username,
                                follower.name,
                                follower.username,
                            ]
                        )
                # try:
                #     pagination_token = data_["meta"]["next_token"]
                # except:
                #     break

        if change:
            for ch in change_list:
                await ctx.send(
                    "**New Influencer Following!**"
                    + "\n\n"
                    + update_message.format(*ch)
                    + "\n"
                )

    except Exception as e:
        log.info(e)

    finally:
        session.close()


async def update_fetcher(ctx: commands.Context):
    log.info("⚡ update_fetcher called!")

    try:
        session = init_session()

        change = False
        change_list = []

        update_message = (
            "| **{}** |  ─── just followed ─── > | **{}** (https://twitter.com/{}) |"
        )
        no_update_messge = "Calm down bro, I'll tell you when I have news!"

        log.info("📙 Fetcher function called!")

        TARGET_API = f"https://api.twitter.com/2/users/{config('USER_ID')}/following"

        response = requests.get(TARGET_API, headers=headers)

        if response.status_code != 200:
            log.info("😔 Oh no! There was some error fetching the data.")
            #       await ctx.send(f"""😔 Oh no! There was some error fetching the data. Too many requests!""")
            return

        data = json.loads(response.content)
        log.info(f"Size of following of burner account: {data['meta']['result_count']}")

        # itr = 0

        for entry in data["data"]:
            new_friend = False

            if session.query(
                session.query(Following.uuid)
                .filter(Following.twitter_id == entry["id"])
                .exists()
            ).scalar():
                following = session.query(Following).filter(
                    Following.twitter_id == entry["id"]
                )[0]
                log.info(f"{following.twitter_id} is an old friend")
            else:
                following = Following(
                    twitter_id=entry["id"],
                    name=entry["name"],
                    username=entry["username"],
                )
                session.add(following)
                session.commit()
                log.info(f"{following.twitter_id} new friend added")
                new_friend = True

            # itr += 1
            # if itr==2:
            #     break
            # pagination_token = ""

            # itr = 0

            # while True:
            # if itr == 0:
            #     TARGET_API = f"https://api.twitter.com/2/users/{following.twitter_id}/following"
            # else:
            #     TARGET_API = f"https://api.twitter.com/2/users/{following.twitter_id}/following?pagination_token={pagination_token}"
            # itr += 1

            TARGET_API = (
                f"https://api.twitter.com/2/users/{following.twitter_id}/following"
            )

            try:
                response = requests.get(TARGET_API, headers=headers)
            except Exception as e:
                log.info(str(e))

            if response.status_code != 200:
                log.info("😔 Oh no! There was some error fetching the data.")
                #          await ctx.send(f"""😔 Oh no! There was some error fetching the data. Too many requests!""")
                return

            data_ = json.loads(response.content)

            for d in data_["data"]:
                if session.query(
                    session.query(Follower.uuid)
                    .filter(
                        Follower.twitter_id == d["id"],
                        Follower.following_id == following.uuid,
                    )
                    .exists()
                ).scalar():
                    break
                else:
                    follower = Follower(
                        twitter_id=d["id"],
                        following_id=following.uuid,
                        name=d["name"],
                        username=d["username"],
                    )
                    session.add(follower)
                    session.commit()
                    # log.info("Friends new friend")
                    if not new_friend:
                        change = True
                        change_list.append(
                            [
                                following.name,
                                # following.username,
                                follower.name,
                                follower.username,
                            ]
                        )
                # try:
                #     pagination_token = data_["meta"]["next_token"]
                # except:
                #     break

        if not change:
            await ctx.send(no_update_messge)
        else:
            for ch in change_list:
                await ctx.send(
                    "**New Influencer Following!**" + "\n" + update_message.format(*ch)
                )

    except Exception as e:
        log.info(e)

    finally:
        session.close()


@tasks.loop(minutes=30)
async def called_once_every_half_hour():
    log.info("⏰ Daily cycle repeats!")
    ctx: discord.TextChannel = bot.get_channel(int(config("TARGET_CHANNEL_ID")))
    await regular_update(ctx)


@called_once_every_half_hour.before_loop
async def before():
    await bot.wait_until_ready()
    log.info("⌛ Finished waiting")


@bot.event
async def on_ready():
    log.info(f"🚀 {bot.user} is now online!")


@bot.command()
async def about(ctx: commands.Context):
    """About the bot"""
    await ctx.send(
        """Hi! I'm **Twitter Tracker** bot. I fetch latest following updates from twitter for you."""
    )


@bot.command()
async def updatefol(ctx: commands.Context):
    """Fetches the data"""
    log.info("⚡ updatefol command called!")
    await ctx.send("""⌛ Wait a moment...""")
    await update_fetcher(ctx)


called_once_every_half_hour.start()
bot.run(config("TOKEN"))
