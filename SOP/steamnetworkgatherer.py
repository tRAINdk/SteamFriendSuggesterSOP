import config as cfg
import aiohttp
# overvej om der skal installeres aiodns
import asyncio
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import json
import csv
import zipfile
import os
import community as community_louvain
from sklearn.cluster import KMeans
from matplotlib.widgets import CheckButtons # benyttes udelukkende til at få checkboxes så det er nemmere at eksportere billeder hvor man kan få et overblik uden panorering ved ikke om jeg gider lave det nu eller bare ændre koden når nødvendigt hvis jeg overhovedet gør. 
import os
'''
README

Hvis du læser dette vil jeg bare sige tak, jeg har brugt mange timer på at tænke over hvordan, og derefter lave denne kode. jeg har brugt meget svag inspiration fra en video jeg så et par måneder siden, har dog ikke genset den for at sørge for at jeg ikke kopierer den. 
( link til video https://www.youtube.com/watch?v=o879xRxmwmU ) 
Det er vigtigt at nævne at koden er lidt funky, kræver af og til at man køre den igen, så hvis man får en fejl med det samme når man kører det, så kør det igen efter. (tror det pga et wtrue loop jeg har)
jeg har fjernet min API key under da det er en del af min ejendom og fungerer på en måde for et ID til mine applikationer, den API nøgle kan lidt forskelligt og er knyttet til mig, så for at undgå at den skulle
havne et tilfældigt sted har jeg fjernet den. hvis du øsnker at lave en ny kan du hente en her https://steamcommunity.com/dev/apikey ved at logge ind med steam, hvis du ikke har en profil kan du lave en her gratis https://store.steampowered.com/join/

koden benytter sig af en menu jeg lavede lidt efter min dokumentering af koden for at samle det hele. den er lidt rushed så kan godt være der er fejl, har dog prøvet på at gøre den så selvofrklarende som muligt ift input osv.
'''

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

plt.rcParams['font.family'] = 'DejaVu Sans'

def display_menu():
    print("\nHovedmenu:")
    print("1. Indlæs tidligere gemt graf")
    print("2. Start ny datasearch")
    print("3. Udforsk eksisterende graf interaktivt (zoom og pan)")
    print("4. Byg og vis graf med filtrerede noder")
    print("5. Cluster graf")
    print("6. Afslut")
    choice = input("Vælg en mulighed (1-6): ").strip()
    return choice

 
def load_previous_graph():
    filename = 'graph_data.json'
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                G = nx.readwrite.json_graph.node_link_graph(data)
                print("Tidligere grafdata indlæst.")
                return G
        except Exception as e:
            print(f"Fejl ved indlæsning af grafdata: {e}")
    else:
        print("Ingen gemte grafdata fundet.")
    return None

async def build_filtered_graph(steam_id, min_connections, depth):
    G = nx.Graph()
    plt.title(f"Filtered Graph with a depth of: {depth} and a minimum connections of {min_connections}")
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
        
        # Filtrering af noder baseret på minimum antal forbindelser, ved ikke hvor nyttigt det er men troede det ville være smartere
        G = nx.Graph((n, d) for n, d in G.degree() if d >= min_connections)
        
        # Beregn positioner med spring_layout
        pos = nx.spring_layout(G, seed=42, k=0.35, iterations=150)  # k styrer hvor meget force nodes bliver eh "trukket fra hinanden"? itteration giver sig selv.
        
        # Farver noderne baseret på degree og skaler deres størrelse
        save_graph_image(G, pos)  # Gem grafen som et billede
    
    return G

def save_graph_image(G, pos, filename='graph.png'):
    
    labels = {
        node: G.nodes[node].get('name', node).replace('$', '')  # Remove problematic characters
        for node in G.nodes()
    }

    # Farv noderne baseret på deres degree (forbindelser)
    node_degrees = [G.degree(node) for node in G.nodes()]
    node_color = plt.cm.plasma(np.array(node_degrees) / max(node_degrees))  # Bruger farveskala (plasma)
    
    # Skaler node_størrelse baseret på degree 
    node_sizes = [G.degree(node) * 10 for node in G.nodes()]  # Størrelse prop. til forbindelser
    
    # Skab grafen og visualiser den
    fig, ax = plt.subplots(figsize=(12, 12))
    nx.draw(
        G, pos, 
        with_labels=True, 
        labels=labels, #bruger labels ovenover for at undgå LaTeX (fordi folk har alle navne i universet som kan ødelægge min kode ):
        node_size=node_sizes,
        node_color=node_color,  # Tildel farver til noderne
        font_size=5, 
        cmap='plasma',  # Farveskala
        ax=ax
    )
    
    plt.savefig(filename, format='png', dpi=300)
    print(f"Graf gemt som {filename}")

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
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                if 'response' in data and 'players' in data['response']:
                    for player in data['response']['players']:
                        profile_cache[player['steamid']] = {
                            'name': player['personaname']
                        }
                    summaries.update(profile_cache)
        except Exception as e:
            print(f"Fejl ved hentning af profiloplysninger: {e}")
    return summaries

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
        player_data = await get_player_summaries(all_steam_ids, session)
        
        for node in G.nodes:
            if node in player_data:
                G.nodes[node]['name'] = player_data[node]['name']
    
    return G

def export_graph_data(G):
    # Exporter som JSON
    json_filename = 'graph_data.json'
    data = nx.readwrite.json_graph.node_link_data(G)
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    print(f"Grafdata gemt som {json_filename}")

    # Exporter nodes and edges som CSV fil :)
    nodes_filename = 'nodes.csv'
    edges_filename = 'edges.csv'

    with open(nodes_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Node', 'Name'])
        for node, attrs in G.nodes(data=True):
            writer.writerow([node, attrs.get('name', '')])

    with open(edges_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Source', 'Target'])
        for source, target in G.edges():
            writer.writerow([source, target])

    print(f"Noder gemt som {nodes_filename}, og kanter gemt som {edges_filename}")

def bundle_graph_files(output_filename='graph_bundle.zip'):
    with zipfile.ZipFile(output_filename, 'w') as zf:
        for file in ['graph_data.json', 'nodes.csv', 'edges.csv', 'graph.png']:
            if os.path.exists(file):
                zf.write(file)
    print(f"Alle filer pakket i {output_filename}")

async def interactive_graph_view(G):
    print("Interaktiv visning af grafen (Zoom og pan understøttes).")
    pos = nx.spring_layout(G, seed=42)
    fig, ax = plt.subplots(figsize=(12, 12))
    nx.draw(
        G, pos, ax=ax, 
        with_labels=True, 
        labels={node: G.nodes[node].get('name', node) for node in G.nodes}, 
        node_size=30, font_size=6
    )
    plt.show()

def detect_communities(G):
    # Bruger Louvain-metoden til at opdage fællesskaber i grafen
    partition = community_louvain.best_partition(G)
    
    pos = nx.spring_layout(G, seed=42)
    plt.figure(figsize=(12, 12))

    # Farv noderne baseret efter community
    communities = set(partition.values())
    colors = plt.cm.get_cmap("tab10", len(communities))

    for community_id in communities: 
        community_nodes = [node for node, comm in partition.items() if comm == community_id]
        nx.draw_networkx_nodes(
            G, pos, nodelist=community_nodes, 
            node_size=300, node_color=[colors(community_id)]
        )

    # Tegn kanterne
    nx.draw_networkx_edges(G, pos, alpha=0.5)
    
    # Tilføj titel og fjern labels
    plt.title("Community Detection med Louvain Metoden") # ovevej at ændre til noget bedre?
    plt.axis("off")  # Slå akser fra så man bedre kan se resultater
    plt.show()


def perform_kmeans_clustering(G, num_clusters):
    # Beregn positioner for alle noder
    pos = nx.spring_layout(G, seed=42)
    node_positions = np.array([pos[node] for node in G.nodes()])
    
    # Bruger KMeans til at finde clustre
    kmeans = KMeans(n_clusters=num_clusters, random_state=42)
    kmeans.fit(node_positions)
    labels = kmeans.labels_

    # Tilknyt cluster labels til noderne
    node_cluster_mapping = {node: labels[i] for i, node in enumerate(G.nodes())}
    return node_cluster_mapping

def draw_clusters(G, node_cluster_mapping):
    pos = nx.spring_layout(G, seed=42)
    plt.figure(figsize=(12, 12))

    # Skab en farvepalette til de forskellige clustre
    colors = plt.cm.get_cmap("tab10", len(set(node_cluster_mapping.values())))
    for cluster_id in set(node_cluster_mapping.values()):
        cluster_nodes = [node for node, label in node_cluster_mapping.items() if label == cluster_id]
        nx.draw_networkx_nodes(G, pos, nodelist=cluster_nodes, node_size=300, node_color=[colors(cluster_id)])

    # Tegn kanterne og noderne
    nx.draw_networkx_edges(G, pos, alpha=0.5)
    #nx.draw_networkx_labels(G, pos, font_size=10) # fjernet fordi de er i vejen
    plt.title("K-Means Clustering af Steam Vennegraf")
    plt.axis("off") #fjern labels da de er i vejen
    plt.show()

async def cluster_graph(G): # menu
    print("Vælg clustering metode:")
    print("1. K-Means")
    print("2. Community Detection (Louvain)")
    choice = input("Vælg en metode (1-2): ").strip()
    
    if choice == "1":    # kmeans
        num_clusters = int(input("Indtast antal clustre (f.eks. 10): ")) # tror mere end 10 er bedre, men det bare et foreslag så andre kan bruge programmet
        node_cluster_mapping = perform_kmeans_clustering(G, num_clusters) 
        draw_clusters(G, node_cluster_mapping)
    elif choice == "2": #  Community Detection (Louvain
        detect_communities(G)
    else:
        print("Ugyldigt valg. Prøv igen.")


# ok, men hvornår er en lambda funktion nyttig, forstår hvad det er, men hvornår er det virkelig bedre, måske ser det mere clean ud idk. det sparer måske memory?

async def main(): # har ikke skrevet så mange kommentarer her da det er en menu og jeg føler den forklarer sig selv ret godt.
    while True:
        choice = display_menu()
        if choice == "1":
            G = load_previous_graph()
            if G:
                print("Tidligere gemt graf er indlæst.")
            else:
                print("Ingen gemte data fundet.")
        
        elif choice == "2":
            depth = int(input("Indtast antal niveauer væk fra center profil (2, 3, 4...): "))
            G = await build_graph(EGO_ID, depth)
            pos = nx.spring_layout(G, seed=42)
            save_graph_image(G, pos)
            export_graph_data(G)
            bundle_graph_files()
            print("Ny datasearch afsluttet, og filer er gemt.")
        
        elif choice == "3":
            G = load_previous_graph()
            if G:
                await interactive_graph_view(G)
            else:
                print("Ingen grafdata tilgængelig til visning.")
        
        elif choice == "4":
            min_connections = int(input("Indtast minimum antal forbindelser for at inkludere noder (f.eks. 2): "))
            depth = int(input("Indtast dybde af grafen (f.eks. 3): "))
            print("Bygger filtreret graf med minimum", min_connections, "forbindelser og dybde", depth, "...")
            G_filtered = await build_filtered_graph(EGO_ID, min_connections, depth)
            print("Filtreret graf bygget og gemt.")
       
        elif choice == "5":
            G = load_previous_graph()
            if G:
                await cluster_graph(G)
            else:
                print("Ingen grafdata tilgængelig for clustering.")

        elif choice == "6":
            print("Afslutter programmet.")
            break
        else:
            print("Ugyldigt valg. Prøv igen.")

# Kør den asynkrone main funktion
asyncio.run(main())

# hvorfor lærer man egentligt ikke bare at sigma er et for loop i skolen? det havde været så meget hurtigere, vi kan alle programmering anyways.
