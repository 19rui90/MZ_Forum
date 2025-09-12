#!/usr/bin/env python3
import requests, json, os, time, hashlib, logging
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread

from zoneinfo import ZoneInfo  # Python 3.9+

# Fuso horário de Lisboa
now = datetime.now(ZoneInfo("Europe/Lisbon"))

# ---------------- CONFIG LOGGING ----------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------- TELEGRAM ----------------
def send_telegram_message(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        resp = requests.post(url, data=data, timeout=10)
        if resp.status_code != 200:
            logger.error(f"Telegram retornou status {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Erro Telegram: {e}")

# ---------------- FORUM SCRAPER ----------------
def get_forum_topics(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept-Language': 'pt-PT,pt;q=0.9,en;q=0.8'
        }
        res = requests.get(url, headers=headers, timeout=25)
        if res.status_code != 200:
            logger.warning(f"HTTP {res.status_code} para {url}")
            return []
        soup = BeautifulSoup(res.text, 'html.parser')
        links = soup.find_all('a', href=lambda x: x and ('topic_id=' in x or 'thread_id=' in x))
        topics = []
        seen = set()
        for link in links:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if len(title) < 5 or '#' in href or title in seen:
                continue
            # montar URL completa
            if href.startswith('?'):
                full_url = "https://www.managerzone.com/" + href
            elif href.startswith('/'):
                full_url = "https://www.managerzone.com" + href
            else:
                full_url = href
            # id único
            topic_id = hashlib.md5(f"{title}|{full_url}".encode()).hexdigest()[:12]
            topics.append({'id': topic_id, 'title': title[:120], 'url': full_url})
            seen.add(title)
            if len(topics) >= 8:
                break
        logger.info(f"Encontrados {len(topics)} tópicos em {url}")
        return topics
    except Exception as e:
        logger.error(f"Erro ao buscar tópicos de {url}: {e}")
        return []

# ---------------- ESTADO ----------------
def load_state():
    try:
        if os.path.exists('forum_state.json'):
            with open('forum_state.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                else:
                    logger.warning("forum_state.json não é dict — recriando.")
                    return {}
    except Exception as e:
        logger.error(f"Erro a carregar estado: {e}")
    return {}

def save_state(state):
    try:
        with open('forum_state.json', 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        logger.info("Estado salvo com sucesso.")
    except Exception as e:
        logger.error(f"Erro a salvar estado: {e}")

# ---------------- LOOP PRINCIPAL ----------------
def monitor():
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHAT_ID')
    if not token or not chat_id:
        logger.error("❌ Faltam variáveis de ambiente: TELEGRAM_TOKEN ou CHAT_ID")
        return

    forums = {
        '125': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=125&sport=soccer', 'name': '🇵🇹 Português(Portugal)\nManagerZone Talk'},
        '126': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=126&sport=soccer', 'name': '🇵🇹 Português(Portugal)\nPerguntas e Respostas'},
        '388': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=388&sport=soccer', 'name': '🇵🇹 Português(Portugal)\nDiscussão sobre as Selecções Nacionais'},
        '47': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=47&sport=soccer', 'name': '🇧🇷 Português(Brasil)\nManagerZone talk'},
        '49': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=49&sport=soccer', 'name': '🇧🇷 Português(Brasil)\nPerguntas & Respostas'},
        '253': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=253&sport=soccer', 'name': '🇦🇷 Español(Latinoamerica)\nManagerZone Habla'},
        '255': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=255&sport=soccer', 'name': '🇦🇷 Español(Latinoamerica)\nPreguntas y Respuestas'},
        '10': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=10&sport=soccer', 'name': '🏴󠁧󠁢󠁥󠁮󠁧󠁿 English\nManagerZone Talk'},
        '12': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=12&sport=soccer', 'name': '🏴󠁧󠁢󠁥󠁮󠁧󠁿 English\nQuestions & Answers'},
        '387': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=387&sport=soccer', 'name': '🏴󠁧󠁢󠁥󠁮󠁧󠁿 English\nSimulator Development Feedback'},
        '318': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=318&sport=soccer', 'name': '🇨🇳 Chinese\n1 新手及疑问解答 Newbie and Q&A'},
        '316': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=316&sport=soccer', 'name': '🇨🇳 Chinese\n2 游戏热点以及官方杯赛讨论 MZ Talk'},  # corrigi acentuação?
        '19': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=19&sport=soccer', 'name': '🇪🇦 Español(España)\nManagerZone habla'},
        '21': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=21&sport=soccer', 'name': '🇪🇦 Español(España)\nPreguntas y Respuestas'},
        '26': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=26&sport=soccer', 'name': '🇵🇱 Polski\nRozmowy ManagerZone [MZ Talk]'},
        '25': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=25&sport=soccer', 'name': '🇵🇱 Polski\nPytania i Odpowiedzi [Q&A]'},
        '1': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=1&sport=soccer', 'name': '🇸🇪 Svenska\nAllmänt om ManagerZone [MZ Talk]'},
        '4': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=4&sport=soccer', 'name': '🇸🇪 Svenska\nFrågor & Svar [Q&A]'},
        '90': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=90&sport=soccer', 'name': '🇹🇷 Türkçe\nManagerZone muhabbetleri [MZ Talk]'},
        '91': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=91&sport=soccer', 'name': '🇹🇷 Türkçe\nSorular & Cevaplar [Q&A]'},
        '9': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=9&sport=soccer', 'name': '🏴󠁧󠁢󠁥󠁮󠁧󠁿 English 🏴󠁧󠁢󠁥󠁮󠁧󠁿\n     Transfers & Market'},
        '249': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=249&sport=soccer', 'name': '🇦🇷 Español(Latinoamerica) 🇦🇷\n      Mercado de Jugadores'}
    }

    prev = load_state()
    curr = {}
    is_first = len(prev) == 0

    if is_first:
        # Só envia esta mensagem uma vez, no primeiro monitoramento
        send_telegram_message(token, chat_id, "🚀🚀🚀\nMonitor ManagerZone iniciado! \nPrimeira verificação...\nSem notificações anteriores.")
        logger.info("Primeira execução: estado inicial carregado.")

    for f_id, f_info in forums.items():
        topics = get_forum_topics(f_info['url'])
        curr[f_id] = [t['id'] for t in topics]

        if not is_first:
            new_topics = [t for t in topics if t['id'] not in prev.get(f_id, [])]
            if new_topics:
                logger.info(f"{len(new_topics)} novos tópicos no fórum {f_info['name']}")
            for t in new_topics:
                # construir mensagem com título, fórum, url e timestamp
                timestamp = datetime.now(ZoneInfo("Europe/Lisbon")).strftime('%d/%m/%Y %H:%M')
                msg = (f"<b>{f_info['name']}</b>\n\n"
                       f"<a href='{t['url']}'>{t['title']}</a>\n\n\n\n")  # Título do tópico clicável
#                       f"🕐 {timestamp}")
                send_telegram_message(token, chat_id, msg)
                time.sleep(3)  # evitar enviar todos ao mesmo tempo

    save_state(curr)

# ---------------- SERVIDOR FLASK (necessário no Render) ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "ManagerZone Monitor Online ✅"

def run_server():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # iniciar servidor web em thread separada
    Thread(target=run_server).start()

    # loop contínuo: executar o monitor a cada 5 minutos
    while True:
        try:
            monitor()
        except Exception as e:
            logger.error(f"Erro no monitor: {e}")
        logger.info("⏳ A aguardar 5 minutos para próxima verificação...")
        time.sleep(300)
