import discord
from discord.ext import commands
from flask import Flask, request, jsonify
import threading
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Configuración del bot de Discord (sin intents privilegiados)
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# ID del canal donde se enviarán las notificaciones
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', '0'))  # Reemplaza con tu channel ID

# Configuración de Flask para el webhook
app = Flask(__name__)

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print(f'Esperando notificaciones de commits...')

@app.route('/webhook/github', methods=['POST'])
def github_webhook():
    """Endpoint para recibir webhooks de GitHub"""
    try:
        data = request.json
        
        if not data:
            print("❌ No se recibieron datos")
            return jsonify({'error': 'No data received'}), 400
        
        print(f"✅ Webhook recibido de GitHub")
        print(f"📦 Evento: {request.headers.get('X-GitHub-Event', 'unknown')}")
        
        # Detectar evento de push (commit)
        if 'commits' in data and data.get('ref'):
            branch = data['ref'].split('/')[-1]
            repo_name = data['repository']['full_name']
            pusher = data['pusher']['name']
            commits = data['commits']
            
            print(f"🔔 Nuevo commit detectado en {repo_name}")
            
            # Crear mensaje para Discord
            message = f"🔔 **Nuevo commit en {repo_name}**\n"
            message += f"📂 Branch: `{branch}`\n"
            message += f"👤 Autor: {pusher}\n"
            message += f"📝 Commits ({len(commits)}):\n\n"
            
            for commit in commits[:5]:  # Limitar a 5 commits
                commit_msg = commit['message'].split('\n')[0][:100]
                commit_id = commit['id'][:7]
                author = commit['author']['name']
                message += f"• `{commit_id}` - {commit_msg} ({author})\n"
            
            if len(commits) > 5:
                message += f"\n... y {len(commits) - 5} commits más"
            
            message += f"\n🔗 [Ver cambios]({data['compare']})"
            
            # Enviar mensaje a Discord de forma asíncrona
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                bot.loop.create_task(channel.send(message))
                print(f"✅ Notificación enviada a Discord")
                return jsonify({'status': 'success', 'message': 'Notification sent'}), 200
            else:
                print(f"❌ Canal {CHANNEL_ID} no encontrado")
                return jsonify({'error': 'Channel not found'}), 404
        
        print(f"⚠️ Evento ignorado (no es un push)")
        return jsonify({'status': 'ignored', 'message': 'Not a push event'}), 200
        
    except Exception as e:
        print(f"❌ Error en webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/gitlab', methods=['POST'])
def gitlab_webhook():
    """Endpoint para recibir webhooks de GitLab"""
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data received'}), 400
    
    # Detectar evento de push
    if data.get('object_kind') == 'push':
        branch = data['ref'].split('/')[-1]
        repo_name = data['project']['path_with_namespace']
        pusher = data['user_name']
        commits = data['commits']
        
        message = f"🔔 **Nuevo commit en {repo_name}**\n"
        message += f"📂 Branch: `{branch}`\n"
        message += f"👤 Autor: {pusher}\n"
        message += f"📝 Commits ({len(commits)}):\n\n"
        
        for commit in commits[:5]:
            commit_msg = commit['message'].split('\n')[0][:100]
            commit_id = commit['id'][:7]
            author = commit['author']['name']
            message += f"• `{commit_id}` - {commit_msg} ({author})\n"
        
        if len(commits) > 5:
            message += f"\n... y {len(commits) - 5} commits más"
        
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            bot.loop.create_task(channel.send(message))
            return jsonify({'status': 'success', 'message': 'Notification sent'}), 200
        else:
            return jsonify({'error': 'Channel not found'}), 404
    
    return jsonify({'status': 'ignored', 'message': 'Not a push event'}), 200

@app.route('/health', methods=['GET'])
def health():
    """Endpoint para verificar que el servidor está funcionando"""
    return jsonify({'status': 'online', 'bot': str(bot.user) if bot.user else 'disconnected'}), 200

@app.route('/', methods=['GET', 'POST'])
def index():
    """Ruta raíz para verificar que el servidor está corriendo"""
    return jsonify({
        'status': 'Server is running',
        'endpoints': {
            'github': '/webhook/github',
            'gitlab': '/webhook/gitlab',
            'health': '/health'
        }
    }), 200

def run_flask():
    """Ejecutar Flask en un thread separado"""
    app.run(host='0.0.0.0', port=5000)

def main():
    # Obtener token de Discord desde variable de entorno
    DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    if not DISCORD_TOKEN:
        print("Error: DISCORD_BOT_TOKEN no está configurado")
        print("Configura tu token: export DISCORD_BOT_TOKEN='tu_token_aqui'")
        return
    
    if CHANNEL_ID == 0:
        print("Advertencia: DISCORD_CHANNEL_ID no está configurado")
        print("Configura tu channel ID: export DISCORD_CHANNEL_ID='123456789'")
    
    # Iniciar Flask en un thread separado
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Servidor Flask iniciado en http://0.0.0.0:5000")
    print("Endpoints disponibles:")
    print("  - POST /webhook/github  (para GitHub)")
    print("  - POST /webhook/gitlab  (para GitLab)")
    print("  - GET  /health          (verificar estado)")
    
    # Iniciar bot de Discord
    bot.run(DISCORD_TOKEN)

if __name__ == '__main__':
    main()