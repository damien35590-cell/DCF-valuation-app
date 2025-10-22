import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. FONCTION DE CALCUL DCF ---
def calculer_dcf(fcf_actuel, croissance_annuelle, wacc, annees_projection, multiple_terminal):
    """Calcule la valeur intrinsèque de l'action selon la méthode DCF."""
    annees = np.arange(1, annees_projection + 1)
    df = pd.DataFrame({'Année': annees})

    # Projection du FCF
    df['FCF Projeté'] = fcf_actuel * (1 + croissance_annuelle) ** df['Année']

    # Facteur et Valeur Actuelle
    df['Facteur d\'Actualisation'] = 1 / (1 + wacc) ** df['Année']
    df['VA du FCF (Actualisée)'] = df['FCF Projeté'] * df['Facteur d\'Actualisation']

    # Calcul de la Valeur Terminale (VT)
    fcf_derniere_annee = df['FCF Projeté'].iloc[-1]
    valeur_terminale = fcf_derniere_annee * multiple_terminal
    
    facteur_actualisation_terminal = 1 / (1 + wacc) ** annees_projection
    va_terminale = valeur_terminale * facteur_actualisation_terminal

    # Résultat Final
    somme_va_fcf = df['VA du FCF (Actualisée)'].sum()
    valeur_intrinsèque = somme_va_fcf + va_terminale

    return valeur_intrinsèque, df

# --- 2. FONCTION POUR RÉCUPÉRER LE FCF VIA YFINANCE ---
@st.cache_data
def get_stock_data(ticker):
    """Récupère le FCF (Annuel) et le nombre d'actions pour le DCF."""
    try:
        stock = yf.Ticker(ticker)
        
        # Le FCF n'est pas toujours disponible directement, on utilise Cashflow Statement (freeCashFlow)
        cf_statement = stock.cashflow
        if 'Free Cash Flow' in cf_statement.index:
            # Récupère le FCF de la dernière année (colonne la plus à gauche)
            fcf_total = cf_statement.loc['Free Cash Flow'].iloc[0]
        else:
             st.error("Free Cash Flow non trouvé. Veuillez saisir le FCF manuellement.")
             return None, None
        
        # Récupère le nombre d'actions (shares outstanding)
        # Utiliser la méthode info pour la capitalisation et diviser par le prix (moins précis)
        # Ou utiliser 'sharesOutstanding' du dictionnaire info (plus direct)
        shares_outstanding = stock.info.get('sharesOutstanding')
        
        if fcf_total and shares_outstanding:
            fcf_par_action = fcf_total / shares_outstanding
            return fcf_par_action, stock.info.get('currentPrice')
        
        st.error("Impossible de récupérer le nombre d'actions. Saisissez les données manuellement.")
        return None, None

    except Exception as e:
        st.error(f"Erreur lors de la récupération des données pour '{ticker}'. Vérifiez le symbole boursier.")
        return None, None


# --- 3. INTERFACE STREAMLIT ---
st.set_page_config(layout="wide", page_title="DCF Valorisation Dynamique")

st.title("💸 DCF Valorisation Dynamique")
st.markdown("Utilisez un symbole boursier pour récupérer automatiquement les données financières (via Yahoo Finance).")

col1, col2 = st.columns(2)

with col1:
    st.header("Entrées Dynamiques")
    ticker = st.text_input("Symbole Boursier (Ex: AAPL, MSFT, AIR.PA)", 'MSFT').upper()
    
    fcf_initial = 0.0
    prix_actuel = None

    if ticker:
        fcf_retrieved, prix_actuel = get_stock_data(ticker)
        
        if fcf_retrieved is not None:
            fcf_initial = fcf_retrieved
            st.success(f"FCF Annuel par Action récupéré : {fcf_initial:.2f} $")
            st.info(f"Prix actuel de l'action : {prix_actuel:.2f} $")
        else:
            st.warning("Échec de la récupération automatique du FCF par action.")

    # Widgets pour les hypothèses ajustables
    fcf_man_input = st.number_input("FCF par Action de Base (saisie manuelle ou récupéré)", 
                                    value=float(fcf_initial), format="%.2f")
    
    croissance_annuelle = st.slider("Taux de Croissance Annuel FCF (%)", min_value=1.0, max_value=20.0, value=5.0, step=0.5) / 100
    wacc = st.slider("Taux d'Actualisation / WACC (%)", min_value=5.0, max_value=15.0, value=10.0, step=0.5) / 100
    annees_projection = st.slider("Années de Projection", min_value=5, max_value=15, value=10, step=1)
    multiple_terminal = st.slider("Multiple de Valeur Terminale (x FCF)", min_value=5.0, max_value=15.0, value=10.0, step=0.5)

    if st.button("Calculer la Valorisation"):
        if fcf_man_input > 0 and wacc > 0:
            valeur_intrinsèque, df_proj = calculer_dcf(
                fcf_man_input, croissance_annuelle, wacc, annees_projection, multiple_terminal
            )

            with col2:
                st.header("Résultats et Analyse")
                
                # Affichage du résultat principal (DCF)
                st.markdown(
                    f"""
                    <div style="padding: 15px; border-radius: 10px; background-color: #34495e; color: white; text-align: center;">
                        <h3 style="margin: 0; color: #f1c40f;">VALEUR INTRINSÈQUE ESTIMÉE</h3>
                        <p style="font-size: 3em; font-weight: bold; margin: 5px 0 0 0; color: #f1c40f;">
                            {valeur_intrinsèque:.2f} $
                        </p>
                    </div>
                    """, unsafe_allow_html=True
                )
                
                # Comparaison avec le prix actuel
                if prix_actuel:
                    difference = valeur_intrinsèque - prix_actuel
                    pourcentage = (difference / prix_actuel) * 100
                    couleur = "green" if difference > 0 else "red"
                    st.markdown(f"**Prix Actuel :** {prix_actuel:.2f} $")
                    st.markdown(f"**Potentiel :** <span style='color:{couleur}; font-weight:bold;'>{pourcentage:.2f} %</span>", unsafe_allow_html=True)


                # Graphique interactif (Plotly)
                fig = px.bar(
                    df_proj, 
                    x='Année', 
                    y='FCF Projeté', 
                    title='Projection des FCF (Flux de Trésorerie Projetés)',
                    template='plotly_white'
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Veuillez saisir un FCF par action et un WACC valides.")