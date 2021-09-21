import asyncio
import websockets
import random

players = {}

# Generate a unique ID for rooms
# 1. Generate an ID
# 2. Check every existing room and see if the generated ID has already been taken
# 3. If not, you're good to go! Else, go back to step 1.


def generate_room():
    roomID = ""
    found = True
    while found:
        roomID = str(random.randrange(1000, 9999))  # Generate a random ID
        found = False
        for player in players.values():
            if player["roomID"] == roomID:
                found = True
                break
    return roomID


# Generate a unique ID for clients
# Similar steps as above but compare already existing client IDs instead of room IDs


def generate_id():
    id = ""
    found = True
    while found:
        id = str(random.randrange(1000, 9999))
        found = False
        for player in players.values():
            if player["id"] == id:
                found = True
                break
    return id


# Handle a client connection
# Intialize all required data structures (such as the client objects)


async def userJoined(websocket, path):
    global players
    # Checks whether the server is full (9k players max)
    if len(players) == 8999:  # 9999 - 1000
        print("Client tried to join a full server")
        await websocket.send("error server_full")
        await websocket.close()
        return

    # Wait for the client to send the nickname
    msg = await websocket.recv()
    if not msg.startswith("nickname "):
        print("Client did not send the nickname")
        await websocket.send("error nickname_required")
        await websocket.close()
        return

    nickname = msg[9:]
    # Check whether the nickname provided falls under the requirements
    if len(nickname) < 1 or len(nickname) > 20:
        print("Client provided an invalid nickname")
        await websocket.send("error invalid_nickname")
        return

    # Generate and send user ID and room ID
    id = generate_id()
    roomID = generate_room()
    await websocket.send(f"id {id}")
    await websocket.send(f"roomID {roomID}")

    # Generate client object
    players[id] = {
        "id": id,
        "roomID": roomID,
        "ws": websocket,
        "nickname": nickname,
        "joined": "",
        "started": False,
        "otherPlayers": [],
        "game": {
            "team1": [],
            "team2": [],
            "team1Vote": [0, 0, 0],
            "team2Vote": [0, 0, 0],
        },
    }
    players[id]["otherPlayers"].append(players[id])

    # Await messages from the client and respond appropriately
    try:
        async for message in websocket:
            print(players)
            if message.startswith("join_room "):
                print("Client wants to join a room")
                reqRoomNo = message[10:]
                if len(reqRoomNo) != 4:
                    await websocket.send("error invalid_room_number")
                    continue
                if players[id]["joined"] != "":
                    await websocket.send("error already_joined")
                    continue
                if len(players[id]["otherPlayers"]) > 1:
                    await websocket.send("error party_is_not_empty")
                    continue
                if reqRoomNo == roomID:
                    print("Client tried to join their own room")
                    await websocket.send("error invalid_room_number")
                    continue
                found = False
                started = False
                for player in players.values():
                    if player["roomID"] == reqRoomNo:
                        found = True
                        if player["started"]:
                            started = True
                            break
                        if player["joined"] != "":
                            break
                        players[id]["joined"] = player["id"]
                        print("Client joined room!")
                        for p in player["otherPlayers"]:
                            await websocket.send(f"in_party {p['id']} {p['nickname']}")
                        await websocket.send("success successfully_joined")
                        for p in player["otherPlayers"]:
                            await p["ws"].send(
                                f"player_joined {id} {players[id]['nickname']}"
                            )
                        player["otherPlayers"].append(players[id])
                        break
                if not found:
                    print("Client sent invalid room number (does not exist)")
                    await websocket.send("error invalid_room_number")
                elif started:
                    print("Client tried to join an existing game")
                    await websocket.send("error game_already_started")
            elif message.startswith("start_game"):
                if players[id]["started"]:
                    await websocket.send("error already_started")
                    continue
                if len(players[id]["otherPlayers"]) == 1:
                    await websocket.send("error not_enough_players")
                    continue
                players[id]["started"] = True
                players[id]["joined"] = id
                team1 = len(players[id]["otherPlayers"]) // 2
                arr = players[id]["otherPlayers"].copy()
                random.shuffle(arr)
                for idx, elem in enumerate(arr):
                    if idx < team1:
                        players[id]["game"]["team1"].append(elem)
                        for elem2 in arr:
                            await elem2["ws"].send(f"game_started team1 {elem['id']}")
                    else:
                        players[id]["game"]["team2"].append(elem)
                        for elem2 in arr:
                            await elem2["ws"].send(f"game_started team2 {elem['id']}")
            elif message.startswith("vote "):
                # Polish this code later, bots can abuse this
                print("Client wants to vote")
                choice = message[5:]
                choiceNo = 0
                if choice == "rock":
                    choiceNo = 0
                elif choice == "paper":
                    choiceNo = 1
                elif choice == "scissor":
                    choiceNo = 2
                else:
                    await websocket.send("error invalid_choice")
                    continue
                print("Reached choice")
                game = players[players[id]["joined"]]["game"]
                found = False
                for member in players[players[id]["joined"]]["otherPlayers"]:
                    if member["id"] != id:
                        await member["ws"].send(f"user_voted {id}")
                for member in game["team1"]:
                    if member["id"] == id:
                        found = True
                        game["team1Vote"][choiceNo] += 1
                        break
                if not found:
                    game["team2Vote"][choiceNo] += 1
                print("Reached vote")
                sum = 0
                for vote in game["team1Vote"]:
                    sum += vote
                for vote in game["team2Vote"]:
                    sum += vote

                if sum >= len(players[players[id]["joined"]]["otherPlayers"]):
                    print("Reached end game")
                    top = 0
                    topChoiceNo = []
                    draw = False
                    for idx, vote in enumerate(game["team1Vote"]):
                        if vote > top:
                            top = vote
                            topChoiceNo = [idx]
                            draw = False
                        elif vote == top:
                            topChoiceNo.append(idx)
                            draw = True
                    team1Pick = 0
                    if not draw:
                        team1Pick = topChoiceNo[0]
                    else:
                        random.shuffle(topChoiceNo)
                        team1Pick = topChoiceNo[0]

                    print("Reached calc1")
                    top = 0
                    topChoiceNo = []
                    draw = False
                    for idx, vote in enumerate(game["team2Vote"]):
                        if vote > top:
                            top = vote
                            topChoiceNo = [idx]
                            draw = False
                        elif vote == top:
                            topChoiceNo.append(idx)
                            draw = True
                    team2Pick = 0
                    if not draw:
                        team2Pick = topChoiceNo[0]
                    else:
                        random.shuffle(topChoiceNo)
                        team2Pick = topChoiceNo[0]

                    print("Reached calc2")
                    if team1Pick == team2Pick:
                        for player in players[players[id]["joined"]]["otherPlayers"]:
                            await player["ws"].send("game_over draw")
                    elif (team1Pick + 1) % 3 == team2Pick:
                        for player in players[players[id]["joined"]]["otherPlayers"]:
                            await player["ws"].send("game_over team2")
                    else:
                        for player in players[players[id]["joined"]]["otherPlayers"]:
                            await player["ws"].send("game_over team1")
                    print("Reached finish")
                    players[players[id]["joined"]]["started"] = False
                    game["team1"] = []
                    game["team2"] = []
                    game["team1Vote"] = [0, 0, 0]
                    game["team2Vote"] = [0, 0, 0]

    except Exception as e:
        print("Something went wrong")
        print(e)
    if players[id]["started"]:
        first = True
        for other in players[id]["otherPlayers"]:
            if first:
                first = False
            else:
                other["joined"] = ""
                await other["ws"].send("game_destroyed")
    elif players[id]["joined"] != "":
        for player in players.values():
            for idx, other in enumerate(player[players[id]["joined"]]["otherPlayers"]):
                if other["id"] == id:
                    player[players[id]["joined"]]["otherPlayers"].pop(idx)
                else:
                    await other["ws"].send(f"player_disconnected {id}")
            game = player[players[id]["joined"]]["game"]
            found = False
            for idx, member in game["team1"]:
                if member["id"] == id:
                    found = True
                    game["team1"].pop(idx)
            if not found:
                for idx, member in game["team2"]:
                    if member["id"] == id:
                        found = True
                        game["team2"].pop(idx)
    players.pop(id)
    print("Player disconnected")
    print(players)
    await websocket.close()


start_server = websockets.serve(userJoined, "localhost", 8765)
print("Started server!")
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
