from flask import Flask, request
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LIEN_RDV = os.environ.get("LIEN_RDV")
LIEN_PAIEMENT = os.environ.get("LIEN_PAIEMENT")

chat_history = {}

SYSTEM_PROMPT = f"""Tu es Samira de DS Digital Hub. Services: Design, Web, IA, Marketing, Streaming, Photo. RDV: {LIEN_RDV}, Paiement: {LIEN_PAIEMENT}."""

@app.route("/", methods=["GET"])
def home():
    return "Samira en ligne ✅"

@app.route("/test", methods=["GET"])
def test():
    return "Samira fonctionne ✅"

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Erreur"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    try:
        if "messages" in data["entry"][0]["changes"][0]["value"]:
            msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
            txt = msg["text"]["body"]
            num = msg["from"]
            if num not in chat_history: chat_history[num] = [{"role": "system", "content": SYSTEM_PROMPT}]
            chat_history[num].append({"role": "user", "content": txt})
            res = requests.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini", "messages": chat_history[num][-10:]})
            reply = res.json()["choices"][0]["message"]["content"]
            requests.post(f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
                json={"messaging_product": "whatsapp", "to": num, "text": {"body": reply}})
    except: pass
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
