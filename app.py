from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

# ==============================
# VARIABLES D’ENVIRONNEMENT
# ==============================

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

LIEN_RDV = os.environ.get("LIEN_RDV")
LIEN_PAIEMENT = os.environ.get("LIEN_PAIEMENT")

# ==============================
# PROMPT SYSTEME - SAMIRA
# ==============================

SYSTEM_PROMPT = f"""
Tu es Samira, l’assistante commerciale officielle de DS Digital Hub.

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

Si le client veut un rendez-vous, donne ce lien : {LIEN_RDV}
Si le client veut payer, donne ce lien : {LIEN_PAIEMENT}
"""

# ==============================
# ROUTE TEST (SANS WHATSAPP)
# ==============================

@app.route("/test", methods=["GET"])
def test():
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Bonjour je veux créer un site web"}
            ]
        }
    )

    result = response.json()
    return result["choices"][0]["message"]["content"]

# ==============================
# VERIFICATION WEBHOOK META
# ==============================

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Erreur de vérification"

# ==============================
# RECEPTION MESSAGE WHATSAPP
# ==============================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        from_number = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]

        # ===== Envoi vers OpenAI =====
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": message}
                ]
            }
        )

        reply = response.json()["choices"][0]["message"]["content"]

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