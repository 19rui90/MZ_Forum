#!/usr/bin/env python3
import requests, json, os, time, hashlib, logging
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread

# ---------------- CONFIG LOGGING ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
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
        requests.post(url, data=data, timeout=10)
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
            return []

        soup = BeautifulSoup(res.text, 'html.parser')
        links = soup.find_all('a', href=lambda x: x and ('topic_id=' in x or 'thread_id=' in x))
        topics, seen = [], set()

        for link in links:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if len(title) < 5 or '#' in href or title in seen:
                continue

            if href.startswith('?'):
                full_url = "https://www.managerzone.com/" + href
            elif href.startswith('/'):
                full_url = "https://www.managerzone.com" + href
            else:
                full_url = href

            topic_id = hashlib.md5(f"{title}|{full_url}".encode()).hexdigest()[:12]
            topics.append({'id': topic_id, 'title': title[:120], 'url': full_url})
            seen.add(title)
            if len(topics) >= 8: break

        return topics
    except Exception as e:
        logger.error(f"Erro ao buscar tópicos: {e}")
        return []

# ---------------- ESTADO ----------------
def load_state():
    if os.path.exists('forum_state.json'):
        with open('forum_state.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_state(state):
    with open('forum_state.json', 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

# ---------------- LOOP PRINCIPAL ----------------
def monitor():
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHAT_ID')
    if not token or not chat_id:
        logger.error("❌ Faltam variáveis TELEGRAM_TOKEN e CHAT_ID")
        return

    forums = {
        '125': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=125&sport=soccer','name': 'Português(Portugal) » Discussão Geral'},
        '126': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=126&sport=soccer','name': 'Português(Portugal) » Discussão sobre as Selecções Nacionais'},
        '388': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=388&sport=soccer','name': 'Português(Portugal) » Outros Desportos'},
        '47': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=47&sport=soccer','name': 'Deutsch » Allgemeine ManagerZone Diskussion'},
        '49': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=49&sport=soccer','name': 'Deutsch » Nationalmannschaft Diskussion'},
        '253': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=253&sport=soccer','name': 'Español(Latinoamerica) » ManagerZone Habla'},
        '255': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=255&sport=soccer','name': 'Español(Latinoamerica) » Selecciones Nacionales'},
        '10': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=10&sport=soccer','name': 'English » ManagerZone Talk'},
        '12': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=12&sport=soccer','name': 'English » National Teams Discussion'},
        '387': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=387&sport=soccer','name': 'English » Other Sports'},
        '318': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=318&sport=soccer','name': 'Türkçe » ManagerZone Konuşmaları'},
        '316': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=316&sport=soccer','name': 'Türkçe » Milli Takım Tartışmaları'},
        '19': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=19&sport=soccer','name': 'Français » Discussion Générale ManagerZone'},
        '21': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=21&sport=soccer','name': 'Français » Équipes Nationales'},
        '26': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=26&sport=soccer','name': 'Italiano » Discussione Generale ManagerZone'},
        '25': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=25&sport=soccer','name': 'Italiano » Squadre Nazionali'},
        '1': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=1&sport=soccer','name': 'Svenska » Allmänt om ManagerZone'},
        '4': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=4&sport=soccer','name': 'Svenska » Landslag Diskussion'},
        '90': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=90&sport=soccer','name': 'Nederlands » Algemene ManagerZone Discussie'},
        '91': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=91&sport=soccer','name': 'Nederlands » Nationale Teams'},
        '9': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=9&sport=soccer','name': 'English » Transfers & Market'},
        '249': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=249&sport=soccer','name': 'Español(Latinoamerica) » Mercado de Jugadores'}
    }

    prev = load_state()
    curr = {}
    is_first = len(prev) == 0

    if is_first:
        send_telegram_message(token, chat_id, "🚀 Monitor ManagerZone iniciado!")

    for f_id, f_info in forums.items():
        topics = get_forum_topics(f_info['url'])
        curr[f_id] = [t['id'] for t in topics]
        if not is_first:
            new = [t for t in topics if t['id'] not in prev.get(f_id, [])]
            for t in new:
                msg = f"🆕 <b>Novo tópico em {f_info['name']}</b>\n\n"
                msg += f"📝 <b>{t['title']}</b>\n🔗 {t['url']}"
                send_telegram_message(token, chat_id, msg)
                time.sleep(3)
    save_state(curr)

# ---------------- SERVIDOR FLASK PARA O RENDER ----------------
app = Flask(__name__)
@app.route("/")
def home():
    return "ManagerZone Monitor Online ✅"

def run_server():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

if __name__ == "__main__":
    Thread(target=run_server).start()
    while True:
        monitor()
        logger.info("⏳ A aguardar 10 minutos...")
        time.sleep(600)
