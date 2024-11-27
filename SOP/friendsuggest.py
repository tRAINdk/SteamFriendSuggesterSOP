import aiohttp
import asyncio
import networkx as nx
import matplotlib.pyplot as plt
from collections import Counter
import config as cfg
import os
#76561198800759738 my steam id

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

friends_cache = {}

async def get_friends(steam_id, session):
    if steam_id in friends_cache:
        return friends_cache[steam_id]
    
    url = f'https://api.steampowered.com/ISteamUser/GetFriendList/v1/?key={API_KEY}&steamid={steam_id}'
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            response_text = await response.text()
            if response_text.strip() == "":
                return []
            data = await response.json()
            if 'friendslist' in data:
                friends = [friend['steamid'] for friend in data['friendslist']['friends']]
                friends_cache[steam_id] = friends
                return friends
            else:
                return []
    except Exception as e:
        print(f"Fejl ved hentning af venneliste: {e}")
        return []

async def find_best_candidate_and_visualize(ego_id):
    async with aiohttp.ClientSession() as session:
        # Trin 1: Hent ego's venner
        ego_friends = await get_friends(ego_id, session)
        print(f"Ego's venner: {ego_friends}")

        # Opret grafen
        G = nx.Graph()
        G.add_node(ego_id, type="ego")

        # Tilføj ego's venner
        for friend in ego_friends:
            G.add_edge(ego_id, friend)
            G.nodes[friend]['type'] = "friend"

        # Trin 2: Hent venners venner og beregn fælles naboer
        candidate_scores = Counter()
        for friend in ego_friends:
            friends_of_friend = await get_friends(friend, session)
            for fof in friends_of_friend:
                G.add_edge(friend, fof)

                if fof != ego_id and fof not in ego_friends:
                    common_neighbors = len(list(nx.common_neighbors(G, ego_id, fof)))
                    candidate_scores[fof] += common_neighbors
                    G.nodes[fof]['type'] = "candidate"  # Marker som kandidat

        # Trin 3: Find den kandidat med flest fælles naboer
        if candidate_scores:
            best_candidate = max(candidate_scores, key=candidate_scores.get)
            best_score = candidate_scores[best_candidate]
            print(f"Bedste kandidat: {best_candidate} med {best_score} fælles naboer https://steamcommunity.com/profiles/{best_candidate}")
        else:
            print("Ingen kandidater fundet.")

        # Visualisering
        visualize_graph(G, candidate_scores, ego_id)

def visualize_graph(G, candidate_scores, ego_id):
    """
    Visualiserer grafen med forskellige farver baseret på nodetyper.
    """
    pos = nx.spring_layout(G, seed=42)  # Layout for grafen
    node_colors = []
    node_sizes = []

    for node in G.nodes:
        if G.nodes[node].get('type') == "ego":
            node_colors.append("red")  # Ego-personen
            node_sizes.append(300)
        elif G.nodes[node].get('type') == "friend":
            node_colors.append("blue")  # Ego's venner
            node_sizes.append(200)
        elif G.nodes[node].get('type') == "candidate":
            # Kandidater får farver og størrelse afhængigt af deres score
            score = candidate_scores.get(node, 0)
            node_colors.append(plt.cm.plasma(score / max(candidate_scores.values(), default=1)))
            node_sizes.append(100 + score * 50)
        else:
            node_colors.append("gray")  # Andre
            node_sizes.append(100)

    plt.figure(figsize=(12, 12))
    nx.draw(
        G, pos,
        with_labels=True,
        labels={node: node if G.nodes[node].get('type') == "ego" else "" for node in G.nodes},  # Kun vis ego's navn. for at hjælpe med identifikation
        node_color=node_colors,
        node_size=node_sizes,
        edge_color="gray",
        font_size=8,
    )
    plt.title("Vennegraf med kandidater og fælles naboer")
    plt.show()

# Kør algoritmen
async def main():
    await find_best_candidate_and_visualize(EGO_ID)

asyncio.run(main())
