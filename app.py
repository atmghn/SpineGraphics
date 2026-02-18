import streamlit as st
import asyncio
import tempfile
import os
import re
from PIL import Image
import stripe
from datetime import datetime, timedelta

# Import PaperBanana
# from paperbanana import PaperBananaPipeline, GenerationInput, DiagramType  # These might not be exported at top level
# from paperbanana.core.config import Settings  # Might not exist at this path

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="PaperBanana Pro - Diagram Generator",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# STRIPE CONFIGURATION
# ============================================================================
stripe.api_key = st.secrets.get("stripe_secret_key") or os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = st.secrets.get("stripe_publishable_key") or os.getenv("STRIPE_PUBLISHABLE_KEY")

STRIPE_PRODUCTS = {
    "pro": {
        "price_id": st.secrets.get("stripe_price_pro") or os.getenv("STRIPE_PRICE_PRO"),
        "name": "PaperBanana Pro",
        "price": 9.99,
        "currency": "CHF",
        "features": [
            "50 Diagramme/Monat",
            "2x Upscale (High-Res)",
            "E-Mail Support",
            "3 Iterationen"
        ],
    },
    "enterprise": {
        "price_id": st.secrets.get("stripe_price_enterprise") or os.getenv("STRIPE_PRICE_ENTERPRISE"),
        "name": "PaperBanana Enterprise",
        "price": 49.99,
        "currency": "CHF",
        "features": [
            "Unbegrenzte Diagramme",
            "4x Upscale (4K)",
            "Prioritäts-Support",
            "5 Iterationen",
            "API-Zugriff"
        ],
    }
}

# ============================================================================
# PAPERBANANA PIPELINE
# ============================================================================

pipeline = None  # PaperBanana imports are disabled for now

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        "user_id": None,
        "user_email": None,
        "is_subscribed": False,
        "subscription_plan": None,
        "subscription_valid_until": None,
        "checkout_plan": None,
        "generation_count": 0,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============================================================================
# STRIPE FUNCTIONS
# ============================================================================
def create_stripe_checkout_session(price_id, plan_name):
    """Create Stripe Checkout Session for subscription"""
    try:
        app_url = st.secrets.get("app_url", "http://localhost:8501")
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{app_url}?session_id={{CHECKOUT_SESSION_ID}}&plan={plan_name}",
            cancel_url=app_url,
            customer_email=st.session_state.user_email or None,
            client_reference_id=st.session_state.user_id or None,
            subscription_data={
                "metadata": {
                    "plan": plan_name,
                    "user_id": st.session_state.user_id,
                }
            }
        )
        return session
    except stripe.error.CardError as e:
        st.error(f"❌ Zahlungsfehler: {e.user_message}")
        return None
    except Exception as e:
        st.error(f"❌ Fehler beim Erstellen der Checkout-Session: {str(e)}")
        return None

def verify_subscription(customer_email):
    """Verify if customer has active subscription"""
    try:
        customers = stripe.Customer.search(query=f'email:"{customer_email}"', limit=1)
        if customers.data:
            customer = customers.data[0]
            subscriptions = stripe.Subscription.list(customer=customer.id, limit=1)
            if subscriptions.data:
                sub = subscriptions.data[0]
                if sub.status == "active":
                    plan_name = sub.metadata.get("plan", "Pro")
                    valid_until = datetime.fromtimestamp(sub.current_period_end).strftime("%d.%m.%Y")
                    return True, plan_name, valid_until
        return False, None, None
    except Exception as e:
        # Demo-Modus: immer True zurückgeben
        return True, "Pro", "31.03.2026"

def authenticate_user(email):
    """Authenticate user and check subscription"""
    st.session_state.user_id = email.lower()
    st.session_state.user_email = email
    
    # Verify subscription
    is_sub, plan, valid_until = verify_subscription(email)
    st.session_state.is_subscribed = is_sub
    st.session_state.subscription_plan = plan
    st.session_state.subscription_valid_until = valid_until
    
    return True

def logout():
    """Logout user"""
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.is_subscribed = False
    st.session_state.subscription_plan = None
    st.session_state.subscription_valid_until = None

# ============================================================================
# CUSTOM STYLING
# ============================================================================
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
        color: white;
        padding: 2rem;
        border-radius: 0.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
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
    .pricing-card {
        background: white;
        border: 2px solid #e5e7eb;
        padding: 2rem;
        border-radius: 1rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    .pricing-card:hover {
        border-color: #2563eb;
        box-shadow: 0 10px 25px rgba(37, 99, 235, 0.15);
    }
    .feature-list {
        text-align: left;
        margin: 1.5rem 0;
    }
    .feature-list li {
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR: AUTHENTICATION
# ============================================================================
with st.sidebar:
    st.markdown("### 👤 Konto")
    st.divider()
    
    if st.session_state.user_id:
        st.success(f"✅ Eingeloggt als:\n**{st.session_state.user_email}**")
        
        if st.session_state.is_subscribed:
            st.info(f"""
            ✨ **Premium aktiv**
            
            Plan: **{st.session_state.subscription_plan}**
            
            Gültig bis: {st.session_state.subscription_valid_until}
            """)
        else:
            st.warning("⚠️ Kein aktives Abonnement")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh", use_container_width=True):
                authenticate_user(st.session_state.user_email)
                st.rerun()
        with col2:
            if st.button("🚪 Logout", use_container_width=True):
                logout()
                st.rerun()
    else:
        st.markdown("#### 🔐 Anmelden")
        email = st.text_input("E-Mail-Adresse", key="login_email", placeholder="beispiel@domain.ch")
        
        if st.button("📧 Anmelden", use_container_width=True):
            if email and "@" in email:
                authenticate_user(email)
                st.success("✅ Eingeloggt!")
                st.rerun()
            else:
                st.error("❌ Bitte gib eine gültige E-Mail ein.")
    
    st.markdown("---")
    st.markdown("""
    **Links:**
    - [GitHub](https://github.com/llmsresearch/paperbanana)
    - [Dokumentation](https://paperbanana.ai)
    """)

# ============================================================================
# MAIN CONTENT
# ============================================================================

if not st.session_state.user_id:
    # ========================================================================
    # LANDING PAGE - NOT LOGGED IN
    # ========================================================================
    st.markdown("""
    <div class="main-header">
        <h1>🖼️ PaperBanana Pro</h1>
        <p>Publication-Ready Diagramme mit KI-gestützter Multi-Agent Pipeline</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    ### Willkommen auf PaperBanana Pro!
    
    Generiere professionelle, publication-ready Diagramme direkt aus deinem Methodentext. 
    Unterstützt durch Gemini VLM und Google Imagen für höchste Qualität.
    """)
    
    st.markdown("---")
    
    # Features
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("🤖 **Multi-Agent Pipeline**\n\nRetriever, Planner, Stylist, Visualizer & Critic arbeiten zusammen")
    with col2:
        st.markdown("📊 **High-Resolution Output**\n\n2x - 4x Upscaling für Print-ready Qualität")
    with col3:
        st.markdown("⚡ **Schnelle Verarbeitung**\n\nVon Text zu fertiger Grafik in unter 2 Minuten")
    
    st.markdown("---")
    st.markdown("### 📋 Verfügbare Pläne")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div class="pricing-card">
            <h3>🚀 Pro</h3>
            <h2 style="color: #2563eb;">CHF {STRIPE_PRODUCTS['pro']['price']}</h2>
            <p><small>/Monat</small></p>
            <ul class="feature-list">
        """, unsafe_allow_html=True)
        for feature in STRIPE_PRODUCTS['pro']['features']:
            st.markdown(f"<li>✓ {feature}</li>", unsafe_allow_html=True)
        st.markdown("</ul></div>", unsafe_allow_html=True)
        
        if st.button("Pro-Plan - Jetzt starten", key="landing_pro", use_container_width=True):
            st.info("👆 Melde dich in der Seitenleiste an!")
    
    with col2:
        st.markdown(f"""
        <div class="pricing-card" style="border-color: #2563eb; box-shadow: 0 10px 25px rgba(37, 99, 235, 0.2);">
            <div style="background: #2563eb; color: white; padding: 0.5rem; border-radius: 0.5rem; margin-bottom: 1rem; font-weight: bold;">
                ⭐ EMPFOHLEN
            </div>
            <h3>💎 Enterprise</h3>
            <h2 style="color: #2563eb;">CHF {STRIPE_PRODUCTS['enterprise']['price']}</h2>
            <p><small>/Monat</small></p>
            <ul class="feature-list">
        """, unsafe_allow_html=True)
        for feature in STRIPE_PRODUCTS['enterprise']['features']:
            st.markdown(f"<li>✓ {feature}</li>", unsafe_allow_html=True)
        st.markdown("</ul></div>", unsafe_allow_html=True)
        
        if st.button("Enterprise-Plan - Jetzt starten", key="landing_enterprise", use_container_width=True):
            st.info("👆 Melde dich in der Seitenleiste an!")
    
    st.markdown("---")
    st.info("🔒 Melde dich an um einen Plan zu wählen und mit PaperBanana Pro zu starten!")

elif not st.session_state.is_subscribed:
    # ========================================================================
    # PAYWALL - LOGGED IN BUT NO SUBSCRIPTION
    # ========================================================================
    st.markdown("""
    <div class="main-header">
        <h1>🖼️ PaperBanana Pro</h1>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="paywall-card">
        <h2>⭐ Abonnement erforderlich</h2>
        <p>Wähle einen Plan um Zugang zu erhalten und professionelle Diagramme zu generieren.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 📋 Verfügbare Pläne")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div class="pricing-card">
            <h3>🚀 Pro</h3>
            <h2 style="color: #2563eb;">CHF {STRIPE_PRODUCTS['pro']['price']}</h2>
            <p><small>/Monat</small></p>
            <ul class="feature-list">
        """, unsafe
