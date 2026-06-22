from flask import Flask, request, render_template_string, jsonify
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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

LIEN_RDV = os.environ.get("LIEN_RDV", "Contactez-nous pour un RDV")
LIEN_PAIEMENT = os.environ.get("LIEN_PAIEMENT", "Contactez-nous pour payer")

# ==============================
# MÉMOIRE DES CONVERSATIONS
# ==============================
# Dictionnaire qui stocke les conversations par utilisateur
# Format : { "user_id": [ {"role": "user", "text": "..."}, {"role": "model", "text": "..."} ] }
conversations = {}

# Nombre maximum de messages à garder en mémoire par utilisateur (pour économiser tokens)
MAX_HISTORY = 10

# ==============================
# PROMPT SYSTEME - SAMIRA
# ==============================

SYSTEM_PROMPT = f"""
Tu es Samira, l'assistante commerciale officielle de DS Digital Hub.

DS Digital Hub est une agence spécialisée en :
- Design graphique (logos, flyers, cartes de visite)
- Création de sites web
- Automatisation IA
- Marketing digital (création et gestion des réseaux sociaux)
- Service de streaming professionnel
- Photographie professionnelle

Ton rôle est de :
1. Accueillir chaleureusement le client.
2. Identifier son besoin précis en posant des questions stratégiques.
3. SE SOUVENIR de tout ce que le client a déjà dit dans la conversation.
4. Proposer le service le plus adapté.
5. Orienter vers une prise de rendez-vous ou un paiement.
6. Rester concise (messages courts adaptés à WhatsApp).
7. Toujours terminer par une question pour faire avancer la conversation.

Règles importantes :
- Tu es professionnelle, dynamique et rassurante.
- Tu mets en avant la valeur et la qualité des services.
- Tu ne dis JAMAIS que tu es une IA.
- Tu te souviens du contexte précédent et tu y fais référence.
- Tu personnalises tes réponses selon ce que le client t'a déjà dit.

Si le client veut un rendez-vous, donne ce lien ou info : {LIEN_RDV}
Si le client veut payer, donne ce lien ou info : {LIEN_PAIEMENT}
"""

# ==============================
# FONCTION GEMINI AVEC MÉMOIRE
# ==============================

def get_gemini_response(user_message, user_id="default"):
    """Appelle l'API Gemini avec l'historique de conversation"""
    
    if not GEMINI_API_KEY or GEMINI_API_KEY == "test":
        return "⚠️ GEMINI_API_KEY non configurée."
    
    try:
        # Récupérer ou créer l'historique de cet utilisateur
        if user_id not in conversations:
            conversations[user_id] = []
        
        # Ajouter le message de l'utilisateur à l'historique
        conversations[user_id].append({
            "role": "user",
            "parts": [{"text": user_message}]
        })
        
        # Limiter l'historique aux derniers MAX_HISTORY messages
        if len(conversations[user_id]) > MAX_HISTORY * 2:
            conversations[user_id] = conversations[user_id][-MAX_HISTORY * 2:]
        
        # URL de l'API Gemini
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
        
        params = {
            "key": GEMINI_API_KEY
        }
        
        # Construire la requête avec system_instruction + historique
        data = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": conversations[user_id],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024
            }
        }
        
        response = requests.post(url, params=params, json=data, timeout=30)
        result = response.json()
        
        if "candidates" in result and len(result["candidates"]) > 0:
            reply = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # Ajouter la réponse de Samira à l'historique
            conversations[user_id].append({
                "role": "model",
                "parts": [{"text": reply}]
            })
            
            return reply
        else:
            print("Erreur Gemini:", result)
            return "Désolée, je n'ai pas pu traiter votre demande. Pouvez-vous reformuler ?"
            
    except Exception as e:
        print("Erreur Gemini:", e)
        return "Désolée, une erreur technique est survenue. Réessayez dans un instant."

# ==============================
# ROUTE ACCUEIL
# ==============================

@app.route("/", methods=["GET"])
def home():
    return "✅ Samira - DS Digital Hub est en ligne avec mémoire !"

# ==============================
# ROUTE TEST
# ==============================

@app.route("/test", methods=["GET"])
def test():
    if not GEMINI_API_KEY:
        return "⚠️ GEMINI_API_KEY non configurée."
    reply = get_gemini_response("Bonjour, je veux créer un site web", "test_user")
    return reply

# ==============================
# ROUTE RESET MÉMOIRE
# ==============================

@app.route("/reset", methods=["GET"])
def reset_memory():
    """Permet de réinitialiser la mémoire d'un utilisateur (pour les tests)"""
    user_id = request.args.get("user", "default")
    if user_id in conversations:
        del conversations[user_id]
        return f"✅ Mémoire de '{user_id}' réinitialisée."
    return f"ℹ️ Aucune mémoire trouvée pour '{user_id}'."

# ==============================
# INTERFACE WEB CHAT
# ==============================

PAGE_CHAT = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Samira - DS Digital Hub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .chat-container {
            width: 100%;
            max-width: 500px;
            height: 90vh;
            background: white;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .chat-header {
            background: linear-gradient(135deg, #25d366 0%, #128c7e 100%);
            color: white;
            padding: 20px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .avatar {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: white;
            color: #25d366;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 24px;
            font-weight: bold;
        }
        .header-info h1 { font-size: 18px; margin-bottom: 3px; }
        .header-info p { font-size: 13px; opacity: 0.9; }
        .status-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #00ff00;
            border-radius: 50%;
            margin-right: 5px;
        }
        .reset-btn {
            margin-left: auto;
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 15px;
            cursor: pointer;
            font-size: 12px;
        }
        .reset-btn:hover { background: rgba(255,255,255,0.3); }
        .chat-box {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #f0f2f5;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .message {
            max-width: 75%;
            padding: 12px 16px;
            border-radius: 15px;
            word-wrap: break-word;
            animation: fadeIn 0.3s ease-in;
            line-height: 1.4;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.user {
            align-self: flex-end;
            background: #dcf8c6;
            color: #000;
            border-bottom-right-radius: 3px;
        }
        .message.bot {
            align-self: flex-start;
            background: white;
            color: #000;
            border-bottom-left-radius: 3px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        .typing {
            align-self: flex-start;
            background: white;
            padding: 12px 16px;
            border-radius: 15px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        .typing span {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #999;
            border-radius: 50%;
            margin: 0 2px;
            animation: bounce 1.4s infinite;
        }
        .typing span:nth-child(2) { animation-delay: 0.2s; }
        .typing span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes bounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-8px); }
        }
        .chat-input {
            display: flex;
            padding: 12px;
            background: white;
            border-top: 1px solid #eee;
            gap: 8px;
        }
        .chat-input input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #ddd;
            border-radius: 25px;
            outline: none;
            font-size: 15px;
        }
        .chat-input input:focus { border-color: #25d366; }
        .chat-input button {
            padding: 12px 20px;
            border: none;
            background: #25d366;
            color: white;
            font-size: 15px;
            cursor: pointer;
            border-radius: 25px;
            font-weight: 600;
            transition: background 0.2s;
        }
        .chat-input button:hover { background: #1ebe5d; }
        .chat-input button:disabled { background: #999; cursor: not-allowed; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <div class="avatar">S</div>
            <div class="header-info">
                <h1>Samira</h1>
                <p><span class="status-dot"></span>En ligne - DS Digital Hub</p>
            </div>
            <button class="reset-btn" onclick="resetChat()">🔄 Reset</button>
        </div>

        <div class="chat-box" id="chatBox">
            <div class="message bot">
                Bonjour 👋 Je suis Samira, l'assistante de DS Digital Hub. Comment puis-je vous aider aujourd'hui ?
            </div>
        </div>

        <div class="chat-input">
            <input type="text" id="userInput" placeholder="Écrivez votre message..." autocomplete="off">
            <button onclick="sendMessage()" id="sendBtn">Envoyer</button>
        </div>
    </div>

    <script>
        const chatBox = document.getElementById('chatBox');
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');

        // Générer un ID unique pour cette session
        let sessionId = localStorage.getItem('samira_session');
        if (!sessionId) {
            sessionId = 'web_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('samira_session', sessionId);
        }

        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        async function sendMessage() {
            const message = userInput.value.trim();
            if (!message) return;

            addMessage(message, 'user');
            userInput.value = '';
            sendBtn.disabled = true;

            const typingDiv = document.createElement('div');
            typingDiv.className = 'typing';
            typingDiv.id = 'typing';
            typingDiv.innerHTML = '<span></span><span></span><span></span>';
            chatBox.appendChild(typingDiv);
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const response = await fetch('/chat-api', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message, user_id: sessionId })
                });
                const data = await response.json();
                document.getElementById('typing').remove();
                addMessage(data.reply, 'bot');
            } catch (error) {
                document.getElementById('typing').remove();
                addMessage('Désolée, une erreur est survenue. Réessayez.', 'bot');
            }
            sendBtn.disabled = false;
            userInput.focus();
        }

        function addMessage(text, sender) {
            const div = document.createElement('div');
            div.className = `message ${sender}`;
            div.textContent = text;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        async function resetChat() {
            if (!confirm('Voulez-vous vraiment effacer cette conversation ?')) return;
            
            await fetch('/reset?user=' + sessionId);
            chatBox.innerHTML = '<div class="message bot">Bonjour 👋 Je suis Samira, l\\'assistante de DS Digital Hub. Comment puis-je vous aider aujourd\\'hui ?</div>';
            
            // Nouveau session ID
            sessionId = 'web_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('samira_session', sessionId);
        }
    </script>
</body>
</html>
"""

@app.route("/chat", methods=["GET"])
def chat_page():
    return render_template_string(PAGE_CHAT)

@app.route("/chat-api", methods=["POST"])
def chat_api():
    try:
        data = request.json
        message = data.get("message", "")
        user_id = data.get("user_id", "default")
        
        if not message:
            return jsonify({"reply": "Message vide."})
        
        reply = get_gemini_response(message, user_id)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": f"Erreur : {str(e)}"})

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

        # ===== Envoi vers Gemini avec mémoire (user_id = numéro WhatsApp) =====
        reply = get_gemini_response(message, user_id=from_number)

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
