import streamlit as st
import datetime
import nba_diff

st.header('NBA Game Differentials')

# calendar to select date
game_date = st.date_input('Select Date')

year = game_date.year
month = game_date.month
date = game_date.day

# show games and dropdown to select
scoreboard = nba_diff.get_scoreboard(year, month, date)
game_descs = [f'{gameid} ({vis} vs. {home})' for gameid, vis, home in 
                zip(scoreboard['gameid'], scoreboard['visiting'], scoreboard['home'])]

if len(scoreboard) == 0:
    st.write(f'No games for {year}-{month}-{date}')
else:
    st.write(scoreboard[['gameid', 'visiting', 'home', 'visiting_score', 'home_score']])
    game_desc = st.selectbox('Select Game', game_descs)

    # gameid and seasonyear for game data
    gameid = game_desc.split(' ')[0]
    seasonyear = scoreboard.query("gameid == @gameid")['seasonYear'].values[0]


