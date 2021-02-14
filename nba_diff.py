import streamlit as st
import requests
import json
import pandas as pd
import numpy as np
from dataclasses import dataclass
from copy import deepcopy
from typing import Union

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


def get_game_data(season: str, gameid: str, data_type: str) -> dict:
    
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
    
    # 3=letter team abbrev
    home = content['g']['hls']['ta']
    visiting = content['g']['vls']['ta']
    
    # points scored
    home_score = content['g']['hls']['s']
    visiting_score = content['g']['vls']['s']
    
    game_data = game(gameid, home, visiting, home_score, visiting_score)
    
    return game_data


def get_player_data(game_detail: dict, team: str) -> dict:
    
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
                
    return np.array(res)

def plot_differential():

    '''plot point differentials'''
    pass

def get_rotations():
    pass

def merge_rotations():

    '''merge timing that spans period breaks. players will have consecutive rotation records with ingame=1'''
    pass

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

season = '2019'
gameid = '0041900401'

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
