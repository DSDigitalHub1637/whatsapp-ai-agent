from flask import Flask, request
import requests
import os

app = Flask(__name__)

# ==============================
# VARIABLES D'ENVIRONNEMENT
# ==============================

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

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
- Marketing digital (création et gestion des réseaux sociaux)
- Service de streaming professionnel
- Photographie professionnelle

Ton rôle est de :
1. Accueillir chaleureusement
2. Comprendre le besoin du client
3. Poser des questions précises
4. Proposer les services adaptés
5. Orienter vers RDV ou paiement
6. Rester concise et professionnelle
7. Toujours terminer par une question

Tu es dynamique, rassurante et orientée solution.
Tu ne dis jamais que tu es une IA.
Si le client veut un RDV : {LIEN_RDV}
Si le client veut payer : {LIEN_PAIEMENT}
"""

# ==============================
# FONCTION GEMINI (CORRIGÉE)
# ==============================

def get_gemini_response(user_message):
    if not GEMINI_API_KEY:
        return "Désolée, je rencontre un problème technique pour le moment."

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [{
                "parts": [{"text": user_message}]
            }],
            "generationConfig": {
                "temperature": 0.75,
                "maxOutputTokens": 800
            }
        }

        response = requests.post(url, json=payload, timeout=20)
        result = response.json()

        if "candidates" in result and len(result["candidates"]) > 0:
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            print("Erreur Gemini API:", result)
            return "Désolée, je n'ai pas pu traiter votre message. Pouvez-vous réessayer ?"

    except Exception as e:
        print("Exception Gemini:", str(e))
        return "Désolée, une erreur est survenue. Pouvez-vous réessayer ?"


# ==============================
# ROUTES
# ==============================

@app.route("/", methods=["GET"])
def home():
    return "✅ Samira - DS Digital Hub est en ligne avec Gemini !"

@app.route("/test", methods=["GET"])
def test():
    reply = get_gemini_response("Bonjour, je veux créer un site web")
    return reply

# VERIFICATION WEBHOOK
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Token invalide", 403

# RÉCEPTION DES MESSAGES WHATSAPP
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        
        # Vérifier si c'est un message texte
        if "messages" in entry and entry["messages"][0]["type"] == "text":
            message = entry["messages"][0]["text"]["body"]
            from_number = entry["messages"][0]["from"]

            print(f"Message reçu de {from_number} : {message}")

            reply = get_gemini_response(message)
            print(f"Réponse de Samira : {reply}")

            # Envoi de la réponse via WhatsApp
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
                },
                timeout=10
            )
            print("Réponse envoyée à WhatsApp avec succès")

    except Exception as e:
        print("ERREUR dans webhook :", str(e))

    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
