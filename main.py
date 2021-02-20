import streamlit as st
import datetime
import nba_diff
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from nba_diff import game
from typing import Dict, Tuple

@st.cache
def full_data(season: str, gameid: str) -> Tuple[game, np.ndarray, pd.DataFrame]:

    '''parse all records'''

    # play-by-play and game details
    game_score = nba_diff.get_game_score(season, gameid)
    pbp = nba_diff.get_game_data(season, gameid, 'pbp')
    game_detail = nba_diff.get_game_data(season, gameid, 'gamedetail')

    # setup player data to hold rotations
    home_players = nba_diff.get_player_data(game_detail, 'home')
    visiting_players = nba_diff.get_player_data(game_detail, 'visiting')
    players = {**home_players, **visiting_players}

    # differential from play-by-play
    diff = nba_diff.get_differential(pbp)

    # merge player rotation times over periods
    players = nba_diff.get_rotations(pbp, players)
    players = nba_diff.merge_rotations(players)

    # to df and keep only ingame
    rotations_df = nba_diff.players_to_df(players)
    ingame_df = nba_diff.get_player_ingame(rotations_df)

    return game_score, diff, ingame_df


def game_played(gameid: str, scoreboard: pd.DataFrame) -> bool:

    '''check no na, from postponed games'''

    done = scoreboard.query("gameid == @gameid")['visiting_score'].values[0] != ''

    return done


def full_plot(ingame_df: pd.DataFrame, diff: np.ndarray, game_score: game, home_c: str, team_c: str) -> mpl.figure.Figure:

    '''plot player rotations and differential'''

    fig, ax = plt.subplots(3, 1, figsize=(10, 15))

    nba_diff.plot_rotation(ingame_df, 'visiting', visit_c, ax=ax.flat[0])
    nba_diff.plot_rotation(ingame_df, 'home', home_c, ax=ax.flat[2])

    # need to manually set symmetric ylim, does not auto set with subplots
    nba_diff.plot_differential(diff, game_score, home_c, visit_c, ax=ax.flat[1])
    max_y = np.abs(diff).max(axis=0)[1] * 1.1
    ax.flat[1].set_ylim([-max_y, max_y])

    plt.tight_layout()

    return fig


###############################################################################

color = pd.read_csv('colors.csv')

st.header('NBA Game Differentials')

# calendar to select date
game_date = st.date_input('Select Date')

year = game_date.year
month = game_date.month
date = game_date.day 

# show games and dropdown to select
# start with no selection
scoreboard = nba_diff.get_scoreboard(year, month, date)
game_descs = [f'{gameid} ({vis} vs. {home})' for gameid, vis, home in 
                zip(scoreboard['gameid'], scoreboard['visiting'], scoreboard['home'])]
game_descs.insert(0, None)

if len(scoreboard) == 0:
    st.write(f'No games for {year}-{month}-{date}')
else:
    st.write(scoreboard[['gameid', 'visiting', 'home', 'visiting_score', 'home_score']])
    game_desc = st.selectbox('Select Game', game_descs)

    if game_desc is not None:

        # gameid and seasonyear for game data
        gameid = game_desc.split(' ')[0]
        seasonyear = scoreboard.query("gameid == @gameid")['seasonYear'].values[0]
        vis = scoreboard.query("gameid == @gameid")['visiting'].values[0]
        home = scoreboard.query("gameid == @gameid")['home'].values[0]

        # plot vaild games
        if game_played(gameid, scoreboard):
            game_score, diff, ingame_df = full_data(seasonyear, gameid)

            # team colors
            home_c = color.query("team == @home")['color'].values[0]
            visit_c = color.query("team == @vis")['color'].values[0]

            fig = full_plot(ingame_df, diff, game_score, home_c, visit_c)
            st.write(fig)
            

        else:
            st.write(f'{gameid} ({vis} vs. {home}) has not been played')

