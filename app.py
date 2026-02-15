import streamlit as st
import asyncio
import tempfile
import os
from paperbanana import PaperBananaPipeline, GenerationInput, DiagramType
from paperbanana.core.config import Settings

# Config laden (dein .env mit API-Key)
settings = Settings(vlm_provider="gemini", image_provider="google_imagen", refinement_iterations=3)
pipeline = PaperBananaPipeline(settings=settings)

st.title("🖼️ PaperBanana Diagram Generator")
st.markdown("Gib deinen Methodentext ein und generiere publication-ready Diagramme!")

# Eingaben
method_text = st.text_area("Methodentext (Paste hier rein):", height=200, placeholder="Unsere TLIF-Technik umfasst...")
caption = st.text_input("Caption:", placeholder="TLIF L5/S1 Übersicht")

if st.button("🚀 Diagramm generieren", type="primary"):
    if method_text and caption:
        with st.spinner("Generiere Diagramm... (Retriever → Planner → Stylist → Visualizer → Critic)"):
            # Temp-Datei für Input
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
                tmp.write(method_text)
                tmp_path = tmp.name
            
            # Async Generate
            @st.cache_data
            def generate_diag(input_path, cap):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    pipeline.generate(
                        GenerationInput(
                            source_context=open(input_path).read(),
                            communicative_intent=cap,
                            diagram_type=DiagramType.METHODOLOGY,
                        )
                    )
                )
                loop.close()
                return result.image_path
            
            img_path = generate_diag(tmp_path, caption)
            os.unlink(tmp_path)  # Temp löschen
            
            st.success("Fertig! 🎉")
            st.image(img_path, caption=caption)
            with open(img_path, "rb") as img_file:
                st.download_button("💾 PNG downloaden", img_file.read(), file_name=f"{caption}.png", mime="image/png")
    else:
        st.warning("Fülle Text und Caption aus!")

# Sidebar mit Repo-Info
with st.sidebar:
    st.markdown("[GitHub Repo](https://github.com/llmsresearch/paperbanana)")
    st.markdown("**Features:** Multi-Agent Pipeline, 3 Iterationen")
