import json
import discord
from discord import app_commands
import asyncio
import random
import requests

import userManager

# CONSTS
GAME_SETTINGS = {}

client = discord.Client(intents=discord.Intents.all())
tree_cls = app_commands.CommandTree(client)

## DISCORD UTIL

def create_embed(
        title=None, 
        description=None, 
        color=discord.Colour.red(), fields=None, 
        thumbnail_url=None, 
        image_url=None, 
        author_name=None, 
        author_url=None, 
        author_icon_url=None, 
        footer_text="Made by DrTranzoc | @honorais\n", 
        footer_icon_url=None, 
        timestamp=None): 
    
    embed = discord.Embed(title=title, description=description, color=color, timestamp=timestamp)
    
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    
    if image_url:
        embed.set_image(url=image_url)
    
    if author_name or author_url or author_icon_url:
        embed.set_author(name=author_name, url=author_url, icon_url=author_icon_url)
    
    if footer_text or footer_icon_url:
        embed.set_footer(text=footer_text, icon_url=footer_icon_url)
    
    return embed

async def check_role(interaction: discord.Interaction, required_role: str) -> bool:
    if required_role not in [role.name for role in interaction.user.roles]:
        return False
    return True

##################

def simulate_battle(players : dict):
    response : str = get_ai_simulated_battle(players)

    outcome = response["reply"]

    start_winner_idx = outcome.index(":") + 1
    end_winner_idx = outcome.index("|Recap|")

    winner = outcome[start_winner_idx:end_winner_idx]
    recap = outcome[end_winner_idx + 8:]

    survivors = [player for player in players.keys() if players[player]["default_nft"]["attributes"]["title"] == winner]
    eliminated = [player for player in players.keys() if player not in survivors]

    return survivors,  eliminated , recap

def get_ai_simulated_battle(players : dict):

    data = {
        'collectionAddress': GAME_SETTINGS["collectionAddress"],
        'BattlingNFTs': [player["default_nft"]["token_id"] for player in players.values()]
    }

    response : dict = requests.post(GAME_SETTINGS["oracleEndpoint"], data=json.dumps(data)).json()

    return response

## COMMANDS

@tree_cls.command(name='honorais-my-balance', description="Retrieve the balances of the asking user")
async def get_user_balance(interaction: discord.Interaction):

    token = interaction.data['options'][0]['value'] if 'options' in interaction.data and len(interaction.data['options']) > 0 else "any"
    user : discord.Member = interaction.user

    # GET BALANCE
    balance = userManager.get_balance(user.id , token)

    if balance == -1:
        await interaction.response.send_message(embed=create_embed(
            description="You are yet not honorable enough to have any of that...disappointing" , 
            color=discord.Colour.red()) , 
            ephemeral=True)
    else:
        if type(balance) == int:
            await interaction.response.send_message(embed=create_embed(
                title="USER BALANCE",
                description=f"You own {balance} ${token}", 
                color=discord.Colour.green()))
        else:
            balance_message = f"{user.mention} owns :\n"
            for token in balance.keys():
                balance_message += f"\n**{balance[token]}** ${token}"
            
            await interaction.response.send_message(embed=create_embed(
                title=f"{user.name} BALANCE",
                description=balance_message, 
                color=discord.Colour.green()))

## COMMANDS
@tree_cls.command(name='honorais-change-balance', description="Give or remove tokens from user")
async def change_user_balance(interaction: discord.Interaction):
    # Only specific people can use the command
    authorized = await check_role(interaction, GAME_SETTINGS["adminRoleName"])
    if not authorized:
        await interaction.response.send_message(embed=create_embed(
            description="You are **not** authorized to use this command." , 
            color=discord.Colour.red()) , 
            ephemeral=True)
        return

    try:
        user = interaction.guild.get_member(int(interaction.data['options'][0]['value']))
        amount : int = interaction.data['options'][1]['value']
        token : str = interaction.data['options'][2]['value'] if len(interaction.data['options']) > 2 else GAME_SETTINGS["rewards"]["rewardName"]
    except Exception:
        await interaction.response.send_message(embed=create_embed(description="An error occurred..." , color=discord.Colour.red()) , ephemeral=True)

    response = userManager.update_balance(user.id , amount , token)
    if response != -1:
        
        await interaction.response.send_message(embed=create_embed(
            title=f"{'Added' if amount > 0 else 'Detracted'} to {user.name} balance" , 
            description=f"{user.mention} balance have been changed : {amount} ${token}\nNew balance is : {response} ${token}", 
            color=discord.Colour.green() if amount > 0 else discord.Colour.red()
            )
        )
    else:
        await interaction.response.send_message(embed=create_embed(description="Couldn't change user balance..." , color=discord.Colour.red()) , ephemeral=True)


@tree_cls.command(name='honorais-my-champion', description="Retrieve user champion")
async def get_user_champion(interaction: discord.Interaction):

    user : discord.Member = interaction.user

    user_data = userManager.get_user_data(user.id)

    if 'default_nft' not in user_data:
        await interaction.response.send_message(embed=create_embed(
            description="You either not connected your wallet to the website, or don't have an active champion" , 
            color=discord.Colour.red(),
            footer_text="Go here to select your champion! https://www.thehonorais.com/profile"),
            ephemeral=True)
    else:
        nft_data = user_data['default_nft']
        attributes = nft_data["attributes"]

        embed = create_embed(title=f"Champion : {attributes['title']} ",description=f"{attributes['description']}")

        embed.add_field(name="STR" , value=f"**{attributes['str']}**", inline=True)
        embed.add_field(name="DEX" , value=f"**{attributes['dex']}**", inline=True)
        embed.add_field(name="INT" , value=f"**{attributes['int']}**", inline=True)
        embed.add_field(name="-" , value=f"-", inline=True)
        embed.add_field(name="LUCK" , value=f"**{attributes['luck']}**", inline=True)
        embed.add_field(name="-" , value=f"-", inline=True)

        embed.set_image(url=nft_data["media"].replace("#","%23"))
        embed.set_footer(text="Made by DrTranzoc | @honorais")

        await interaction.response.send_message(embed=embed)


@tree_cls.command(name='honorais-arena-leaderboard', description="Look at the leaderboard (Top 10 only)")
async def get_leaderboard(interaction: discord.Interaction):

    mode : str = interaction.data['options'][0]['value'] if 'options' in interaction.data and len(interaction.data['options']) > 0 else "HONOR"

    leaderboard_raw = userManager.get_leaderboard(mode)
    if len(leaderboard_raw) == 0:
        interaction.response.send_message(embed=create_embed("NO USERS IN THE LEADERBOARD"))

    embed = create_embed(title="HONORAIS LEADERBOARD",description=f"HonOrais royale rankings, sorted by {mode.lower().replace('_',' ')}")

    rank = 1

    header_spaces = " ".join(["" for _ in range(25)])
    embed.add_field(name="User" + header_spaces + "Amount" , value="###############", inline=False)
    for user_raw in leaderboard_raw:
        user : discord.Member = interaction.guild.get_member(int(user_raw["discord_id"]))
        
        user_value = f"{rank}) **{user.global_name if user else '...'}"
        value=str(user_raw["games_data"]["games_played"])
        if mode == "HONOR":
            value=str(user_raw["balances"].get("HONOR", 0))
        elif mode == "WINS":
            value=str(user_raw["games_data"]["games_won"])

        spaces = " ".join(["" for _ in range(35 - len(user_value) - len(value))])
        
        embed.add_field(name=f"{user_value}{spaces}{value}", inline=False)

        rank += 1

    await interaction.response.send_message(embed=embed)

@tree_cls.command(name='honorais-arena-start', description="Start an arena. React to participate!")
async def arena_start(interaction: discord.Interaction):

    try:
        countdown = interaction.data['options'][0]['value']
        minplayers = interaction.data['options'][1]['value']
        role : discord.Role = interaction.data['options'][2]['value'] if len(interaction.data['options']) > 2 else "<@everyone>"
    except Exception:
        await interaction.response.send_message(embed=create_embed(description="An error occurred..." , color=discord.Colour.red()) , ephemeral=True)

    if minplayers < 1:
        await interaction.response.send_message(embed=create_embed(description="Minimum-players **cannot** be lower than **1**" , color=discord.Colour.red()) , ephemeral=True)
        return

    # Only specific people can use the command
    authorized = await check_role(interaction, GAME_SETTINGS["adminRoleName"])
    if not authorized:
        await interaction.response.send_message(embed=create_embed(description="You are **not** authorized to use this command." , color=discord.Colour.red()) , ephemeral=True)
        return

    await interaction.response.send_message("<@&" + role + ">" if role != "@everyone" else role, embed=create_embed(
                                                                        title="HONORAIS ROYALE",
                                                                        description="# HONORAIS! \n Fight and DIE for **honor!** Your anchestors awaits *you*!\n## REACT WITH ⚔️ TO JOIN!",
                                                                        color=discord.Colour.dark_green(),
                                                                        image_url=GAME_SETTINGS["botBanner"],
                                                                        footer_text="Made by DrTranzoc @honorais\n"
                                                                    ))
    message = await interaction.original_response()
    await message.add_reaction('⚔️')

    valid_users = {}
    
    warning = 0
    for _ in range(0 , countdown, 10):

        await asyncio.sleep(10)

        warning += 10
        if warning % 30 == 0:
            await interaction.followup.send(embed=create_embed(description=f"## The bloodbath will start in {countdown - warning} seconds..." , color=discord.Colour.yellow())) 

        #Fetch every user that reacted to the original message
        message = await interaction.channel.fetch_message(message.id)
        reaction_users : list = []

        for reaction in message.reactions:
            if reaction.emoji == '⚔️':
                async for user in reaction.users():
                    if user != client.user:
                        reaction_users.append(user)

        #Check if user is valid
        for user in reaction_users:
            if user not in valid_users:
                check_outcome = userManager.check_active_roster(user.id, GAME_SETTINGS["collectionAddress"])
                if check_outcome["outcome"]:
                    valid_users[user] = check_outcome["user_data"]
                else:
                    await message.remove_reaction('⚔️', user)
                    try:
                        await user.send("You don't have an NFT in the active roster!\nLink your discord and select your active NFT here : https://www.thehonorais.com/profile")
                    except discord.Forbidden:
                        pass

    if len(valid_users.keys()) < minplayers:
        await interaction.followup.send(embed=create_embed(description="Not enough players to start the arena!" , color=discord.Colour.red()))
        return
    
    await run_arena(interaction, valid_users)
        
async def run_arena(interaction: discord.Interaction, players : dict):
    rewards : dict = GAME_SETTINGS["rewards"]
    running_players = list(players.keys())
    top = min(len(rewards["rewardDistribution"].keys()) , len(players.keys()))
    token = rewards["rewardName"]
    topPlayers = []

    runningPlayersString = '\n'.join([player.mention for player in running_players])
    await interaction.followup.send(embed=discord.Embed(
        title="ARENA IS STARTING!!",
        description=f"Running players :  \n {runningPlayersString}!"
    ))
    
    while len(running_players) > 1:

        if len(running_players) < 2:
            break
        
        group = {}
        for player in random.sample(running_players, min(3, len(running_players))):
            group[player] = players[player]

        survivors, eliminated, recap = simulate_battle(group)

        #Inject player names instead of the NFT name
        for player in players:
            player_name = players[player]["default_nft"]["attributes"]["title"]
            recap = recap.replace(player_name , player.mention)

        #Remove defeated players
        for player in eliminated:
            if len(running_players) <= top:
                
                topPlayers.insert(0, {
                    "position" : str(top - len(topPlayers)),
                    "player_data" : player
                })

            running_players.remove(player)

        #Battle recap
        recap = recap.replace(". ",".\n\n")

        survivor_mentions = '\n'.join([player.mention for player in survivors])
        await interaction.followup.send(embed=create_embed(title="BATTLE RECAP\n\n" , 
                                                           description=recap + f"\n\n\n**ROUND SURVIVOR** \n{survivor_mentions} \n**{str(len(running_players))}** players remaining!",
                                                           thumbnail_url=players[survivors[0]]["default_nft"]["media"].replace("#","%23")
                                                           ))
        
        await asyncio.sleep(6)  # Time between rounds

    ### RESULT PHASE
    if len(running_players) == 1:
        await asyncio.sleep(5)
        
        winner = running_players.pop()
        embed = create_embed(
            title=f"WINNER! {winner.global_name}" , 
            description=f"Congratulations, {winner.mention}, you are earned **{rewards['rewardDistribution']['1']} ${token}**" , 
            image_url=players[winner]["default_nft"]["media"].replace("#","%23"))
        
        embed.add_field(name="POSITION", value="#######" , inline=True)
        embed.add_field(name="NAME", value="#####" , inline=True)
        embed.add_field(name=f"${token}", value="######" , inline=True)

        for player in topPlayers:
            embed.add_field(name=f"-" , value=f"{player['position']}" , inline=True)
            embed.add_field(name=f"-" , value=f"{player['player_data'].mention}" , inline=True)
            embed.add_field(name=f"-" , value=f"+{rewards['rewardDistribution'][player['position']]}" , inline=True)
        
        embed.set_footer(text="Made by DrTranzoc | @honorais")

        await interaction.followup.send(embed=embed)

        topPlayers.insert(0, {
                    "position" : "1",
                    "player_data" : winner
                   })
        
        #Reward players with custom token
        for player in topPlayers:
            amount = rewards["rewardDistribution"][player["position"]]
            userManager.update_balance(player["player_data"].id , amount , token)
            userManager.update_user_wins(player["player_data"].id)
        
        for player in players:
            userManager.update_user_gamescount(player.id)

if __name__=='__main__':
    #Load game settings
    GAME_SETTINGS = json.load(open("gameSettings.json", "r"))
    client.run(GAME_SETTINGS["discordBotToken"])