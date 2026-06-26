from flask import Flask, request, render_template_string, jsonify, session, redirect, url_for, Response
import requests
import os
import json
import jwt
import csv
import io
from functools import wraps
from datetime import datetime
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

ADMIN_EMAILS = ["daoudasanou6737@gmail.com"]

conversations = {}
MAX_HISTORY = 10

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
# DÉTECTION DE SERVICES
# ==============================
def detect_service(message):
    message_lower = message.lower()
    services = {
        "site_web": ["site web", "site internet", "création site", "page web"],
        "logo_design": ["logo", "design", "flyer", "carte de visite", "graphique"],
        "reseaux_sociaux": ["réseau social", "instagram", "facebook", "tiktok", "community"],
        "photographie": ["photo", "photographie", "shooting", "portrait"],
        "automatisation_ia": ["automatisation", "ia", "intelligence artificielle", "chatbot", "bot"],
        "streaming": ["streaming", "live", "diffusion", "direct"]
    }
    for service, keywords in services.items():
        for kw in keywords:
            if kw in message_lower:
                return service
    return None

def detect_commande(message):
    message_lower = message.lower()
    keywords = ["je veux", "j'aimerais", "réserver", "commander", "acheter", 
                "combien", "prix", "tarif", "rdv", "rendez-vous", "contact",
                "intéressé", "interessé", "devis"]
    return any(kw in message_lower for kw in keywords)

# ==============================
# FONCTION GEMINI
# ==============================
def get_gemini_response(user_message, user_id="default"):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "test":
        return "⚠️ GEMINI_API_KEY non configurée."
    try:
        if user_id not in conversations:
            conversations[user_id] = []
        conversations[user_id].append({"role": "user", "parts": [{"text": user_message}]})
        if len(conversations[user_id]) > MAX_HISTORY * 2:
            conversations[user_id] = conversations[user_id][-MAX_HISTORY * 2:]
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
        params = {"key": GEMINI_API_KEY}
        data = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": conversations[user_id],
            "generationConfig": {"temperature": 0.7, "topK": 40, "topP": 0.95, "maxOutputTokens": 1024}
        }
        response = requests.post(url, params=params, json=data, timeout=30)
        result = response.json()
        if "candidates" in result and len(result["candidates"]) > 0:
            reply = result["candidates"][0]["content"]["parts"][0]["text"]
            conversations[user_id].append({"role": "model", "parts": [{"text": reply}]})
            return reply
        else:
            if conversations[user_id]: conversations[user_id].pop()
            return "Désolée, je n'ai pas pu traiter votre demande. Pouvez-vous reformuler ?"
    except Exception as e:
        print("Erreur Gemini:", e)
        if user_id in conversations and conversations[user_id]: conversations[user_id].pop()
        return "Désolée, une erreur technique est survenue. Réessayez dans un instant."

# ==============================
# AUTH & SUPABASE
# ==============================
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = session.get("user")
        if not user:
            return redirect(url_for("login_page"))
        if user.get("email") not in ADMIN_EMAILS:
            return "Acces refuse. Page reservee a l administrateur.", 403
        return f(*args, **kwargs)
    return decorated

def save_to_supabase(user_id, role, content, message_text=None):
    if not supabase:
        return
    try:
        conv = supabase.table("conversations").select("id").eq("user_id", user_id).eq("status", "active").limit(1).execute()
        if conv.data:
            conversation_id = conv.data[0]["id"]
        else:
            new_conv = supabase.table("conversations").insert({
                "user_id": user_id, "title": "Conversation avec Samira",
                "status": "active", "topic_type": "general"
            }).execute()
            conversation_id = new_conv.data[0]["id"]
        supabase.table("messages").insert({
            "conversation_id": conversation_id, "role": role, "content": content
        }).execute()
        if role == "user" and message_text:
            service = detect_service(message_text)
            if service:
                update_data = {"service_demande": service, "topic_type": service}
                if detect_commande(message_text):
                    update_data["lead_status"] = "interesse"
                supabase.table("conversations").update(update_data).eq("id", conversation_id).execute()
    except Exception as e:
        print(f"Erreur Supabase: {e}")

# ==============================
# ROUTES PRINCIPALES
# ==============================
@app.route("/", methods=["GET"])
def home():
    if session.get("user"):
        return redirect(url_for("chat_page"))
    return redirect(url_for("login_page"))

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
        session["user"] = {"id": user_id, "email": email, "name": display_name, "avatar": avatar_url}
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/auth/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/chat", methods=["GET"])
@require_auth
def chat_page():
    user = session.get("user")
    is_admin = user.get("email") in ADMIN_EMAILS
    return render_template_string(PAGE_CHAT, user=user, is_admin=is_admin)

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
        save_to_supabase(user_id, "user", message, message_text=message)
        save_to_supabase(user_id, "model", reply)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": f"Erreur : {str(e)}"})

# ==============================
# ROUTES ADMIN
# ==============================
@app.route("/admin")
@require_admin
def admin_dashboard():
    user = session.get("user")
    try:
        users_data = supabase.table("users").select("*").execute().data
        conversations_data = supabase.table("conversations").select("*").execute().data
        messages_data = supabase.table("messages").select("*").execute().data
        total_users = len(users_data)
        total_conversations = len(conversations_data)
        total_messages = len(messages_data)
        today = datetime.utcnow().date()
        messages_today = 0
        for m in messages_data:
            if m.get("created_at"):
                try:
                    msg_date = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")).date()
                    if msg_date == today:
                        messages_today += 1
                except:
                    pass
        services_count = {}
        leads_interesses = 0
        for c in conversations_data:
            service = c.get("service_demande")
            if service:
                services_count[service] = services_count.get(service, 0) + 1
            if c.get("lead_status") == "interesse":
                leads_interesses += 1
        users_enriched = []
        for u in users_data:
            user_convs = [c for c in conversations_data if c.get("user_id") == u["id"]]
            user_conv_ids = [c["id"] for c in user_convs]
            user_msg_count = sum(1 for m in messages_data if m.get("conversation_id") in user_conv_ids)
            user_services = list(set([c.get("service_demande") for c in user_convs if c.get("service_demande")]))
            users_enriched.append({
                **u, "nb_messages": user_msg_count, "services": user_services,
                "is_lead": any(c.get("lead_status") == "interesse" for c in user_convs)
            })
        users_enriched.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return render_template_string(PAGE_ADMIN, user=user,
            stats={
                "total_users": total_users, "total_conversations": total_conversations,
                "total_messages": total_messages, "messages_today": messages_today,
                "leads_interesses": leads_interesses
            },
            users=users_enriched, services_count=services_count)
    except Exception as e:
        return f"Erreur: {str(e)}", 500

@app.route("/admin/conversation/<user_id>")
@require_admin
def admin_view_conversation(user_id):
    try:
        user_info = supabase.table("users").select("*").eq("id", user_id).execute().data
        if not user_info:
            return "Utilisateur introuvable", 404
        target_user = user_info[0]
        convs = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute().data
        all_messages = []
        for c in convs:
            msgs = supabase.table("messages").select("*").eq("conversation_id", c["id"]).order("created_at").execute().data
            all_messages.append({"conversation": c, "messages": msgs})
        return render_template_string(PAGE_ADMIN_CONV, user=session.get("user"),
            target_user=target_user, conversations=all_messages)
    except Exception as e:
        return f"Erreur: {str(e)}", 500

@app.route("/admin/export-csv")
@require_admin
def admin_export_csv():
    try:
        users_data = supabase.table("users").select("*").execute().data
        conversations_data = supabase.table("conversations").select("*").execute().data
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Nom", "Email", "Google ID", "Date inscription", "Services demandes", "Statut"])
        for u in users_data:
            user_convs = [c for c in conversations_data if c.get("user_id") == u["id"]]
            services = list(set([c.get("service_demande") for c in user_convs if c.get("service_demande")]))
            is_lead = any(c.get("lead_status") == "interesse" for c in user_convs)
            writer.writerow([
                u.get("display_name", ""), u.get("email", ""), u.get("google_id", ""),
                u.get("created_at", ""), ", ".join(services) if services else "Aucun",
                "Lead interesse" if is_lead else "Visiteur"
            ])
        output.seek(0)
        return Response(output.getvalue(), mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=ds_contacts_{datetime.now().strftime('%Y%m%d')}.csv"})
    except Exception as e:
        return f"Erreur: {str(e)}", 500

@app.route("/admin/notifications-check")
@require_admin
def admin_notifications():
    try:
        since = request.args.get("since")
        query = supabase.table("conversations").select("*").eq("lead_status", "interesse")
        if since:
            query = query.gte("updated_at", since)
        leads = query.order("updated_at", desc=True).limit(10).execute().data
        enriched = []
        for lead in leads:
            user_info = supabase.table("users").select("display_name, email, avatar_url").eq("id", lead["user_id"]).execute().data
            if user_info:
                lead["user"] = user_info[0]
            enriched.append(lead)
        return jsonify({"leads": enriched, "now": datetime.utcnow().isoformat()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================
# WEBHOOK WHATSAPP
# ==============================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Erreur de verification", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        from_number = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
        reply = get_gemini_response(message, user_id=from_number)
        requests.post(
            f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages",
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": from_number, "text": {"body": reply}}
        )
    except Exception as e:
        print("Erreur :", e)
    return "ok"

# ==============================
# PAGE LOGIN
# ==============================
PAGE_LOGIN = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Connexion - DS Digital Hub</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; font-family:'Inter',sans-serif; }
body { background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0f1729 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; color: white; padding: 20px; }
.login-card { background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); padding: 50px 40px; border-radius: 24px; text-align: center; max-width: 420px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.4); }
.logo-ds { width: 80px; height: 80px; background: linear-gradient(135deg, #2563eb, #4f46e5); border-radius: 18px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 32px; margin: 0 auto 24px; box-shadow: 0 8px 30px rgba(59,130,246,0.4); }
h1 { font-size: 26px; margin-bottom: 8px; font-weight: 800; }
p { color: rgba(255,255,255,0.6); margin-bottom: 32px; font-size: 15px; line-height: 1.5; }
.google-btn { display: inline-flex; align-items: center; gap: 12px; background: white; color: #1a1f3a; padding: 14px 28px; border-radius: 12px; text-decoration: none; font-weight: 600; transition: all 0.2s; box-shadow: 0 4px 16px rgba(0,0,0,0.2); }
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

# ==============================
# PAGE CALLBACK
# ==============================
PAGE_CALLBACK = """
<!DOCTYPE html>
<html>
<head><title>Connexion...</title><meta charset="UTF-8"></head>
<body style="background:#0a0e27;color:white;font-family:sans-serif;text-align:center;padding:50px;">
<h2>Connexion en cours...</h2>
<p>Veuillez patienter, vous allez etre redirige.</p>
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
        if (data.success) window.location.href = '/chat';
        else document.body.innerHTML = '<h2>Erreur</h2><a href="/login" style="color:#3b82f6;">Reessayer</a>';
    });
} else {
    document.body.innerHTML = '<h2>Erreur token</h2><a href="/login" style="color:#3b82f6;">Reessayer</a>';
}
</script>
</body>
</html>
"""

# ==============================
# PAGE CHAT
# ==============================
PAGE_CHAT = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Samira - DS Digital Hub</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; font-family:'Inter',sans-serif; }
body { background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0f1729 100%); min-height: 100vh; overflow: hidden; color: white; }
body::before { content:''; position:fixed; top:0; left:0; width:100%; height:100%; background: radial-gradient(circle at 20% 30%, rgba(59,130,246,0.15) 0%, transparent 50%), radial-gradient(circle at 80% 70%, rgba(99,102,241,0.15) 0%, transparent 50%); animation: bgFlow 20s ease infinite; z-index:0; }
@keyframes bgFlow { 0%,100% { transform: scale(1) rotate(0deg); } 50% { transform: scale(1.1) rotate(180deg); } }
.app-container { position:relative; z-index:1; height:100vh; display:flex; }
.sidebar { width:280px; background:rgba(10,14,39,0.7); backdrop-filter: blur(20px); border-right:1px solid rgba(255,255,255,0.08); display:flex; flex-direction:column; padding:24px 20px; overflow-y:auto; }
.sidebar-header { display:flex; align-items:center; gap:14px; margin-bottom:32px; }
.logo-ds { width:50px; height:50px; background:linear-gradient(135deg, #2563eb, #4f46e5); border-radius:12px; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:22px; color:white; box-shadow: 0 4px 20px rgba(59,130,246,0.4); }
.brand-info h2 { font-size:18px; font-weight:800; }
.brand-info p { font-size:12px; color:rgba(255,255,255,0.5); margin-top:2px; }
.sidebar-title { font-size:11px; font-weight:600; color:rgba(255,255,255,0.5); text-transform:uppercase; letter-spacing:1.5px; margin-bottom:14px; padding-left:4px; }
.services-list { display:flex; flex-direction:column; gap:8px; margin-bottom:24px; }
.service-item { display:flex; align-items:center; gap:12px; padding:12px 14px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:12px; cursor:pointer; transition: all 0.25s; color:rgba(255,255,255,0.85); font-size:14px; font-weight:500; text-align:left; width:100%; }
.service-item:hover { background:rgba(59,130,246,0.15); border-color:rgba(59,130,246,0.4); color:white; transform:translateX(4px); }
.service-icon { font-size:18px; min-width:24px; }
.new-chat-btn, .admin-btn { margin-top:auto; padding:14px; background:linear-gradient(135deg, #2563eb, #4f46e5); color:white; border:none; border-radius:12px; cursor:pointer; font-size:14px; font-weight:600; display:flex; align-items:center; justify-content:center; gap:8px; transition: all 0.2s; box-shadow: 0 4px 16px rgba(59,130,246,0.3); text-decoration:none; }
.admin-btn { background:linear-gradient(135deg, #f59e0b, #d97706); margin-top:8px; }
.new-chat-btn:hover, .admin-btn:hover { transform:translateY(-2px); }
.user-info { display:flex; align-items:center; gap:10px; padding:10px; background:rgba(255,255,255,0.04); border-radius:12px; margin-top:12px; }
.user-avatar { width:36px; height:36px; border-radius:50%; background:linear-gradient(135deg, #2563eb, #4f46e5); display:flex; align-items:center; justify-content:center; font-weight:700; font-size:14px; overflow:hidden; }
.user-avatar img { width:100%; height:100%; object-fit:cover; }
.user-details { flex:1; min-width:0; }
.user-name { font-size:13px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.user-email { font-size:11px; color:rgba(255,255,255,0.5); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.logout-btn { background:none; border:none; color:rgba(255,255,255,0.6); cursor:pointer; padding:6px; border-radius:8px; transition: all 0.2s; }
.logout-btn:hover { background:rgba(239,68,68,0.15); color:#ef4444; }
.main-area { flex:1; display:flex; flex-direction:column; min-width:0; }
.chat-header { display:flex; align-items:center; gap:12px; padding:20px 24px; background:rgba(15,23,42,0.5); backdrop-filter:blur(20px); border-bottom:1px solid rgba(255,255,255,0.08); }
.header-avatar { width:42px; height:42px; border-radius:50%; background:linear-gradient(135deg, #2563eb, #4f46e5); display:flex; align-items:center; justify-content:center; font-weight:800; font-size:16px; }
.header-info h1 { font-size:17px; font-weight:700; }
.header-info .status { font-size:12px; color:rgba(255,255,255,0.6); display:flex; align-items:center; gap:6px; margin-top:2px; }
.status-dot { width:8px; height:8px; background:#10b981; border-radius:50%; box-shadow:0 0 12px #10b981; animation: pulse 2s ease infinite; }
@keyframes pulse { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:0.6; transform:scale(1.2); } }
.chat-box { flex:1; overflow-y:auto; padding:24px 32px; display:flex; flex-direction:column; gap:16px; }
.chat-box::-webkit-scrollbar { width:6px; }
.chat-box::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.1); border-radius:10px; }
.message { max-width:70%; padding:14px 18px; border-radius:18px; line-height:1.5; font-size:15px; animation: slideIn 0.4s; }
@keyframes slideIn { from { opacity:0; transform:translateY(15px); } to { opacity:1; transform:translateY(0); } }
.message.user { align-self:flex-end; background:linear-gradient(135deg, #2563eb, #4f46e5); border-bottom-right-radius:4px; }
.message.bot { align-self:flex-start; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.08); border-bottom-left-radius:4px; }
.typing { align-self:flex-start; background:rgba(255,255,255,0.06); padding:16px 20px; border-radius:18px; display:flex; gap:5px; }
.typing span { width:8px; height:8px; background:rgba(255,255,255,0.5); border-radius:50%; animation: typingBounce 1.4s infinite; }
.typing span:nth-child(2) { animation-delay:0.2s; }
.typing span:nth-child(3) { animation-delay:0.4s; }
@keyframes typingBounce { 0%,60%,100% { transform:translateY(0); opacity:0.5; } 30% { transform:translateY(-8px); opacity:1; } }
.input-area { padding:16px 32px 24px; background:rgba(15,23,42,0.5); border-top:1px solid rgba(255,255,255,0.08); }
.input-wrapper { display:flex; gap:10px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:16px; padding:6px; }
.input-wrapper input { flex:1; padding:12px 16px; background:transparent; border:none; outline:none; color:white; font-size:15px; }
.send-btn { width:44px; height:44px; border:none; background:linear-gradient(135deg, #2563eb, #4f46e5); color:white; border-radius:12px; cursor:pointer; display:flex; align-items:center; justify-content:center; }
.send-btn svg { width:20px; height:20px; }
.footer-info { text-align:center; margin-top:12px; font-size:12px; color:rgba(255,255,255,0.4); }
@media (max-width:768px) { .sidebar { display:none; } .chat-box { padding:18px; } .message { max-width:85%; } }
</style>
</head>
<body>
<div class="app-container">
<aside class="sidebar">
<div class="sidebar-header">
<div class="logo-ds">DS</div>
<div class="brand-info">
<h2>DS Digital Hub</h2>
<p>Assistant Samira</p>
</div>
</div>
<div class="sidebar-title">Nos Services</div>
<div class="services-list">
<button class="service-item" onclick="sendSuggestion('Je veux creer un site web pour mon entreprise')"><span class="service-icon">🌐</span><span>Creer un site web</span></button>
<button class="service-item" onclick="sendSuggestion('Je veux un logo professionnel')"><span class="service-icon">🎨</span><span>Logo & Design</span></button>
<button class="service-item" onclick="sendSuggestion('Je veux gerer mes reseaux sociaux')"><span class="service-icon">📱</span><span>Reseaux sociaux</span></button>
<button class="service-item" onclick="sendSuggestion('Je veux des photos professionnelles')"><span class="service-icon">📸</span><span>Photographie</span></button>
<button class="service-item" onclick="sendSuggestion('Je veux automatiser mon business avec IA')"><span class="service-icon">🤖</span><span>Automatisation IA</span></button>
<button class="service-item" onclick="sendSuggestion('Je veux un service de streaming')"><span class="service-icon">🎬</span><span>Streaming pro</span></button>
</div>
<button class="new-chat-btn" onclick="resetChat()">
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
Nouvelle conversation
</button>
{% if is_admin %}
<a href="/admin" class="admin-btn">
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 3h18v18H3z"/><path d="M3 9h18M9 21V9"/></svg>
Dashboard Admin
</a>
{% endif %}
<div class="user-info">
<div class="user-avatar">{% if user.avatar %}<img src="{{ user.avatar }}">{% else %}{{ user.name[0]|upper }}{% endif %}</div>
<div class="user-details">
<div class="user-name">{{ user.name }}</div>
<div class="user-email">{{ user.email }}</div>
</div>
<a href="/auth/logout" class="logout-btn" title="Deconnexion">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
</a>
</div>
</aside>
<main class="main-area">
<div class="chat-header">
<div class="header-avatar">S</div>
<div class="header-info">
<h1>Samira</h1>
<div class="status"><span class="status-dot"></span>En ligne maintenant</div>
</div>
</div>
<div class="chat-box" id="chatBox">
<div class="message bot">
Bonjour {{ user.name.split(' ')[0] }} 👋 Je suis <strong>Samira</strong>, votre assistante chez <strong>DS Digital Hub</strong>.<br><br>
Choisissez un service a gauche ou posez-moi directement votre question. Comment puis-je vous aider a booster votre business aujourd'hui ?
</div>
</div>
<div class="input-area">
<div class="input-wrapper">
<input type="text" id="userInput" placeholder="Posez votre question a Samira..." autocomplete="off">
<button class="send-btn" id="sendBtn" onclick="sendMessage()">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
</button>
</div>
<div class="footer-info">Powered by DS Digital Hub - Samira IA</div>
</div>
</main>
</div>
<script>
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
userInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendMessage(); });
function sendSuggestion(text) { userInput.value = text; sendMessage(); }
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
        addMessage('Desolee, une erreur est survenue.', 'bot');
    }
    sendBtn.disabled = false;
    userInput.focus();
}
function addMessage(text, sender) {
    const div = document.createElement('div');
    div.className = 'message ' + sender;
    div.innerHTML = text.replace(/\\n/g, '<br>');
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}
function resetChat() {
    if (!confirm('Demarrer une nouvelle conversation ?')) return;
    location.reload();
}
</script>
</body>
</html>
"""

# ==============================
# PAGE ADMIN
# ==============================
PAGE_ADMIN = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Admin - DS Digital Hub</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; font-family:'Inter',sans-serif; }
body { background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0f1729 100%); min-height:100vh; color:white; padding:24px; }
.container { max-width:1400px; margin:0 auto; }
.header { display:flex; justify-content:space-between; align-items:center; margin-bottom:32px; flex-wrap:wrap; gap:16px; }
.header h1 { font-size:28px; font-weight:800; display:flex; align-items:center; gap:12px; }
.badge-admin { background:linear-gradient(135deg, #f59e0b, #d97706); padding:4px 12px; border-radius:20px; font-size:12px; font-weight:700; }
.header-actions { display:flex; gap:12px; }
.btn { padding:10px 18px; border-radius:10px; text-decoration:none; font-weight:600; font-size:14px; display:inline-flex; align-items:center; gap:8px; transition: all 0.2s; border:none; cursor:pointer; }
.btn-primary { background:linear-gradient(135deg, #2563eb, #4f46e5); color:white; }
.btn-secondary { background:rgba(255,255,255,0.1); color:white; border:1px solid rgba(255,255,255,0.2); }
.btn:hover { transform:translateY(-2px); }
.stats-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:16px; margin-bottom:32px; }
.stat-card { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); padding:24px; border-radius:16px; backdrop-filter:blur(10px); }
.stat-card.highlight { background:linear-gradient(135deg, rgba(245,158,11,0.15), rgba(217,119,6,0.05)); border-color:rgba(245,158,11,0.3); }
.stat-icon { width:48px; height:48px; border-radius:12px; background:linear-gradient(135deg, #2563eb, #4f46e5); display:flex; align-items:center; justify-content:center; font-size:22px; margin-bottom:12px; }
.stat-card.highlight .stat-icon { background:linear-gradient(135deg, #f59e0b, #d97706); }
.stat-value { font-size:32px; font-weight:800; margin-bottom:4px; }
.stat-label { font-size:13px; color:rgba(255,255,255,0.6); }
.section { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:24px; margin-bottom:24px; }
.section h2 { font-size:18px; font-weight:700; margin-bottom:20px; display:flex; align-items:center; gap:10px; }
.services-chart { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; }
.service-stat { background:rgba(255,255,255,0.05); padding:16px; border-radius:12px; display:flex; justify-content:space-between; align-items:center; }
.service-name { font-size:14px; font-weight:500; }
.service-count { background:linear-gradient(135deg, #2563eb, #4f46e5); padding:4px 12px; border-radius:20px; font-weight:700; font-size:14px; }
.users-table { width:100%; border-collapse:collapse; }
.users-table th { text-align:left; padding:12px; font-size:12px; text-transform:uppercase; color:rgba(255,255,255,0.5); font-weight:600; border-bottom:1px solid rgba(255,255,255,0.1); }
.users-table td { padding:14px 12px; border-bottom:1px solid rgba(255,255,255,0.05); font-size:14px; }
.users-table tr:hover { background:rgba(255,255,255,0.03); }
.user-cell { display:flex; align-items:center; gap:10px; }
.user-cell-avatar { width:36px; height:36px; border-radius:50%; background:linear-gradient(135deg, #2563eb, #4f46e5); display:flex; align-items:center; justify-content:center; font-weight:700; overflow:hidden; }
.user-cell-avatar img { width:100%; height:100%; object-fit:cover; }
.tag { display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:600; margin-right:4px; }
.tag-service { background:rgba(59,130,246,0.2); color:#60a5fa; }
.tag-lead { background:linear-gradient(135deg, #f59e0b, #d97706); color:white; animation: pulse-lead 2s infinite; }
@keyframes pulse-lead { 0%,100% { box-shadow:0 0 0 0 rgba(245,158,11,0.5); } 50% { box-shadow:0 0 0 8px rgba(245,158,11,0); } }
.view-btn { background:rgba(59,130,246,0.2); color:#60a5fa; padding:6px 12px; border-radius:8px; text-decoration:none; font-size:12px; font-weight:600; }
.view-btn:hover { background:rgba(59,130,246,0.4); }
.notification-toast { position:fixed; top:24px; right:24px; background:linear-gradient(135deg, #f59e0b, #d97706); padding:16px 20px; border-radius:12px; box-shadow:0 10px 40px rgba(0,0,0,0.4); display:flex; align-items:center; gap:12px; max-width:380px; transform:translateX(450px); transition: transform 0.4s; z-index:1000; }
.notification-toast.show { transform:translateX(0); }
.notification-toast .icon { font-size:24px; }
.notification-toast .content { flex:1; }
.notification-toast .title { font-weight:700; font-size:14px; }
.notification-toast .msg { font-size:12px; opacity:0.9; margin-top:2px; }
@media (max-width:768px) { .users-table { font-size:12px; } .users-table th, .users-table td { padding:8px; } }
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>📊 Dashboard Admin <span class="badge-admin">ADMIN</span></h1>
<div class="header-actions">
<a href="/admin/export-csv" class="btn btn-secondary">📥 Export CSV</a>
<a href="/chat" class="btn btn-primary">💬 Retour au chat</a>
</div>
</div>
<div class="stats-grid">
<div class="stat-card"><div class="stat-icon">👥</div><div class="stat-value">{{ stats.total_users }}</div><div class="stat-label">Utilisateurs inscrits</div></div>
<div class="stat-card"><div class="stat-icon">💬</div><div class="stat-value">{{ stats.total_conversations }}</div><div class="stat-label">Conversations</div></div>
<div class="stat-card"><div class="stat-icon">✉️</div><div class="stat-value">{{ stats.total_messages }}</div><div class="stat-label">Messages totaux</div></div>
<div class="stat-card"><div class="stat-icon">📅</div><div class="stat-value">{{ stats.messages_today }}</div><div class="stat-label">Messages aujourd'hui</div></div>
<div class="stat-card highlight"><div class="stat-icon">🔥</div><div class="stat-value">{{ stats.leads_interesses }}</div><div class="stat-label">Leads intéressés</div></div>
</div>
<div class="section">
<h2>🎯 Services demandés</h2>
{% if services_count %}
<div class="services-chart">
{% for service, count in services_count.items() %}
<div class="service-stat"><span class="service-name">{{ service.replace('_', ' ').title() }}</span><span class="service-count">{{ count }}</span></div>
{% endfor %}
</div>
{% else %}
<p style="color:rgba(255,255,255,0.5);">Aucun service demandé pour le moment.</p>
{% endif %}
</div>
<div class="section">
<h2>👥 Utilisateurs ({{ users|length }})</h2>
<div style="overflow-x:auto;">
<table class="users-table">
<thead><tr><th>Utilisateur</th><th>Email</th><th>Messages</th><th>Services</th><th>Statut</th><th>Action</th></tr></thead>
<tbody>
{% for u in users %}
<tr>
<td><div class="user-cell"><div class="user-cell-avatar">{% if u.avatar_url %}<img src="{{ u.avatar_url }}">{% else %}{{ u.display_name[0]|upper if u.display_name else '?' }}{% endif %}</div><div><strong>{{ u.display_name or 'Sans nom' }}</strong></div></div></td>
<td>{{ u.email }}</td>
<td><strong>{{ u.nb_messages }}</strong></td>
<td>{% for s in u.services %}<span class="tag tag-service">{{ s.replace('_', ' ') }}</span>{% endfor %}{% if not u.services %}<span style="color:rgba(255,255,255,0.4);">-</span>{% endif %}</td>
<td>{% if u.is_lead %}<span class="tag tag-lead">🔥 LEAD</span>{% else %}<span style="color:rgba(255,255,255,0.4);">Visiteur</span>{% endif %}</td>
<td><a href="/admin/conversation/{{ u.id }}" class="view-btn">Voir</a></td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
</div>
<div id="notification" class="notification-toast">
<div class="icon">🔥</div>
<div class="content"><div class="title" id="notif-title">Nouveau lead !</div><div class="msg" id="notif-msg"></div></div>
</div>
<script>
let lastCheck = new Date().toISOString();
const knownLeads = new Set();
async function checkNotifications() {
    try {
        const res = await fetch('/admin/notifications-check?since=' + lastCheck);
        const data = await res.json();
        if (data.leads && data.leads.length > 0) {
            data.leads.forEach(lead => {
                if (!knownLeads.has(lead.id)) {
                    knownLeads.add(lead.id);
                    showNotification(lead);
                }
            });
        }
        lastCheck = data.now;
    } catch (e) { console.error(e); }
}
function showNotification(lead) {
    const notif = document.getElementById('notification');
    const userName = lead.user ? lead.user.display_name : 'Un client';
    const service = lead.service_demande ? lead.service_demande.replace('_', ' ') : 'un service';
    document.getElementById('notif-title').textContent = '🔥 Nouveau lead : ' + userName;
    document.getElementById('notif-msg').textContent = 'Intéressé par ' + service;
    notif.classList.add('show');
    try { new Audio('https://www.soundjay.com/buttons/sounds/button-09.mp3').play(); } catch(e){}
    setTimeout(() => notif.classList.remove('show'), 6000);
}
async function initLeads() {
    const res = await fetch('/admin/notifications-check');
    const data = await res.json();
    if (data.leads) data.leads.forEach(l => knownLeads.add(l.id));
    lastCheck = data.now;
}
initLeads();
setInterval(checkNotifications, 10000);
</script>
</body>
</html>
"""

# ==============================
# PAGE ADMIN CONVERSATION DETAIL
# ==============================
PAGE_ADMIN_CONV = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Conversation - Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; font-family:'Inter',sans-serif; }
body { background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0f1729 100%); min-height:100vh; color:white; padding:24px; }
.container { max-width:1000px; margin:0 auto; }
.back-btn { display:inline-flex; align-items:center; gap:8px; background:rgba(255,255,255,0.1); padding:10px 16px; border-radius:10px; color:white; text-decoration:none; margin-bottom:24px; font-weight:600; font-size:14px; }
.back-btn:hover { background:rgba(255,255,255,0.15); }
.user-header { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:24px; margin-bottom:24px; display:flex; align-items:center; gap:16px; }
.user-header-avatar { width:64px; height:64px; border-radius:50%; background:linear-gradient(135deg, #2563eb, #4f46e5); display:flex; align-items:center; justify-content:center; font-weight:800; font-size:24px; overflow:hidden; }
.user-header-avatar img { width:100%; height:100%; object-fit:cover; }
.user-header-info h2 { font-size:22px; font-weight:800; }
.user-header-info p { color:rgba(255,255,255,0.6); font-size:14px; margin-top:4px; }
.conversation { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:20px; margin-bottom:16px; }
.conv-title { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid rgba(255,255,255,0.1); }
.conv-title h3 { font-size:16px; font-weight:700; }
.conv-meta { font-size:12px; color:rgba(255,255,255,0.5); }
.tag { display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:600; margin-left:6px; }
.tag-service { background:rgba(59,130,246,0.2); color:#60a5fa; }
.tag-lead { background:linear-gradient(135deg, #f59e0b, #d97706); }
.messages { display:flex; flex-direction:column; gap:12px; }
.message { padding:12px 16px; border-radius:14px; max-width:75%; font-size:14px; line-height:1.5; }
.message.user { align-self:flex-end; background:linear-gradient(135deg, #2563eb, #4f46e5); border-bottom-right-radius:4px; }
.message.model { align-self:flex-start; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.08); border-bottom-left-radius:4px; }
.message-time { font-size:10px; color:rgba(255,255,255,0.4); margin-top:4px; }
</style>
</head>
<body>
<div class="container">
<a href="/admin" class="back-btn">← Retour au dashboard</a>
<div class="user-header">
<div class="user-header-avatar">{% if target_user.avatar_url %}<img src="{{ target_user.avatar_url }}">{% else %}{{ target_user.display_name[0]|upper if target_user.display_name else '?' }}{% endif %}</div>
<div class="user-header-info">
<h2>{{ target_user.display_name or 'Sans nom' }}</h2>
<p>📧 {{ target_user.email }} | 📅 Inscrit le {{ target_user.created_at[:10] if target_user.created_at else '-' }}</p>
</div>
</div>
{% for conv in conversations %}
<div class="conversation">
<div class="conv-title">
<div>
<h3>{{ conv.conversation.title or 'Conversation' }}
{% if conv.conversation.service_demande %}<span class="tag tag-service">{{ conv.conversation.service_demande.replace('_', ' ') }}</span>{% endif %}
{% if conv.conversation.lead_status == 'interesse' %}<span class="tag tag-lead">🔥 LEAD</span>{% endif %}
</h3>
</div>
<div class="conv-meta">{{ conv.conversation.created_at[:16] if conv.conversation.created_at else '-' }}</div>
</div>
<div class="messages">
{% for msg in conv.messages %}
<div class="message {{ msg.role }}">
{{ msg.content }}
<div class="message-time">{{ msg.created_at[:16] if msg.created_at else '' }}</div>
</div>
{% endfor %}
{% if not conv.messages %}<p style="color:rgba(255,255,255,0.4); text-align:center; padding:20px;">Aucun message dans cette conversation.</p>{% endif %}
</div>
</div>
{% endfor %}
{% if not conversations %}<p style="color:rgba(255,255,255,0.5); text-align:center; padding:40px;">Aucune conversation pour cet utilisateur.</p>{% endif %}
</div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
