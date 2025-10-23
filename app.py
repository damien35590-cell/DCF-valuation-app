import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from math import pow

# --- Configuration de l'application Streamlit ---
st.set_page_config(
    page_title="Calculateur de Juste Valeur (DCF)",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Utiliser les secrets de Streamlit si vous le pouvez, sinon la clé en dur
# La clé Alpha Vantage (à remplacer par st.secrets["ALPHA_VANTAGE_KEY"] en production)
ALPHA_VANTAGE_API_KEY = "ZSSQL9X44YE0IN6K" 
BASE_CURRENCY = "€" # Devise par défaut

# Initialisation de l'état de session
if 'current_price' not in st.session_state:
    st.session_state.current_price = 0.0
if 'stock_name' not in st.session_state:
    st.session_state.stock_name = "--"

# --- Fonctions de Récupération de Données ---

@st.cache_data(ttl=3600) # Mise en cache des résultats pour 1 heure
def fetch_stock_price(symbol, api_key):
    """
    Récupère le prix actuel d'une action en utilisant l'API Alpha Vantage.
    """
    if not symbol:
        return 0.0, "--"
    
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
        data = response.json()

        if data.get('Global Quote') and data['Global Quote'].get('05. price'):
            price = float(data['Global Quote']['05. price'])
            return price, symbol # L'API ne donne pas toujours un nom, on utilise le symbole
        elif data.get('Error Message'):
            st.error(f"Erreur API: {data['Error Message']}")
            return 0.0, symbol
        else:
            return 0.0, symbol
            
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur de connexion lors de la récupération des données : {e}")
        return 0.0, "--"


# --- Fonction de Calcul et de Projection ---

def calculate_projection(start_value, growth_rate, multiple, years, desired_return, current_price, metric_label):
    """
    Calcule la juste valeur et le rendement annuel pour une projection.
    Retourne la juste valeur, le rendement actuel, et le DataFrame de projection.
    """
    try:
        # 1. Calculer la valeur future de la métrique (EPS ou FCFPS)
        future_metric = start_value * pow(1 + growth_rate, years)

        # 2. Calculer le prix futur de l'action
        future_stock_price = future_metric * multiple

        # 3. Calculer le prix d'entrée (Juste Valeur) pour le rendement souhaité
        just_value = future_stock_price / pow(1 + desired_return, years)

        # 4. Calculer le rendement annuel actuel
        current_annual_return = 0.0
        if current_price > 0:
            current_annual_return = (pow(future_stock_price / current_price, 1/years) - 1) * 100
        
        # 5. Créer le DataFrame de projection pour le graphique
        projection_data = []
        for year in range(years + 1):
            if year == 0:
                price_i = current_price if current_price > 0 else 0
                metric_i = start_value
            else:
                metric_i = start_value * pow(1 + growth_rate, year)
                price_i = metric_i * multiple
            
            projection_data.append({
                "Année": year,
                "Prix Projeté": price_i,
                metric_label: metric_i,
                "Type": "Prix Projeté",
            })
        
        df = pd.DataFrame(projection_data)
        
        # Ajout du prix futur cible et du prix actuel pour le graphique
        df_cible = pd.DataFrame([
            {"Année": 0, "Prix Projeté": current_price, metric_label: 0, "Type": "Prix Actuel"},
            {"Année": years, "Prix Projeté": future_stock_price, metric_label: 0, "Type": "Prix Cible"}
        ])
        df = pd.concat([df, df_cible]).sort_values("Année").reset_index(drop=True)

        return just_value, current_annual_return, df
    
    except Exception:
        # Retourne des valeurs par défaut en cas d'erreur de calcul (ex: division par zéro)
        return 0.0, 0.0, pd.DataFrame()


# --- Interface Utilisateur Streamlit ---

st.title("Calculateur de Juste Valeur (DCF)")
st.caption("Évaluation d'actions basée sur la projection de BPA et de FCF.")

# --- Section 1: Récupération du prix de l'action ---

st.header("1. Prix de l'action")

col1, col2 = st.columns([3, 1])

with col1:
    symbol = st.text_input("Symbole Boursier (Ticker) :", value="AAPL", max_chars=10).strip().upper()

with col2:
    st.markdown("<!-- Espace pour aligner le bouton -->")
    if st.button("Rechercher le prix"):
        with st.spinner(f"Récupération du prix pour {symbol}..."):
            price, name = fetch_stock_price(symbol, ALPHA_VANTAGE_API_KEY)
            st.session_state.current_price = price
            st.session_state.stock_name = name

# Affichage du prix actuel
st.info(f"**Prix actuel de l'action {st.session_state.stock_name}:** "
        f"{st.session_state.current_price:,.2f}{BASE_CURRENCY}")

# Entrée manuelle du prix
manual_price = st.number_input(
    f"OU Entrer le prix manuellement ({BASE_CURRENCY}):", 
    min_value=0.0, 
    value=st.session_state.current_price,
    format="%.2f",
    key="manual_price_input"
)
st.session_state.current_price = manual_price


# --- Section 2: Onglets d'évaluation ---

tab_eps, tab_fcf = st.tabs(["Bénéfice par Action (BPA/EPS)", "Flux de Trésorerie Disponibles (FCF)"])

# --- Onglet BPA (EPS) ---
with tab_eps:
    st.subheader("Paramètres d'évaluation BPA")

    col_a, col_b = st.columns(2)
    
    eps = col_a.number_input("Bénéfice par action (BPA/EPS):", value=7.50, min_value=0.0, format="%.2f", key="eps")
    eps_growth = col_b.slider("Taux de croissance du BPA (annuel, %):", min_value=1.0, max_value=25.0, value=10.0, step=0.1, key="eps_growth")
    
    pe_multiple = col_a.number_input("Multiple P/E approprié (Poids):", value=20.0, min_value=1.0, format="%.1f", key="pe_multiple")
    desired_return_eps = col_b.slider("Rendement annuel souhaité (%):", min_value=5.0, max_value=30.0, value=15.0, step=0.5, key="desired_return_eps")
    
    years = 5 # Nombre d'années de projection fixé

    # Calcul
    just_value_eps, current_return_eps, df_eps = calculate_projection(
        start_value=eps,
        growth_rate=eps_growth / 100,
        multiple=pe_multiple,
        years=years,
        desired_return=desired_return_eps / 100,
        current_price=st.session_state.current_price,
        metric_label="EPS Projeté"
    )

    st.markdown("---")
    st.subheader("Résultats et Projection sur 5 ans")

    col_res_a, col_res_b = st.columns(2)
    
    col_res_a.metric(
        label=f"Prix d'entrée pour un rendement de {desired_return_eps:.1f}%",
        value=f"{just_value_eps:,.2f} {BASE_CURRENCY}",
        delta="JUSTE VALEUR ESTIMÉE"
    )
    
    col_res_b.metric(
        label="Rendement annuel à partir du prix actuel",
        value=f"{current_return_eps:,.2f} %",
        delta=f"Objectif: {desired_return_eps:.1f}%",
        delta_color="normal" if current_return_eps >= desired_return_eps else "inverse"
    )

    if not df_eps.empty:
        # Création du graphique Plotly
        fig_eps = px.line(
            df_eps, 
            x="Année", 
            y="Prix Projeté", 
            color="Type",
            title="Projection du Prix de l'Action (basée sur le BPA)",
            markers=True
        )
        
        # Mise en évidence des points de départ et de fin
        fig_eps.update_traces(
            marker=dict(size=8), 
            selector=dict(mode='markers+lines')
        )
        
        st.plotly_chart(fig_eps, use_container_width=True)


# --- Onglet FCF (Flux de Trésorerie Disponibles) ---
with tab_fcf:
    st.subheader("Paramètres d'évaluation FCF")
    
    col_a, col_b = st.columns(2)
    
    fcfps = col_a.number_input("FCF par action (FCFPS):", value=39.50, min_value=0.0, format="%.2f", key="fcfps")
    fcf_growth = col_b.slider("Taux de croissance du FCF (annuel, %):", min_value=1.0, max_value=25.0, value=10.0, step=0.1, key="fcf_growth")
    
    pfcf_multiple = col_a.number_input("Multiple P/FCF approprié:", value=25.0, min_value=1.0, format="%.1f", key="pfcf_multiple")
    desired_return_fcf = col_b.slider("Rendement annuel souhaité (%):", min_value=5.0, max_value=30.0, value=15.0, step=0.5, key="desired_return_fcf")
    
    years = 5 # Nombre d'années de projection fixé

    # Calcul
    just_value_fcf, current_return_fcf, df_fcf = calculate_projection(
        start_value=fcfps,
        growth_rate=fcf_growth / 100,
        multiple=pfcf_multiple,
        years=years,
        desired_return=desired_return_fcf / 100,
        current_price=st.session_state.current_price,
        metric_label="FCFPS Projeté"
    )

    st.markdown("---")
    st.subheader("Résultats et Projection sur 5 ans")

    col_res_a, col_res_b = st.columns(2)
    
    col_res_a.metric(
        label=f"Prix d'entrée pour un rendement de {desired_return_fcf:.1f}%",
        value=f"{just_value_fcf:,.2f} {BASE_CURRENCY}",
        delta="JUSTE VALEUR ESTIMÉE"
    )
    
    col_res_b.metric(
        label="Rendement annuel à partir du prix actuel",
        value=f"{current_return_fcf:,.2f} %",
        delta=f"Objectif: {desired_return_fcf:.1f}%",
        delta_color="normal" if current_return_fcf >= desired_return_fcf else "inverse"
    )

    if not df_fcf.empty:
        # Création du graphique Plotly
        fig_fcf = px.line(
            df_fcf, 
            x="Année", 
            y="Prix Projeté", 
            color="Type",
            title="Projection du Prix de l'Action (basée sur le FCF)",
            markers=True
        )
        
        # Mise en évidence des points de départ et de fin
        fig_fcf.update_traces(
            marker=dict(size=8), 
            selector=dict(mode='markers+lines')
        )
        
        st.plotly_chart(fig_fcf, use_container_width=True)
