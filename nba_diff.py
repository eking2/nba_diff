import streamlit as st
import requests
import json
import pandas as pd
import numpy as np
from dataclasses import dataclass
from copy import deepcopy
from typing import Optional, Dict
import matplotlib as mpl
import matplotlib.pyplot as plt

# namedtuple will not work, can't replace attribute values or set defaults
@dataclass
class game:
    '''game boxscore holding team names and points'''
    id: int
    home: str
    visiting: str
    home_score: int
    visiting_score: int


@dataclass
class rotation:
    '''track player ingame status'''
    ingame: int
    start_time: float
    # negative values when player never substituted out
    end_time: float = -1


@dataclass
class player:
    '''player info'''
    first_name: str
    last_name: str
    team: str
    rotations: list

###############################################################################
# parse data

def get_game_data(season: str, gameid: str, data_type: str) -> Dict:

    '''download play by play or game detail json data'''

    assert data_type in ['pbp', 'gamedetail'], 'invalid game data type'

    if data_type == 'pbp':
        url = f'http://data.nba.net/v2015/json/mobile_teams/nba/{season}/scores/pbp/{gameid}_full_pbp.json'
    elif data_type == 'gamedetail':
        url = f'http://data.nba.net/v2015/json/mobile_teams/nba/{season}/scores/gamedetail/{gameid}_gamedetail.json'

    r = requests.get(url)
    assert r.status_code == 200, f'invalid {data_type} request for season: {season}, gameid: {gameid}'

    content = json.loads(r.text)

    return content


def get_game_score(season: str, gameid: str) -> game:

    '''get final score and team info'''

    content = get_game_data(season, gameid, 'gamedetail')

    # 3-letter team abbrev
    home = content['g']['hls']['ta']
    visiting = content['g']['vls']['ta']

    # points scored
    home_score = content['g']['hls']['s']
    visiting_score = content['g']['vls']['s']

    game_data = game(gameid, home, visiting, home_score, visiting_score)

    return game_data


def get_player_data(game_detail: dict, team: str) -> Dict:

    '''dict of player id and info from game details. use to hold rotations'''

    assert team in ['home', 'visiting'], "invalid team option, choose ['home', 'visiting']"

    if team == 'home':
        roster = game_detail['g']['hls']['pstsg']
    else:
        roster = game_detail['g']['vls']['pstsg']

    players = {}
    for p in roster:
        if p['totsec'] > 0:
            fn = p['fn']
            ln = p['ln']
            player_id = p['pid']
            rot = rotation(0, 0)
            p_data = player(fn, ln, team, [rot])
            players[player_id] = p_data

    return players


def get_differential(pbp: dict) -> np.ndarray:

    '''record point differential between home and visiting team over time'''

    res = []

    # hs - vs (home - visiting)
    for period in pbp['g']['pd']:
        for play in period['pla']:
            if play['etype'] == 1 or play['etype'] == 3:

                # store time counting up from beginning of game and differential
                time = cl_to_seconds(play['cl'], period['p'])
                hs = play['hs']
                vs = play['vs']
                diff = hs - vs

                res.append([time, diff])

    # [time(s), point differential]
    # + is for home, - is for visiting
    return np.array(res)


def get_rotations(pbp: dict, players: dict) -> Dict:

    '''parse play-by-play for player substitution times'''

    players_copy = deepcopy(players)

    # data stored per period
    for period in pbp['g']['pd']:
        for event in period['pla']:

            # 8 = substitution
            if event['etype'] == 8:
                player_in = int(event['epid'])
                player_out = int(event['pid'])
                time = cl_to_seconds(event['cl'], period['p'])

                # sub in
                players_copy[player_in].rotations[-1].ingame = 0
                players_copy[player_in].rotations[-1].end_time = time
                players_copy[player_in].rotations.append(rotation(1, time))

                # sub out
                players_copy[player_out].rotations[-1].ingame = 1
                players_copy[player_out].rotations[-1].end_time = time
                players_copy[player_out].rotations.append(rotation(0, time))

            # end of period reset, set all players out
            elif event['etype'] == 13:

                for player_id, player in players_copy.items():
                    period_end = cl_to_seconds(event['cl'], period['p'])
                    player.rotations[-1].end_time = period_end
                    player.rotations.append(rotation(0, period_end))

            # end of game reset, remove last rotation record (will be empty)
            elif event['etype'] == 0:

                for player_id, player in players_copy.items():
                    player.rotations.pop()

            # if a player scores or assists but is not substituted the whole quarter, they must be ingame
            else:
                # 1 = score, 3 = freethrow
                if event['etype'] == 1 or event['etype'] == 3:
                    scorer = int(event['pid'])
                    players_copy[scorer].rotations[-1].ingame = 1

                    # will be blank if unassisted shot or ft
                    try:
                        assister = int(event['epid'])
                        players_copy[assister].rotations[-1].ingame = 1
                    except:
                        continue

    return players_copy


def get_player_ingame(rotation_df: pd.DataFrame) -> pd.DataFrame:

    '''time windows for when each player is in game'''

    # need time span for broken hbar, plots x + xwidth
    ingame_df = rotation_df.query("ingame == 1")
    ingame_df = ingame_df.assign(xwidth = lambda x: x['end'] - x['start'])

    player_times = []
    for player_id in rotation_df['id'].unique():
        subset = ingame_df.query("id == @player_id")
        name = subset[['fn', 'ln']].values[0]  # np array
        name = ' '.join(list(map(str, name)))
        times = subset[['start', 'xwidth']].values.tolist()
        team = subset['team'].tolist()[0]

        player_times.append([player_id, name, team, times])

    df = pd.DataFrame(player_times, columns=['id', 'name', 'team', 'times'])

    return df


@st.cache
def get_scoreboard(year: str, month: str, date: str) -> pd.DataFrame:

    '''download nba boxscore data for games on input date'''

    # pad zeros
    url = f'https://data.nba.net/data/10s/prod/v1/{year:0>4}{month:0>2}{date:0>2}/scoreboard.json'

    r = requests.get(url)
    assert r.status_code == 200, 'invalid request'

    # get stats json
    scoreboard = json.loads(r.text)

    # to dataframe
    res = []
    num_games = scoreboard['numGames']
    for i in range(num_games):
        game_id = scoreboard['games'][i]['gameId']
        visit = scoreboard['games'][i]['vTeam']['triCode']
        home = scoreboard['games'][i]['hTeam']['triCode']
        season_year = scoreboard['games'][i]['seasonYear']

        visit_score = scoreboard['games'][i]['vTeam']['score']
        home_score = scoreboard['games'][i]['hTeam']['score']

        res.append([game_id, season_year, visit, home, visit_score, home_score])

    df = pd.DataFrame(res, columns=['gameid', 'seasonYear', 'visiting', 'home', 'visiting_score', 'home_score'])

    return df


###############################################################################
# utils

def cl_to_seconds(cl: str, period: int) -> float:

    '''convert cl timing to game time elapsed in seconds'''

    # cl counts down from 12 min per period
    # DOES NOT ACCOUNT FOR OT

    mins = int(cl.split(':')[0])
    secs = float(cl.split(':')[1])  # time has decimals below 1 min

    # cl resets every period
    p = period * 12 * 60

    # count down
    elapsed = p - (mins*60) - secs

    # in seconds
    return elapsed


def players_to_df(players: dict) -> pd.DataFrame:

    '''convert players data from dict to dataframe'''

    to_df = []
    for player_id, player in players.items():
        first_name = player.first_name
        last_name = player.last_name
        team = player.team

        for rotation in player.rotations:
            ingame = rotation.ingame
            start = rotation.start_time
            end = rotation.end_time

            to_df.append([first_name, last_name, player_id, team, ingame, start, end])

    df = pd.DataFrame(to_df, columns=['fn', 'ln', 'id', 'team', 'ingame', 'start', 'end'])

    return df


def merge_rotations(players: dict) -> Dict:

    '''merge timing that spans period breaks, players will have consecutive rotation records with ingame=1'''

    players_copy = deepcopy(players)

    for player_id, player in players_copy.items():
        i = 0
        while i < len(player.rotations) - 1:
            # ingame = 1 through quarters
            if player.rotations[i].ingame == player.rotations[i+1].ingame:

                # extend end_time for rotation
                player.rotations[i].end_time = player.rotations[i+1].end_time

                # remove next rotation, no longer necessary since prior rotation extended
                player.rotations.pop(i+1)

            else:
                i += 1

    return players_copy


###############################################################################
# plotting

def plot_differential(diff: np.ndarray,
                      game_score: game,
                      home_color: str,
                      visit_color: str,
                      ax: Optional[mpl.axes.SubplotBase] = None) -> None:

    '''plot point differentials'''

    if ax is None:
        ax = plt.gca()

    p = ax.step(diff[:, 0], diff[:, 1], where='mid', color='k', alpha=0.3)

    # split into periods
    x_la = ['Q1', 'Q2', 'Q3', 'Q4']
    x_ra = [i*12*60 for i in range(len(x_la))]
    ax.set_xticks(x_ra)
    ax.set_xticklabels(x_la)

    # add horizontal 0
    ax.axhline(0, color='k', alpha=0.5)

    # fill steps with different colors
    ax.fill_between(diff[:, 0], diff[:, 1], step='mid', alpha=0.3, where=diff[:, 1] >= 0,
                    facecolor=home_color, interpolate=True, label=game_score.home)
    ax.fill_between(diff[:, 0], diff[:, 1], step='mid', alpha=0.3, where=diff[:, 1] <= 0,
                    facecolor=visit_color, interpolate=True, label=game_score.visiting)

    ax.grid(alpha=0.2)
    ax.set_axisbelow(True)
    ax.set_ylabel('Differential')
    ax.legend()

    ax.set_title(f'{game_score.visiting} vs. {game_score.home}\n{game_score.visiting_score} - {game_score.home_score}', size=15)

    # set symmetic ylim
    y_max = max(list(map(abs, plt.gca().get_ylim())))
    ax.set_ylim([-y_max, y_max])


def plot_rotation(ingame_df: pd.DataFrame,
                  team: str,
                  color: str,
                  ax: Optional[mpl.axes.SubplotBase] = None) -> None:

    '''plot rotation chart'''

    if ax is None:
        ax = plt.gca()

    subset = ingame_df.query("team == @team")

    for i, (idx, row) in enumerate(subset.iterrows()):
        times = row['times']
        ax.broken_barh(times, (i-0.25, 0.5), color=color, edgecolor='k', alpha=0.5)

    # split into periods
    x_la = ['Q1', 'Q2', 'Q3', 'Q4']
    x_ra = [i*12*60 for i in range(len(x_la))]
    ax.set_xticks(x_ra)
    ax.set_xticklabels(x_la)

    # y label player names
    y_la = subset['name'].values
    y_ra = np.arange(len(y_la))
    ax.set_yticks(y_ra)
    ax.set_yticklabels(y_la, size=12)

    ax.invert_yaxis()
    ax.grid(alpha=0.2)
    ax.set_axisbelow(True)


###############################################################################


#season = '2019'
#gameid = '0041900401'

#df = get_scoreboard('2020', '9', '8')
#print(df)

# pbp = get_game_data('2019', '0041900401', 'pbp')
# print(pbp)
# print(type(pbp))

#game_score = get_game_score('2019', '0041900401')
#print(game_score)

# game_detail = get_game_data(season, gameid, 'gamedetail')
# home_players = get_player_data(game_detail, 'home')
# print(home_players)
