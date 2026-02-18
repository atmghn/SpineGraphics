import streamlit as st
import asyncio
import tempfile
import os
import re
from PIL import Image
import stripe
from datetime import datetime, timedelta
import json

# ============================================================================
# STRIPE CONFIGURATION
# ============================================================================
# Die Keys werden aus secrets.toml oder Umgebungsvariablen geladen
stripe.api_key = st.secrets.get("stripe_secret_key") or os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = st.secrets.get("stripe_publishable_key") or os.getenv("STRIPE_PUBLISHABLE_KEY")

# Deine Stripe Produkt-IDs (später im Stripe Dashboard erstellen)
STRIPE_PRODUCTS = {
    "pro": {
        "price_id": st.secrets.get("stripe_price_pro") or os.getenv("STRIPE_PRICE_PRO"),
        "name": "PaperBanana Pro",
        "price": 9.99,
        "period": "month",
    },
    "enterprise": {
        "price_id": st.secrets.get("stripe_price_enterprise") or os.getenv("STRIPE_PRICE_ENTERPRISE"),
        "name": "PaperBanana Enterprise",
        "price": 49.99,
        "period": "month",
    }
}

# ============================================================================
# PAPERBANANA PIPELINE
# ============================================================================
from paperbanana import PaperBananaPipeline, GenerationInput, DiagramType
from paperbanana.core.config import Settings

settings = Settings(
    vlm_provider="gemini",
    image_provider="google_imagen",
    refinement_iterations=3,
)
pipeline = PaperBananaPipeline(settings=settings)

# ============================================================================
# SESSION STATE MANAGEMENT
# ============================================================================
def init_session_state():
    """Initialisiere Session-State Variablen"""
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "is_subscribed" not in st.session_state:
        st.session_state.is_subscribed = False
    if "subscription_plan" not in st.session_state:
        st.session_state.subscription_plan = None
    if "subscription_valid_until" not in st.session_state:
        st.session_state.subscription_valid_until = None

init_session_state()

# ============================================================================
# STRIPE AUTH & SUBSCRIPTION MANAGEMENT
# ============================================================================
def create_stripe_checkout_session(price_id, plan_name):
    """Erstelle eine Stripe Checkout-Session für ein Abonnement"""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=st.secrets.get("app_url") or "http://localhost:8501?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=st.secrets.get("app_url") or "http://localhost:8501",
            customer_email=st.session_state.user_email if st.session_state.user_email else None,
        )
        return session
    except stripe.error.CardError as e:
        st.error(f"Zahlungsfehler: {e.user_message}")
        return None
    except Exception as e:
        st.error(f"Fehler beim Erstellen der Checkout-Session: {str(e)}")
        return None

def check_subscription_status(customer_id):
    """Prüfe den aktuellen Subscription-Status eines Kunden"""
    try:
        subscriptions = stripe.Subscription.list(customer=customer_id, limit=1)
        if subscriptions.data:
            sub = subscriptions.data[0]
            if sub.status == "active":
                return True, sub.plan.nickname or "Pro"
            return False, None
        return False, None
    except Exception as e:
        st.error(f"Fehler beim Prüfen des Subscriptions: {e}")
        return False, None

def authenticate_user(email, password=None):
    """
    Authentifiziere einen User (vereinfacht mit Stripe-Integration).
    In einer echten App würde man hier OAuth2 oder Auth0 nutzen.
    """
    # Für diese Demo nutzen wir einfach die E-Mail als User-ID
    # In Production: Google OAuth, Supabase Auth, etc.
    st.session_state.user_id = email.lower()
    st.session_state.user_email = email
    return True

def logout():
    """Logout-Funktion"""
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.is_subscribed = False
    st.session_state.subscription_plan = None
    st.session_state.subscription_valid_until = None

# ============================================================================
# PAGE LAYOUT & STYLING
# ============================================================================
st.set_page_config(
    page_title="PaperBanana Pro - Diagram Generator",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS für besseres Branding
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
        color: white;
        padding: 2rem;
        border-radius: 0.5rem;
        margin-bottom: 2rem;
    }
    .subscription-banner {
        background: #dbeafe;
        border-left: 4px solid #2563eb;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 2rem;
    }
    .paywall-card {
        background: #fef3c7;
        border: 2px solid #f59e0b;
        padding: 2rem;
        border-radius: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# MAIN APP LOGIC
# ============================================================================

# Sidebar: Auth & Account
with st.sidebar:
    st.markdown("### 👤 Konto")
    
    if st.session_state.user_id:
        st.success(f"✅ Eingeloggt als: {st.session_state.user_email}")
        
        # Subscription-Status
        if st.session_state.is_subscribed:
            st.info(f"""
            ✨ **Premium-Abonnement aktiv**
            
            Plan: {st.session_state.subscription_plan}
            
            Gültig bis: {st.session_state.subscription_valid_until}
            """)
        else:
            st.warning("⚠️ Kein aktives Abonnement")
        
        if st.button("🚪 Logout"):
            logout()
            st.rerun()
    else:
        # Login Bereich
        st.markdown("#### Login oder Registrierung")
        
        email = st.text_input("E-Mail", key="login_email")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📧 Mit E-Mail anmelden"):
                if email:
                    authenticate_user(email)
                    st.session_state.is_subscribed = False
                    st.success("Eingeloggt! Wähle jetzt einen Plan.")
                    st.rerun()
                else:
                    st.error("Bitte gib eine E-Mail-Adresse ein.")
        
        with col2:
            if st.button("🔵 Google anmelden"):
                st.info("Google OAuth wird bald verfügbar!")
    
    st.markdown("---")
    st.markdown("[GitHub](https://github.com/llmsresearch/paperbanana) | [Docs](https://paperbanana.ai)")

# ============================================================================
# PAYWALL & PRICING
# ============================================================================

if not st.session_state.user_id:
    # User ist nicht eingeloggt
    st.markdown("""
    <div class="main-header">
        <h1>🖼️ PaperBanana Pro</h1>
        <p>Publication-Ready Diagramme mit KI</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.warning("👆 Bitte logge dich in der Seitenleiste ein, um zu beginnen.")
    
    st.markdown("---")
    st.markdown("## Verfügbare Pläne")
    
    cols = st.columns(2)
    
    with cols[0]:
        st.markdown("""
        ### 🚀 Pro
        **€9.99/Monat**
        
        ✓ 50 Diagramme/Monat
        ✓ Hochauflösende Ausgabe (2x)
        ✓ E-Mail-Support
        ✓ 3 Iterationen
        """)
        if st.button("Pro-Plan abonnieren", key="buy_pro"):
            st.session_state.checkout_plan = "pro"
            st.rerun()
    
    with cols[1]:
        st.markdown("""
        ### 💎 Enterprise
        **€49.99/Monat**
        
        ✓ Unbegrenzte Diagramme
        ✓ 4K Ausgabe (4x upscale)
        ✓ Prioritäts-Support
        ✓ 5 Iterationen
        ✓ API-Zugriff
        """)
        if st.button("Enterprise-Plan abonnieren", key="buy_enterprise"):
            st.session_state.checkout_plan = "enterprise"
            st.rerun()

elif not st.session_state.is_subscribed:
    # User ist eingeloggt, aber hat kein aktives Abonnement
    st.markdown("""
    <div class="main-header">
        <h1>🖼️ PaperBanana Pro</h1>
        <p>Publication-Ready Diagramme mit KI</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="paywall-card">
        <h2>⭐ Abonnement erforderlich</h2>
        <p>Wähle einen Plan, um die App freizuschalten und Diagramme zu generieren.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("## Verfügbare Pläne")
    
    cols = st.columns(2)
    
    with cols[0]:
        st.markdown("""
        ### 🚀 Pro
        **€9.99/Monat**
        
        ✓ 50 Diagramme/Monat
        ✓ Hochauflösende Ausgabe (2x)
        ✓ E-Mail-Support
        ✓ 3 Iterationen
        """)
        if st.button("Pro-Plan abonnieren", key="buy_pro_2"):
            session = create_stripe_checkout_session(
                STRIPE_PRODUCTS["pro"]["price_id"],
                "pro"
            )
            if session:
                st.markdown(f"[🔗 Zur Zahlung]({session.url})")
                st.info("Du wirst zu Stripe weitergeleitet. Nach der Zahlung kannst du die App nutzen.")

    with cols[1]:
        st.markdown("""
        ### 💎 Enterprise
        **€49.99/Monat**
        
        ✓ Unbegrenzte Diagramme
        ✓ 4K Ausgabe (4x upscale)
        ✓ Prioritäts-Support
        ✓ 5 Iterationen
        ✓ API-Zugriff
        """)
        if st.button("Enterprise-Plan abonnieren", key="buy_enterprise_2"):
            session = create_stripe_checkout_session(
                STRIPE_PRODUCTS["enterprise"]["price_id"],
                "enterprise"
            )
            if session:
                st.markdown(f"[🔗 Zur Zahlung]({session.url})")
                st.info("Du wirst zu Stripe weitergeleitet. Nach der Zahlung kannst du die App nutzen.")

else:
    # ========================================================================
    # MAIN APP - User ist eingeloggt UND hat Subscription
    # ========================================================================
    
    st.markdown("""
    <div class="main-header">
        <h1>🖼️ PaperBanana Pro</h1>
        <p>Publication-Ready Diagramme mit KI</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="subscription-banner">
        ✨ <strong>Premium aktiv</strong> | Plan: {} | Gültig bis: {}
    </div>
    """.format(
        st.session_state.subscription_plan,
        st.session_state.subscription_valid_until
    ), unsafe_allow_html=True)
    
    # Eingaben
    col1, col2 = st.columns([2, 1])
    
    with col1:
        method_text = st.text_area(
            "📝 Methodentext (Paste hier rein):",
            height=200,
            placeholder="Unsere TLIF-Technik umfasst folgende Schritte: 1) Patientenvorbereitung, 2) Zugangsweg, 3) Implantation..."
        )
    
    with col2:
        st.markdown("### ⚙️ Einstellungen")
        diagram_type = st.radio(
            "Diagramm-Typ:",
            ["METHODOLOGY", "FLOWCHART", "ARCHITECTURE"],
            horizontal=False
        )
    
    title = st.text_input(
        "Diagram Titel:",
        placeholder="Figure 1: TLIF-Verfahren Übersicht"
    )
    caption = st.text_input(
        "Caption:",
        placeholder="Schematische Darstellung der TLIF-Technik bei L5/S1"
    )
    
    if st.button("🚀 Diagramm generieren", type="primary", use_container_width=True):
        if method_text and title and caption:
            with st.spinner("⏳ Generiere Diagramm... (Retriever → Planner → Stylist → Visualizer → Critic)"):
                # Temp-Datei für Input
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
                    tmp.write(method_text)
                    tmp_path = tmp.name
                
                try:
                    # Async generate_fn
                    async def run_generation(path, cap, diag_type):
                        with open(path, 'r') as f:
                            text = f.read()
                        result = await pipeline.generate(
                            GenerationInput(
                                source_context=text,
                                communicative_intent=cap,
