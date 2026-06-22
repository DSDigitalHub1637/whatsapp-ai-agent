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
conversations = {}
MAX_HISTORY = 10

# ==============================
# PROMPT SYSTEME
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
    if not GEMINI_API_KEY or GEMINI_API_KEY == "test":
        return "⚠️ GEMINI_API_KEY non configurée."
    
    try:
        if user_id not in conversations:
            conversations[user_id] = []
        
        conversations[user_id].append({
            "role": "user",
            "parts": [{"text": user_message}]
        })
        
        if len(conversations[user_id]) > MAX_HISTORY * 2:
            conversations[user_id] = conversations[user_id][-MAX_HISTORY * 2:]
        
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
        params = {"key": GEMINI_API_KEY}
        
        data = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
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
            conversations[user_id].append({
                "role": "model",
                "parts": [{"text": reply}]
            })
            return reply
        else:
            print("Erreur Gemini:", result)
            if conversations[user_id]:
                conversations[user_id].pop()
            return "Désolée, je n'ai pas pu traiter votre demande. Pouvez-vous reformuler ?"
            
    except Exception as e:
        print("Erreur Gemini:", e)
        if user_id in conversations and conversations[user_id]:
            conversations[user_id].pop()
        return "Désolée, une erreur technique est survenue. Réessayez dans un instant."

# ==============================
# ROUTES
# ==============================

@app.route("/", methods=["GET"])
def home():
    return "✅ Samira - DS Digital Hub est en ligne avec mémoire !"

@app.route("/test", methods=["GET"])
def test():
    if not GEMINI_API_KEY:
        return "⚠️ GEMINI_API_KEY non configurée."
    reply = get_gemini_response("Bonjour, je veux créer un site web", "test_user")
    return reply

@app.route("/reset", methods=["GET"])
def reset_memory():
    user_id = request.args.get("user", "default")
    if user_id in conversations:
        del conversations[user_id]
        return f"✅ Mémoire de '{user_id}' réinitialisée."
    return f"ℹ️ Aucune mémoire trouvée pour '{user_id}'."

# ==============================
# INTERFACE WEB AVEC SIDEBAR
# ==============================

PAGE_CHAT = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Samira • DS Digital Hub</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        body {
            background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0f1729 100%);
            min-height: 100vh;
            overflow: hidden;
            color: white;
            position: relative;
        }

        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(circle at 20% 30%, rgba(59, 130, 246, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 80% 70%, rgba(99, 102, 241, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(139, 92, 246, 0.1) 0%, transparent 50%);
            animation: bgFlow 20s ease infinite;
            z-index: 0;
        }

        @keyframes bgFlow {
            0%, 100% { transform: scale(1) rotate(0deg); }
            50% { transform: scale(1.1) rotate(180deg); }
        }

        .app-container {
            position: relative;
            z-index: 1;
            height: 100vh;
            display: flex;
        }

        /* ====================== */
        /* SIDEBAR GAUCHE        */
        /* ====================== */
        .sidebar {
            width: 280px;
            background: rgba(10, 14, 39, 0.7);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            flex-direction: column;
            padding: 24px 20px;
            overflow-y: auto;
        }

        .sidebar-header {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 32px;
        }

        .logo-container {
            position: relative;
            width: 50px;
            height: 50px;
        }

        .logo-halo {
            position: absolute;
            top: -3px;
            left: -3px;
            right: -3px;
            bottom: -3px;
            background: linear-gradient(135deg, #3b82f6, #6366f1, #8b5cf6);
            border-radius: 14px;
            opacity: 0.6;
            filter: blur(10px);
            animation: halo 3s ease-in-out infinite;
        }

        @keyframes halo {
            0%, 100% { opacity: 0.4; transform: scale(1); }
            50% { opacity: 0.8; transform: scale(1.1); }
        }

        .logo-ds {
            position: relative;
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 22px;
            color: white;
            letter-spacing: -1px;
            box-shadow: 0 4px 20px rgba(59, 130, 246, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.15);
        }

        .brand-info h2 {
            font-size: 18px;
            font-weight: 800;
            color: white;
            letter-spacing: -0.3px;
        }

        .brand-info p {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.5);
            margin-top: 2px;
        }

        .sidebar-title {
            font-size: 11px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.5);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 14px;
            padding-left: 4px;
        }

        .services-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 24px;
        }

        .service-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 14px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
            color: rgba(255, 255, 255, 0.85);
            font-size: 14px;
            font-weight: 500;
            text-align: left;
            width: 100%;
        }

        .service-item:hover {
            background: rgba(59, 130, 246, 0.15);
            border-color: rgba(59, 130, 246, 0.4);
            color: white;
            transform: translateX(4px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
        }

        .service-icon {
            font-size: 18px;
            min-width: 24px;
        }

        .new-chat-btn {
            margin-top: auto;
            padding: 14px;
            background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
            color: white;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: all 0.2s;
            box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
        }

        .new-chat-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(59, 130, 246, 0.5);
        }

        /* ====================== */
        /* ZONE PRINCIPALE        */
        /* ====================== */
        .main-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
        }

        .chat-header {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 20px 24px;
            background: rgba(15, 23, 42, 0.5);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }

        .header-avatar {
            width: 42px;
            height: 42px;
            border-radius: 50%;
            background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 16px;
            color: white;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        .header-info {
            flex: 1;
        }

        .header-info h1 {
            font-size: 17px;
            font-weight: 700;
            color: white;
        }

        .header-info .status {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.6);
            display: flex;
            align-items: center;
            gap: 6px;
            margin-top: 2px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 12px #10b981;
            animation: pulse 2s ease infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.6; transform: scale(1.2); }
        }

        .chat-box {
            flex: 1;
            overflow-y: auto;
            padding: 24px 32px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            scroll-behavior: smooth;
        }

        .chat-box::-webkit-scrollbar { width: 6px; }
        .chat-box::-webkit-scrollbar-track { background: transparent; }
        .chat-box::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
        }
        .chat-box::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .message {
            max-width: 70%;
            padding: 14px 18px;
            border-radius: 18px;
            word-wrap: break-word;
            line-height: 1.5;
            font-size: 15px;
            animation: slideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(15px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            align-self: flex-end;
            background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
            color: white;
            border-bottom-right-radius: 4px;
            box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
        }

        .message.bot {
            align-self: flex-start;
            background: rgba(255, 255, 255, 0.06);
            backdrop-filter: blur(10px);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-bottom-left-radius: 4px;
        }

        .typing {
            align-self: flex-start;
            background: rgba(255, 255, 255, 0.06);
            backdrop-filter: blur(10px);
            padding: 16px 20px;
            border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            gap: 5px;
            align-items: center;
        }

        .typing span {
            width: 8px;
            height: 8px;
            background: rgba(255, 255, 255, 0.5);
            border-radius: 50%;
            animation: typingBounce 1.4s infinite ease-in-out;
        }

        .typing span:nth-child(2) { animation-delay: 0.2s; }
        .typing span:nth-child(3) { animation-delay: 0.4s; }

        @keyframes typingBounce {
            0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
            30% { transform: translateY(-8px); opacity: 1; }
        }

        .input-area {
            padding: 16px 32px 24px;
            background: rgba(15, 23, 42, 0.5);
            backdrop-filter: blur(20px);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        }

        .input-wrapper {
            display: flex;
            gap: 10px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 6px;
            transition: all 0.2s;
        }

        .input-wrapper:focus-within {
            border-color: rgba(59, 130, 246, 0.5);
            background: rgba(255, 255, 255, 0.08);
            box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1);
        }

        .input-wrapper input {
            flex: 1;
            padding: 12px 16px;
            background: transparent;
            border: none;
            outline: none;
            color: white;
            font-size: 15px;
            font-family: inherit;
        }

        .input-wrapper input::placeholder {
            color: rgba(255, 255, 255, 0.4);
        }

        .send-btn {
            width: 44px;
            height: 44px;
            border: none;
            background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
            color: white;
            border-radius: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        .send-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5);
        }

        .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .send-btn svg { width: 20px; height: 20px; }

        .footer-info {
            text-align: center;
            margin-top: 12px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.4);
        }

        /* MOBILE - Sidebar disparaît */
        @media (max-width: 768px) {
            .sidebar {
                display: none;
            }
            .mobile-menu-btn {
                display: flex !important;
            }
            .chat-box { padding: 18px; }
            .input-area { padding: 14px 18px 20px; }
            .message { max-width: 85%; font-size: 14px; }
        }

        .mobile-menu-btn {
            display: none;
            width: 40px;
            height: 40px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 
