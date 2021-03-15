import numpy as np
from pathlib import Path
from zephyrus_sc2_parser import parse_replay
from constants import MATCHUPS, LETTER_TO_RACE, COMMAND_BUILDINGS, TECH_BUILDINGS

replay_dir = Path('IEM')

matchup_maps = {}
matchup_openers = {}
matchup_max_collection_rate = {}
matchup_win_loss = {}
player_win_loss = {}
for matchup in MATCHUPS:
    matchup_max_collection_rate[matchup] = []
    matchup_openers[matchup] = {
        LETTER_TO_RACE[matchup[:1]]: {},
        LETTER_TO_RACE[matchup[-1:]]: {},
    }
    matchup_win_loss[matchup] = {
        'win': 0,
        'loss': 0,
    }


def handle_replay(replay):
    players = replay.players
    for matchup in matchup_win_loss.keys():
        # check for mirror
        if players[1].race[:1] == players[2].race[:1]:
            if f'{players[1].race[:1]}v{players[1].race[:1]}' == matchup:
                current_matchup = matchup
                break
            else:
                continue

        # check that the inital letter of both races is in the matchup
        if (
            players[1].race[:1] in matchup
            and players[2].race[:1] in matchup
        ):
            current_matchup = matchup
            break

    # add map
    current_map = replay.metadata['map']
    if current_map not in matchup_maps:
        matchup_maps[current_map] = {}

    if current_matchup not in matchup_maps[current_map]:
        matchup_maps[current_map][current_matchup] = {
            'win': 0,
            'loss': 0,
        }

    # add max collection rate for matchup
    max_collection_rate = min(
        replay.summary['max_collection_rate'][1],
        replay.summary['max_collection_rate'][2],
    )
    matchup_max_collection_rate[current_matchup].append(max_collection_rate)

    # add win/loss for matchup
    # need to find the leading race player
    for player in players.values():
        if player.name not in player_win_loss:
            player_win_loss[player.name] = {
                'win': 0,
                'loss': 0,
            }

        if replay.metadata['winner'] == player.player_id:
            player_win_loss[player.name]['win'] += 1
        else:
            player_win_loss[player.name]['loss'] += 1

        # this player is the leading race in the matchup
        # since that is the perspective matchup stats are from
        if player.race[:1] == current_matchup[:1]:
            if replay.metadata['winner'] == player.player_id:
                matchup_win_loss[current_matchup]['win'] += 1
                matchup_maps[current_map][current_matchup]['win'] += 1
            else:
                matchup_win_loss[current_matchup]['loss'] += 1
                matchup_maps[current_map][current_matchup]['loss'] += 1

    for player in players.values():
        opening_buildings = []
        for obj in player.objects.values():
            if (
                (
                    obj.name in COMMAND_BUILDINGS[player.race]
                    or obj.name in TECH_BUILDINGS[player.race]
                )
                and obj.birth_time
            ):
                opening_buildings.append(obj)
        opening_buildings.sort(key=lambda x: x.init_time)

        player_opening = []
        prev_tech_building = None
        tech_building_count = 0
        for obj in opening_buildings:
            if tech_building_count >= 3:
                break

            if obj.name in TECH_BUILDINGS[player.race]:
                # sequential tech buildings of the same type only count as 1 tech building
                if not prev_tech_building or (prev_tech_building.name != obj.name):
                    tech_building_count += 1
                    prev_tech_building = obj
            player_opening.append(obj.name_at_gameloop(obj.init_time))  # , round(obj.birth_time / 22.4)))

        # # secondary pass for morphed buildings (Orbital, Lair, etc)
        # for obj in opening_buildings:
        #     # if we found the last building in the recorded opening, we're done
        #     if obj is player_opening[-1]:
        #         break

        #     if obj.morph_time:
        #         for index, building in player_opening:
        #             if building.init_time < obj.morph_time:
        #                 player_opening.insert(index + 1, obj.name_at_gameloop(obj.morph_time))

        # cast list to tuple so it's hashable
        if tuple(player_opening) not in matchup_openers[current_matchup][player.race]:
            matchup_openers[current_matchup][player.race][tuple(player_opening)] = 0
        matchup_openers[current_matchup][player.race][tuple(player_opening)] += 1


def recurse(dir_path):
    if dir_path.is_file():
        handle_replay(parse_replay(dir_path, local=True, network=False))
        return

    for obj_path in dir_path.iterdir():
        if obj_path.is_file():
            handle_replay(parse_replay(obj_path, local=True, network=False))
        elif obj_path.is_dir():
            recurse(obj_path)


recurse(replay_dir)

print('Matchup Winrates')
print('----------------')
for matchup, record in matchup_win_loss.items():
    wins = record['win']
    losses = record['loss']
    winrate = round((wins / (wins + losses) * 100), 1) if wins or losses else 'N/A'
    print(f'{matchup}: {winrate}% ({wins}W, {losses}L)')

print('\n\nPlayer Winrates')
print('---------------')
for player, record in player_win_loss.items():
    wins = record['win']
    losses = record['loss']
    winrate = round((wins / (wins + losses) * 100), 1) if wins or losses else 'N/A'
    print(f'{player}: {winrate}% ({wins}W, {losses}L)')


print('\n\nMap Winrates')
print('------------')
for map_name, matchups in matchup_maps.items():
    print(f'\n{map_name}')
    print('----------')
    for matchup, record in matchups.items():
        wins = record['win']
        losses = record['loss']
        winrate = round((wins / (wins + losses) * 100), 1) if wins and losses else 'N/A'
        print(f'\n{matchup}: {winrate}% ({wins}W, {losses}L)')

print('\n\nMatchup Max Collection Rate')
print('---------------------------')
for matchup, values in matchup_max_collection_rate.items():
    hist = np.histogram(values, bins=5) if values else 'N/A'
    print(f'{matchup}: {hist}')

print('\n\nMatchup Openers')
print('---------------')
for matchup, race_builds in matchup_openers.items():
    print(f'\n{matchup}')
    print('---')
    for race, builds in race_builds.items():
        ordered_builds = sorted(list(builds.items()), key=lambda x: x[1], reverse=True)
        total_builds = sum(list(map(lambda x: x[1], ordered_builds)))

        print(f'\n{race} Builds:')
        build_count = 0
        for build, freq in ordered_builds:
            if build_count >= 5:
                break
            build_count += 1
            print(f'- {build} ({freq}/{total_builds})')
