import boto3
from boto3.dynamodb.conditions import Key

session = boto3.Session(
    region_name='eu-north-1',
)

dynamodb = session.resource('dynamodb')

users_table = dynamodb.Table('honorais-users')
users_discord_data = dynamodb.Table('user-discord-data')
nft_table = dynamodb.Table('nft-metadata')

def get_or_create_user_data(discord_id):
    response = users_discord_data.get_item(Key={
        "discord_id" : str(discord_id)
    })

    return response['Item'] if 'Item' in response else {
        "discord_id" : str(discord_id),
        "balances" : {},
        "games_data" : {
            "games_won" : 0,
            "games_played" : 0
        }
    }

def get_leaderboard(mode):

    users_data = scan_table(users_discord_data)
        
    if mode == "HONOR":
        users_data = list(filter(lambda x: len(x["balances"].keys()) > 0, users_data))
        return sorted(users_data, key=lambda x: x["balances"].get("HONOR", 0), reverse=True)
    
    elif mode == "WINS":
        return sorted(users_data, key=lambda x: x["games_data"]["games_won"], reverse=True)
    
    else:
        return sorted(users_data, key=lambda x: x["games_data"]["games_played"], reverse=True)


def update_balance(discord_id , amount, token_name) -> bool:

    user_data = get_or_create_user_data(discord_id)
    
    if token_name in user_data['balances']:
        user_data['balances'][token_name] += amount
        
        if user_data['balances'][token_name] < 0:
            user_data['balances'][token_name] = 0
    else:
        user_data['balances'][token_name] = amount if amount > 0 else 0

    try:
        users_discord_data.put_item(Item=user_data)
        return user_data['balances'][token_name]
    except Exception as e:
        print(e)
        return -1
    
def update_user_wins(discord_id):
    user_data = get_or_create_user_data(discord_id)
    user_data["games_data"]["games_won"] += 1
    users_discord_data.put_item(Item=user_data)

def update_user_gamescount(discord_id):
    user_data = get_or_create_user_data(discord_id)
    user_data["games_data"]["games_played"] += 1
    users_discord_data.put_item(Item=user_data)

def get_balance(discord_id , token_name) -> int:
    
    response = users_discord_data.get_item(Key={
        "discord_id" : str(discord_id)
    })

    if 'Item' not in response:
        return -1
    
    return response['Item']['balances'][token_name] if token_name != "any" else response['Item']['balances']


def check_active_roster(discord_id, collection_address):
    check_outcome = {
        "outcome": False,
        "user_data" : {}
    }
    user_data = get_user_data(discord_id)

    if "default_nft" in user_data:
        if check_still_owner(discord_id, collection_address, user_data["default_nft"]["token_id"]):
            check_outcome["outcome"] = True
            check_outcome["user_data"] = user_data
    
    return check_outcome

def get_user_data(discord_id):
    filtering_exp = Key("discord_id").eq(str(discord_id))
    response = users_table.query(KeyConditionExpression=filtering_exp)

    if 'Items' in response and len(response['Items']) > 0:
        user_data = response['Items'][0]
        return user_data
    
    return {}


def check_still_owner(discord_id , collection_address , token_id) -> bool:
    #1) Get user data to retrievbe the address
    user_data = get_user_data(discord_id)

    if "address" not in user_data:
        return False
    
    address = user_data["address"]

    nft_info = nft_table.get_item(Key = {
        "collection_address" : collection_address,
        "token_id" : token_id
    })

    if 'Item' not in nft_info:
        return False
    
    if nft_info['Item']["owner"] == address:
        return True
    
    del user_data["default_nft"]
    users_table.put_item(Item=user_data)
    
    return False

def scan_table(table):
    scan_kwargs = {}
    done = False
    start_key = None
    items = []

    while not done:
        if start_key:
            scan_kwargs['ExclusiveStartKey'] = start_key
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        start_key = response.get('LastEvaluatedKey', None)
        done = start_key is None

    return items