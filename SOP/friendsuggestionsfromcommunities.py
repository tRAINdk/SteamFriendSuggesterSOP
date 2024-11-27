import community as community_louvain
import aiohttp
import networkx as nx
import matplotlib.pyplot as plt #ikke brugt
import numpy as np # ikke brugt
import os
import asyncio 
import config as cfg
from aiohttp import ClientResponseError # JEG HADER ERRORHANDLING
API_KEY = '' # dette felt skulle gerne være blankt, indsæt en api key, har fjernet min da de er lavet til personligt brug og direkte kan ændre profil data  
EGO_ID = '' # Unique Identifier for en steam profil, alle profiler har en, men nogle profiler vises med deres navn i stedet for ID i deres url, jeg fortrækker at bruge https://steamid.io til at finde deres ID, men der er mange andre redskaber
if not EGO_ID:
    if cfg.EGO_ID:
        EGO_ID = cfg.EGO_ID
    else:
        print(f"FEJL: manglene EGO ID! indsæt et steam ID, enten her i {os.path.basename(os.path.abspath(__file__))} eller gennem config ved {os.path.abspath('config.py')}")
if not API_KEY:
    if cfg.API_KEY:
        API_KEY = cfg.API_KEY
    else:
        print(f"FEJL: manglene API KEY! indsæt en API key, enten her i {os.path.basename(os.path.abspath(__file__))} eller gennem config ved {os.path.abspath('config.py')}")
#prøver virkelig på at gøre det nemt at arbejde med ift error handling xD

# Cache til API-respons
friends_cache = {}
profile_cache = {}


async def get_friends(steam_id, session):
    if steam_id in friends_cache:
        return friends_cache[steam_id]

    url = f'https://api.steampowered.com/ISteamUser/GetFriendList/v1/?key={API_KEY}&steamid={steam_id}'
    data = await fetch_with_retries(session, url)

    if data and 'friendslist' in data:
        friends = [friend['steamid'] for friend in data['friendslist']['friends']]
        friends_cache[steam_id] = friends
        return friends
    return []


async def get_player_summaries(steam_ids, session):
    summaries = {}
    for i in range(0, len(steam_ids), 100):
        chunk = steam_ids[i:i + 100]
        uncached_ids = [sid for sid in chunk if sid not in profile_cache]

        if not uncached_ids:
            summaries.update({sid: profile_cache[sid] for sid in chunk})
            continue

        ids_string = ','.join(uncached_ids)
        url = f'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={API_KEY}&steamids={ids_string}'
        data = await fetch_with_retries(session, url)

        if data and 'response' in data and 'players' in data['response']:
            for player in data['response']['players']:
                profile_cache[player['steamid']] = {'name': player['personaname']}
            summaries.update(profile_cache)
    return summaries


# Community detection og graph creation
async def build_graph(steam_id, depth):
    G = nx.Graph()
    visited = set()
    current_level = [steam_id]
    
    async with aiohttp.ClientSession() as session:
        for _ in range(depth):
            next_level = []
            for sid in current_level:
                if sid not in visited:
                    visited.add(sid)
                    friends = await get_friends(sid, session)
                    for friend_id in friends:
                        G.add_node(sid)
                        G.add_node(friend_id)
                        G.add_edge(sid, friend_id)
                        if friend_id not in visited:
                            next_level.append(friend_id)
            current_level = next_level
        
        all_steam_ids = list(G.nodes)
        #player_data = await get_player_summaries(all_steam_ids, session)
        
        #for node in G.nodes:
        #    if node in player_data:
        #        G.nodes[node]['name'] = player_data[node]['name']   
 # commented a lot because I'm getting rate limited hard lol and this is quite a slow process.   
    return G

# Community Detection (Louvain)
def detect_communities(G):
    partition = community_louvain.best_partition(G)
    communities = {}
    for node, comm in partition.items():
        if comm not in communities:
            communities[comm] = []
        communities[comm].append(node)
    return communities

# bruger Jaccard similarity
def calculate_similarity(user, community, G):
    similarities = []
    for other_user in community:
        if other_user != user:
            # Here we calculate similarity based on common neighbors (Jaccard similarity)
            common_neighbors = len(set(G.neighbors(user)) & set(G.neighbors(other_user)))
            total_neighbors = len(set(G.neighbors(user)) | set(G.neighbors(other_user)))
            similarity = common_neighbors / total_neighbors if total_neighbors > 0 else 0
            similarities.append((other_user, similarity))
    return similarities

# Function to get recommended friends based on similarity
def recommend_friends(user, K, communities, G):
    recommendations = []
    existing_friends = set(G.neighbors(user))  # Alle eksisterende venner
    existing_friends.add(user)  # Tilføj brugeren selv for at udelukke fra anbefalinger

    for community_id, community in communities.items():
        similarities = calculate_similarity(user, community, G)
        # Filtrerer eksisterende venner fra anbefalingerne (et step jeg glemte første gang så fik returneret en anbefaling til en allerede eksisterende ven :b)
        similarities = [(other_user, similarity) for other_user, similarity in similarities if other_user not in existing_friends]
        similarities.sort(key=lambda x: x[1], reverse=True)  # Sorter efter lighedsværdi
        recommendations.extend(similarities[:K])

    # Sorter alle anbefalinger og returner de top K brugere
    recommendations.sort(key=lambda x: x[1], reverse=True) #lambda babyy
    recommended_users = [user for user, _ in recommendations[:K]]

    return recommended_users
async def fetch_with_retries(session, url, max_retries=5, initial_wait=1):
    retries = 0
    wait_time = initial_wait

    while retries < max_retries:
        try:
            # Check remaining requests before proceeding
            remaining_requests = await get_remaining_requests(session)
            if remaining_requests is not None and remaining_requests < 20: # ved ikke helt hvad det bedste nummer er så prøv frem.
                print(f"Low on remaining requests ({remaining_requests}). Pausing for {wait_time} seconds")
                await asyncio.sleep(wait_time)
                wait_time *= 2  # Exponential backoff
            
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()
        except ClientResponseError as e:
            if e.status == 429:  # Too Many Requests
                print(f"HTTP 429 Too Many Requests. Retrying in {wait_time} seconds")
                await asyncio.sleep(wait_time)
                wait_time *= 2  # Exponential backoff
                retries += 1
            elif e.status == 401:  # Unauthorized
                print(f"HTTP 401 Unauthorized: probably private profile/friends {url}")
                return None
            else:
                print(f"HTTP Error {e.status}: {e.message} for {url}")
                return None
        except Exception as e:
            print(f"Error during fetch: {e}")
            return None
    print(f"Max retries exceeded for {url}.")
    return None

async def get_remaining_requests(session): # i tilfælde af rate limit benyttes denne til at begrænse anmodninger
    url = "https://api.steampowered.com/ISteamApps/GetAppList/v2/?key={API_KEY}"
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
            if 'remaining_requests' in data:
                return int(data['remaining_requests'])
    except Exception as e: # og ja, mine anmodninger omkring hvor mange API anmodninger jeg har tilbage bliver også rate limited ):
        print(f"Error checking remaining requests: {e}")
    return None  





# main exec logik
async def main(depth, user_id, K):
    
    G = await build_graph(user_id, depth)
    
    # communities med Louvain algoritme
    communities = detect_communities(G)
    
    # anbefalede venner
    recommended_friends = recommend_friends(user_id, K, communities, G)
    
    print(f"Recommended friends for user {user_id}: {recommended_friends}")

# User input
depth = int(input("Indtast antal niveauer væk fra center profil (2 eller 3 er nok bedst): "))
K = int(input("Indtast antal anbefalede venner (k): "))

# Run the main algorithm asyncronously, actually hard ish to spell
asyncio.run(main(depth, EGO_ID, K))  
