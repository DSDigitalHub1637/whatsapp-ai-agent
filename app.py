from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

# ==============================
# VARIABLES D'ENVIRONNEMENT
# ==============================

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # ✅ Nouvelle variable

LIEN_RDV = os.environ.get("LIEN_RDV", "Contactez-nous pour un RDV")
LIEN_PAIEMENT = os.environ.get("LIEN_PAIEMENT", "Contactez-nous pour payer")

# ==============================
# PROMPT SYSTEME - SAMIRA
# ==============================

SYSTEM_PROMPT = f"""
Tu es Samira, l'assistante commerciale officielle de DS Digital Hub.

DS Digital Hub est une agence spécialisée en :
- Design graphique
- Création de sites web
- Automatisation IA
- Marketing digital (création et gestion des réseaux sociaux pour entreprises et particuliers)
- Service de streaming professionnel
- Photographie professionnelle

Ton rôle est de :
1. Accueillir chaleureusement le client.
2. Identifier son besoin précis.
3. Poser des questions stratégiques pour comprendre son projet.
4. Proposer le service le plus adapté.
5. Orienter vers une prise de rendez-vous ou un paiement.
6. Rester concise (messages courts adaptés à WhatsApp).
7. Toujours terminer par une question pour faire avancer la conversation.

Tu es professionnelle, dynamique et rassurante.
Tu mets en avant la valeur et la qualité des services.
Tu ne dis jamais que tu es une IA.

Si le client veut un rendez-vous, donne ce lien ou info : {LIEN_RDV}
Si le client veut payer, donne ce lien ou info : {LIEN_PAIEMENT}
"""

# ==============================
# ROUTE ACCUEIL
# ==============================

@app.route("/", methods=["GET"])
def home():
    return "✅ Samira - DS Digital Hub est en ligne avec Gemini !"

# ==============================
# FONCTION GEMINI (REMPLACE OPENAI)
# ==============================

def get_gemini_response(user_message):
    """Appelle l'API Gemini pour obtenir une réponse"""
    
    if not GEMINI_API_KEY or GEMINI_API_KEY == "test":
        return "⚠️ GEMINI_API_KEY non configurée."
    
    try:
        # URL de l'API Gemini
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        params = {
            "key": GEMINI_API_KEY
        }
        
        data = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{SYSTEM_PROMPT}\n\nUser: {user_message}\nSamira:"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 2048
            }
        }
        
        response = requests.post(url, params=params, json=data, timeout=30)
        result = response.json()
        
        if "candidates" in result and len(result["candidates"]) > 0:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "Erreur Gemini: " + str(result)
            
    except Exception as e:
        return "Erreur: " + str(e)

# ==============================
# ROUTE TEST (SANS WHATSAPP)
# ==============================

@app.route("/test", methods=["GET"])
def test():
    if not GEMINI_API_KEY or GEMINI_API_KEY == "test":
        return "⚠️ GEMINI_API_KEY non configurée dans Render."
    
    reply = get_gemini_response("Bonjour, je veux créer un site web")
    return reply

# ==============================
# VERIFICATION WEBHOOK META
# ==============================

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Erreur de vérification", 403

# ==============================
# RECEPTION MESSAGE WHATSAPP
# ==============================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        from_number = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]

        # ===== Envoi vers Gemini =====
        reply = get_gemini_response(message)

        # ===== Envoi réponse WhatsApp =====
        requests.post(
            f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages",
            headers={
                "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "messaging_product": "whatsapp",
                "to": from_number,
                "text": {"body": reply}
            }
        )

    except Exception as e:
        print("Erreur :", e)

    return "ok"

# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
