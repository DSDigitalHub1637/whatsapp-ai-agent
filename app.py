from flask import Flask, request, render_template_string, jsonify, session, redirect, url_for
import requests
import os
import json
import jwt
from functools import wraps
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "samira-ds-hub-secret-2026")

# ==============================
# VARIABLES D'ENVIRONNEMENT
# ==============================

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

LIEN_RDV = os.environ.get("LIEN_RDV", "Contactez-nous pour un RDV")
LIEN_PAIEMENT = os.environ.get("LIEN_PAIEMENT", "Contactez-nous pour payer")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://fzjqtmjnhykejojeesmh.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_SERVICE_KEY else None

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
# AUTHENTIFICATION & SUPABASE
# ==============================

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

def save_to_supabase(user_id, role, content):
    if not supabase:
        return
    try:
        conv = supabase.table("conversations").select("id").eq("user_id", user_id).eq("status", "active").limit(1).execute()
        if conv.data:
            conversation_id = conv.data[0]["id"]
        else:
            new_conv = supabase.table("conversations").insert({
                "user_id": user_id,
                "title": "Conversation avec Samira",
                "status": "active",
                "topic_type": "general"
            }).execute()
            conversation_id = new_conv.data[0]["id"]
        
        supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "role": role,
            "content": content
        }).execute()
    except Exception as e:
        print(f"Erreur Supabase: {e}")

# ==============================
# ROUTES
# ==============================

@app.route("/", methods=["GET"])
def home():
    if session.get("user"):
        return redirect(url_for("chat_page"))
    return redirect(url_for("login_page"))

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
# ROUTES AUTHENTIFICATION
# ==============================

@app.route("/login")
def login_page():
    return render_template_string(PAGE_LOGIN)

@app.route("/auth/google")
def auth_google():
    redirect_url = url_for("auth_callback", _external=True)
    auth_url = f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={redirect_url}"
    return redirect(auth_url)

@app.route("/auth/callback")
def auth_callback():
    return render_template_string(PAGE_CALLBACK)

@app.route("/auth/set-session", methods=["POST"])
def set_session_route():
    try:
        data = request.json
        access_token = data.get("access_token")
        if not access_token:
            return jsonify({"error": "No token"}), 400
        
        decoded = jwt.decode(access_token, options={"verify_signature": False})
        user_id = decoded.get("sub")
        email = decoded.get("email")
        
        display_name = email
        avatar_url = None
        if supabase:
            try:
                user_info = supabase.table("users").select("*").eq("id", user_id).execute()
                if user_info.data:
                    display_name = user_info.data[0].get("display_name") or email
                    avatar_url = user_info.data[0].get("avatar_url")
            except Exception as e:
                print(f"Info user: {e}")
        
        session["user"] = {
            "id": user_id,
            "email": email,
            "name": display_name,
            "avatar": avatar_url
        }
        return jsonify({"success": True})
    except Exception as e:
        print(f"Erreur set_session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/auth/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ==============================
# PAGE LOGIN
# ==============================

PAGE_LOGIN = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connexion • DS Digital Hub</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; font-family:'Inter',sans-serif; }
        body {
            background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0f1729 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            padding: 20px;
        }
        .login-card {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            padding: 50px 40px;
            border-radius: 24px;
            text-align: center;
            max-width: 420px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
        }
        .logo-ds {
            width: 80px; height: 80px;
            background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
            border-radius: 18px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 800; font-size: 32px;
            margin: 0 auto 24px;
            box-shadow: 0 8px 30px rgba(59,130,246,0.4);
        }
        h1 { font-size: 26px; margin-bottom: 8px; font-weight: 800; }
        p { color: rgba(255,255,255,0.6); margin-bottom: 32px; font-size: 15px; line-height: 1.5; }
        .google-btn {
            display: inline-flex; align-items: center; gap: 12px;
            background: white; color: #1a1f3a;
            padding: 14px 28px; border-radius: 12px;
            text-decoration: none; font-weight: 600;
            transition: all 0.2s;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        }
        .google-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
        .google-btn img { width: 22px; height: 22px; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo-ds">DS</div>
        <h1>Bienvenue chez DS Digital Hub</h1>
        <p>Connectez-vous pour discuter avec Samira, votre assistante IA personnelle</p>
        <a href="/auth/google" class="google-btn">
            <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="Google">
            Se connecter avec Google
        </a>
    </div>
</body>
</html>
"""

PAGE_CALLBACK = """
<!DOCTYPE html>
<html>
<head>
    <title>Connexion en cours...</title>
    <meta charset="UTF-8">
</head>
<body style="background:#0a0e27;color:white;font-family:sans-serif;text-align:center;padding:50px;">
    <h2>Connexion en cours...</h2>
    <p>Veuillez patienter, vous allez être redirigé.</p>
    <script>
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        const accessToken = params.get('access_token');
        
        if (accessToken) {
            fetch('/auth/set-session', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({access_token: accessToken})
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    window.location.href = '/chat';
                } else {
                    document.body.innerHTML = '<h2>Erreur : ' + (data.error || 'inconnue') + '</h2><a href="/login" style="color:#3b82f6;">Réessayer</a>';
                }
            }).catch(err => {
                document.body.innerHTML = '<h2>Erreur de connexion</h2><a href="/login" style="color:#3b82f6;">Réessayer</a>';
            });
        } else {
            document.body.innerHTML = '<h2>Erreur : token non reçu</h2><a href="/login" style="color:#3b82f6;">Réessayer</a>';
        }
    </script>
</body>
</html>
"""

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

        .user-info {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            background: rgba(255,255,255,0.04);
            border-radius: 12px;
            margin-top: 12px;
        }

        .user-avatar {
            width: 36px; height: 36px;
            border-radius: 50%;
            background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 14px;
            overflow: hidden;
        }
        .user-avatar img { width: 100%; height: 100%; object-fit: cover; }

        .user-details { flex: 1; min-width: 0; }
        .user-name { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .user-email { font-size: 11px; color: rgba(255,255,255,0.5); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

        .logout-btn {
            background: none; border: none; color: rgba(255,255,255,0.6);
            cursor: pointer; padding: 6px; border-radius: 8px;
            transition: all 0.2s;
        }
        .logout-btn:hover { background: rgba(239,68,68,0.15); color: #ef4444; }

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

        .header-info { flex: 1; }

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
        .chat-box::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 10px; }
        .chat-box::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }

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

        .input-wrapper input::placeholder { color: rgba(255, 255, 255, 0.4); }

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

        @media (max-width: 768px) {
            .sidebar { display: none; }
            .chat-box { padding: 18px; }
            .input-area { padding: 14px 18px 20px; }
            .message { max-width: 85%; font-size: 14px; }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <aside class="sidebar">
            <div class="sidebar-header">
                <div class="logo-container">
                    <div class="logo-halo"></div>
                    <div class="logo-ds"><span style="font-style:italic">D</span><span>S</span></div>
                </div>
                <div class="brand-info">
                    <h2>DS Digital Hub</h2>
                    <p>Assistant Samira</p>
                </div>
            </div>

            <div class="sidebar-title">Nos Services</div>
            <div class="services-list">
                <button class="service-item" onclick="sendSuggestion('Je veux créer un site web pour mon entreprise')">
                    <span class="service-icon">🌐</span>
                    <span>Créer un site web</span>
                </button>
                <button class="service-item" onclick="sendSuggestion('Je veux un logo professionnel')">
                    <span class="service-icon">🎨</span>
                    <span>Logo & Design</span>
                </button>
                <button class="service-item" onclick="sendSuggestion('Je veux gérer mes réseaux sociaux')">
                    <span class="service-icon">📱</span>
                    <span>Réseaux sociaux</span>
                </button>
                <button class="service-item" onclick="sendSuggestion('Je veux des photos professionnelles')">
                    <span class="service-icon">📸</span>
                    <span>Photographie</span>
                </button>
                <button class="service-item" onclick="sendSuggestion('Je veux automatiser mon business avec IA')">
                    <span class="service-icon">🤖</span>
                    <span>Automatisation IA</span>
                </button>
                <button class="service-item" onclick="sendSuggestion('Je veux un service de streaming')">
                    <span class="service-icon">🎬</span>
                    <span>Streaming pro</span>
                </button>
            </div>

            <button class="new-chat-btn" onclick="resetChat()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <line x1="12" y1="5" x2="12" y2="19"/>
                    <line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                Nouvelle conversation
            </button>

            <div class="user-info">
                <div class="user-avatar">
                    {% if user.avatar %}
                        <img src="{{ user.avatar }}" alt="avatar">
                    {% else %}
                        {{ user.name[0]|upper }}
                    {% endif %}
                </div>
                <div class="user-details">
                    <div class="user-name">{{ user.name }}</div>
                    <div class="user-email">{{ user.email }}</div>
                </div>
                <a href="/auth/logout" class="logout-btn" title="Déconnexion">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                        <polyline points="16 17 21 12 16 7"/>
                        <line x1="21" y1="12" x2="9" y2="12"/>
                    </svg>
                </a>
            </div>
        </aside>

        <main class="main-area">
            <div class="chat-header">
                <div class="header-avatar">S</div>
                <div class="header-info">
                    <h1>Samira</h1>
                    <div class="status">
                        <span class="status-dot"></span>
                        En ligne maintenant
                    </div>
                </div>
            </div>

            <div class="chat-box" id="chatBox">
                <div class="message bot">
                    Bonjour {{ user.name.split(' ')[0] }} 👋 Je suis <strong>Samira</strong>, votre assistante chez <strong>DS Digital Hub</strong>.<br><br>
                    Choisissez un service à gauche ou posez-moi directement votre question. Comment puis-je vous aider à booster votre business aujourd'hui ?
                </div>
            </div>

            <div class="input-area">
                <div class="input-wrapper">
                    <input type="text" id="userInput" placeholder="Posez votre question à Samira..." autocomplete="off">
                    <button class="send-btn" id="sendBtn" onclick="sendMessage()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13"/>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                        </svg>
                    </button>
                </div>
                <div class="footer-info">
                    Powered by DS Digital Hub • Samira IA
                </div>
            </div>
        </main>
    </div>

    <script>
        const chatBox = document.getElementById('chatBox');
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');

        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        function sendSuggestion(text) {
            userInput.value = text;
            sendMessage();
        }

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
                    body: JSON.stringify({ message: message })
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
            div.innerHTML = text.replace(/\\n/g, '<br>');
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        async function resetChat() {
            if (!confirm('Démarrer une nouvelle conversation ?')) return;
            location.reload();
        }
    </script>
</body>
</html>
"""

@app.route("/chat", methods=["GET"])
@require_auth
def chat_page():
    user = session.get("user")
    return render_template_string(PAGE_CHAT, user=user)

@app.route("/chat-api", methods=["POST"])
@require_auth
def chat_api():
    try:
        data = request.json
        message = data.get("message", "")
        user_id = session["user"]["id"]
        
        if not message:
            return jsonify({"reply": "Message vide."})
        
        reply = get_gemini_response(message, user_id)
        
        save_to_supabase(user_id, "user", message)
        save_to_supabase(user_id, "model", reply)
        
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": f"Erreur : {str(e)}"})

# ==============================
# WEBHOOK WHATSAPP
# ==============================

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Erreur de vérification", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        from_number = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]

        reply = get_gemini_response(message, user_id=from_number)

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
