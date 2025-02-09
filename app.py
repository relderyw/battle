import requests
import json
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards  # Para estilizar métricas
import plotly.graph_objects as go  # Para gráficos

# Função para ajustar data e hora
def getYour(your: str, adjust_minutes=0):
    """
    Ajusta a data e hora fornecidas com base no fuso horário e minutos de ajuste.
    """
    your = datetime.strptime(your, '%d/%m/%Y %H:%M')
    your = your + relativedelta(hours=-4, minutes=adjust_minutes)
    return your.strftime('%d/%m/%Y %H:%M')

# Função para buscar os últimos dois torneios com resultados
def get_last_two_tournaments(player_nickname):
    try:
        URL = f'https://football.esportsbattle.com/api/participants/{player_nickname}/tournaments?page=1'
        response = requests.get(URL)
        dados = json.loads(response.text)
        paginas = int(dados.get('totalPages', 0))
        torneios_com_resultados = []
        for pagina in range(1, paginas + 1):
            URL = f'https://football.esportsbattle.com/api/participants/{player_nickname}/tournaments?page={pagina}'
            response = requests.get(URL)
            torneios = json.loads(response.text).get('tournaments', [])
            for torneio in torneios:
                if torneio.get('results') is not None:  # Filtra torneios com resultados
                    torneios_com_resultados.append(torneio)
            if len(torneios_com_resultados) >= 2:
                break
        return torneios_com_resultados[:2]  # Retorna os dois últimos torneios com resultados
    except Exception as e:
        print(f"❌ Erro ao buscar torneios do jogador {player_nickname}: {e}")
        return []

# Função para buscar partidas de um torneio específico
def get_tournament_matches(tournament_id):
    try:
        URL = f'https://football.esportsbattle.com/api/tournaments/{tournament_id}/matches'
        response = requests.get(URL)
        return json.loads(response.text)
    except Exception as e:
        print(f"❌ Erro ao buscar partidas do torneio {tournament_id}: {e}")
        return []

# Função para extrair dados de um jogador específico
def extract_player_data(matches, player_nickname):
    player_data = []
    for match in matches:
        if match['participant1'].get('score') is None or match['participant2'].get('score') is None:
            continue  # Pula partidas não finalizadas
        if match['participant1']['nickname'] == player_nickname:
            participant = match['participant1']
            opponent = match['participant2']
            is_home = True
        elif match['participant2']['nickname'] == player_nickname:
            participant = match['participant2']
            opponent = match['participant1']
            is_home = False
        else:
            continue  # Jogador não está nesta partida
        ht_casa = int(participant.get('prevPeriodsScores', [0])[0]) if participant.get('prevPeriodsScores') else 0
        ft_casa = participant['score']
        tt_casa = ft_casa - ht_casa
        ht_fora = int(opponent.get('prevPeriodsScores', [0])[0]) if opponent.get('prevPeriodsScores') else 0
        ft_fora = opponent['score']
        tt_fora = ft_fora - ht_fora
        pl_casa = participant['nickname'] if is_home else opponent['nickname']
        team_casa = participant['team']['token_international'] if is_home else opponent['team']['token_international']
        pl_fora = opponent['nickname'] if is_home else participant['nickname']
        team_fora = opponent['team']['token_international'] if is_home else participant['team']['token_international']
        player_data.append([
            pl_casa, team_casa, ht_casa, ft_casa, tt_casa,
            pl_fora, team_fora, ht_fora, ft_fora, tt_fora
        ])
    return player_data

# Função para criar DataFrame com os dados do jogador
def create_player_dataframe(player_nickname):
    try:
        recent_tournaments = get_last_two_tournaments(player_nickname)
        matches_data = []
        for tournament in recent_tournaments:
            tournament_id = tournament['id']
            matches = get_tournament_matches(tournament_id)
            player_data = extract_player_data(matches, player_nickname)
            matches_data.extend(player_data)
        columns = [
            'pl_casa', 'team_casa', 'ht_casa', 'ft_casa', 'tt_casa',
            'pl_fora', 'team_fora', 'ht_fora', 'ft_fora', 'tt_fora'
        ]
        return pd.DataFrame(matches_data, columns=columns)
    except Exception as e:
        print(f"❌ Erro ao criar DataFrame para o jogador {player_nickname}: {e}")
        return pd.DataFrame()

# Função para calcular métricas
def calculate_metrics(df):
    metrics = {}
    last_5 = df.tail(5)
    last_10 = df.tail(10)
    metrics['last_5'] = {
        'media_gols_ht': last_5['ht_casa'].mean(),
        'media_gols_ft': last_5['ft_casa'].mean(),
        'media_gols_totais': last_5['tt_casa'].mean(),
        'media_ambos_marcam': (last_5['ht_casa'] > 0).mean()
    }
    metrics['last_10'] = {
        'media_gols_ht': last_10['ht_casa'].mean(),
        'media_gols_ft': last_10['ft_casa'].mean(),
        'media_gols_totais': last_10['tt_casa'].mean(),
        'media_ambos_marcam': (last_10['ht_casa'] > 0).mean()
    }
    return metrics

# Função para capturar nomes de jogadores da API
def fetch_all_players():
    all_players = []
    for page in range(1, 19):  # Navega pelas 18 páginas
        URL = f'https://football.esportsbattle.com/api/participants?nickname=&page={page}'
        response = requests.get(URL)
        players = json.loads(response.text).get('participants', [])
        all_players.extend([player['nickname'] for player in players])
    return all_players

# Interface Streamlit
st.title("⚽ Análise de Confrontos ⚽")

# Captura todos os jogadores disponíveis
if 'all_players' not in st.session_state:
    st.session_state.all_players = fetch_all_players()

# Entrada de Dados
player1_nickname = st.selectbox("Jogador 1 (Casa):", st.session_state.all_players)
player2_nickname = st.selectbox("Jogador 2 (Fora):", st.session_state.all_players)

if st.button("Carregar Dados e Métricas"):
    if player1_nickname and player2_nickname:
        # Carrega os dados dos jogadores
        df_player1 = create_player_dataframe(player1_nickname)
        df_player2 = create_player_dataframe(player2_nickname)
        
        if not df_player1.empty and not df_player2.empty:
            # Calcula as métricas
            metrics_player1 = calculate_metrics(df_player1)
            metrics_player2 = calculate_metrics(df_player2)
            
            # Exibe as métricas lado a lado
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(f"Métricas de {player1_nickname}")
                st.metric(label="Gols HT (Últimos 5)", value=f"{metrics_player1['last_5']['media_gols_ht']:.2f}", delta=None)
                st.metric(label="Gols FT (Últimos 5)", value=f"{metrics_player1['last_5']['media_gols_ft']:.2f}", delta=None)
                st.metric(label="Gols Totais (Últimos 5)", value=f"{metrics_player1['last_5']['media_gols_totais']:.2f}", delta=None)
                st.metric(label="Ambos Marcaram (Últimos 5)", value=f"{metrics_player1['last_5']['media_ambos_marcam']:.2f}", delta=None)
            
            with col2:
                st.subheader(f"Métricas de {player2_nickname}")
                st.metric(label="Gols HT (Últimos 5)", value=f"{metrics_player2['last_5']['media_gols_ht']:.2f}", delta=None)
                st.metric(label="Gols FT (Últimos 5)", value=f"{metrics_player2['last_5']['media_gols_ft']:.2f}", delta=None)
                st.metric(label="Gols Totais (Últimos 5)", value=f"{metrics_player2['last_5']['media_gols_totais']:.2f}", delta=None)
                st.metric(label="Ambos Marcaram (Últimos 5)", value=f"{metrics_player2['last_5']['media_ambos_marcam']:.2f}", delta=None)
            
            # Estiliza as métricas (sem text_color)
            style_metric_cards(
                background_color="#1F2937",  # Fundo escuro
                border_size_px=1,
                border_color="#4B5563",      # Borda cinza
                border_radius_px=5,
                box_shadow=False
            )
            
            # Gráfico comparativo de gols totais
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=["Últimos 5 Jogos", "Últimos 10 Jogos"],
                y=[metrics_player1['last_5']['media_gols_totais'], metrics_player1['last_10']['media_gols_totais']],
                name=player1_nickname,
                marker_color='blue'
            ))
            fig.add_trace(go.Bar(
                x=["Últimos 5 Jogos", "Últimos 10 Jogos"],
                y=[metrics_player2['last_5']['media_gols_totais'], metrics_player2['last_10']['media_gols_totais']],
                name=player2_nickname,
                marker_color='red'
            ))
            fig.update_layout(
                title="Comparação de Gols Totais",
                xaxis_title="Período",
                yaxis_title="Média de Gols",
                barmode='group'
            )
            st.plotly_chart(fig)
            
            # Exibe os DataFrames
            st.subheader("📊 Dados Brutos")
            st.write(f"Dados de {player1_nickname}:")
            st.dataframe(df_player1)
            st.write(f"Dados de {player2_nickname}:")
            st.dataframe(df_player2)
        else:
            st.error("❌ Nenhum dado encontrado para um ou ambos os jogadores.")
    else:
        st.error("❌ Por favor, insira os nomes dos jogadores.")