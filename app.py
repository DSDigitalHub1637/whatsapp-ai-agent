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
# ROUTE CHAT WEB (INTERFACE) - AJOUTÉ
# ==============================

@app.route("/chat", methods=["GET"])
def chat_page():
    # Retourne une page HTML avec l'interface de chat
    html = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Samira - Chat en direct</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .chat-container {
            width: 100%;
            max-width: 500px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 600px;
        }
        .chat-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .chat-header h1 {
            font-size: 24px;
            margin-bottom: 5px;
        }
        .chat-header p {
            font-size: 14px;
            opacity: 0.9;
        }
        .chat-messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #f9f9f9;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .message {
            max-width: 80%;
            padding: 12px 16px;
            border-radius: 15px;
            word-wrap: break-word;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.bot {
            align-self: flex-start;
            background: #e9e9e9;
            color: #000;
            border-bottom-left-radius: 5px;
        }
        .message.user {
            align-self: flex-end;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-bottom-right-radius: 5px;
        }
        .typing-indicator {
            align-self: flex-start;
            background: #e9e9e9;
            padding: 12px 16px;
            border-radius: 15px;
            display: none;
        }
        .typing-indicator span {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #999;
            border-radius: 50%;
            margin: 0 2px;
            animation: typing 1.4s infinite;
        }
        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-5px); }
        }
        .chat-input-container {
            padding: 20px;
            border-top: 1px solid #eee;
            display: flex;
            gap: 10px;
            background: white;
        }
        .chat-input-container input {
            flex: 1;
            padding: 15px;
            border: 2px solid #ddd;
            border-radius: 25px;
            outline: none;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .chat-input-container input:focus {
            border-color: #667eea;
        }
        .chat-input-container button {
            padding: 15px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: transform 0.2s;
        }
        .chat-input-container button:hover {
            transform: scale(1.05);
        }
        .chat-input-container button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>💬 Samira</h1>
            <p>Assistante IA de DS Digital Hub</p>
        </div>
        <div class="chat-messages" id="messages">
            <div class="message bot">Bonjour ! Je suis Samira, l'assistante commerciale de DS Digital Hub. Comment puis-je vous aider aujourd'hui ?</div>
        </div>
        <div class="typing-indicator" id="typingIndicator">
            <span></span><span></span><span></span>
        </div>
        <div class="chat-input-container">
            <input type="text" id="userInput" placeholder="Écrivez votre message..." onkeypress="handleKeyPress(event)">
            <button onclick="sendMessage()" id="sendBtn">Envoyer</button>
        </div>
    </div>

    <script>
        const messagesDiv = document.getElementById('messages');
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        const typingIndicator = document.getElementById('typingIndicator');

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }

        function showTyping() {
            typingIndicator.style.display = 'block';
            scrollToBottom();
        }

        function hideTyping() {
            typingIndicator.style.display = 'none';
        }

        function scrollToBottom() {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function addMessage(text, sender) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}`;
            messageDiv.textContent = text;
            messagesDiv.appendChild(messageDiv);
            scrollToBottom();
        }

        async function sendMessage() {
            const message = userInput.value.trim();
            if (!message) return;

            // Afficher le message utilisateur
            addMessage(message, 'user');
            userInput.value = '';
            sendBtn.disabled = true;

            // Montrer l'indicateur de frappe
            showTyping();

            try {
                // Appeler notre API /api/chat avec le message
                const response = await fetch('/api/chat?message=' + encodeURIComponent(message));
                const data = await response.json();
                
                hideTyping();
                addMessage(data.response, 'bot');
            } catch (error) {
                hideTyping();
                addMessage("Désolé, une erreur est survenue. Veuillez réessayer.", 'bot');
                console.error('Error:', error);
            }

            sendBtn.disabled = false;
            userInput.focus();
        }

        // Scroll au bas lors du chargement
        window.onload = function() {
            scrollToBottom();
        };
    </script>
</body>
</html>
"""
    
    return html

# Route API pour que le frontend puisse appeler Samira
@app.route("/api/chat", methods=["GET"])
def api_chat():
    user_message = request.args.get("message", "")
    if not user_message:
        return {"response": "Aucun message reçu."}
    
    # Utiliser la fonction get_gemini_response que nous avons déjà
    reply = get_gemini_response(user_message)
    return {"response": reply}

# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
