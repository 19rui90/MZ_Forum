#!/usr/bin/env python3
import requests, json, os, time, hashlib, logging, re
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
from zoneinfo import ZoneInfo

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
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'pt-PT,pt;q=0.9,en;q=0.8'}
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
            # extrair topic_id real
            match = re.search(r'(?:topic_id|thread_id)=(\d+)', href)
            if not match:
                continue
            topic_id = match.group(1)

            # montar URL completa
            if href.startswith('?'):
                full_url = "https://www.managerzone.com/" + href
            elif href.startswith('/'):
                full_url = "https://www.managerzone.com" + href
            else:
                full_url = href

            topics.append({'id': topic_id, 'title': title[:120], 'url': full_url})
            seen.add(title)
            if len(topics) >= 20:
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
        '125': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=125&sport=soccer', 'name': '🇵🇹 Português(Portugal)\n      ManagerZone Talk'},
        '126': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=126&sport=soccer', 'name': '🇵🇹 Português(Portugal)\n      Perguntas e Respostas'},
        '388': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=388&sport=soccer', 'name': '🇵🇹 Português(Portugal)\n      Discussão sobre as Selecções Nacionais'},
        '47': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=47&sport=soccer', 'name': '🇧🇷 Português(Brasil)\n      ManagerZone talk'},
        '49': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=49&sport=soccer', 'name': '🇧🇷 Português(Brasil)\n      Perguntas & Respostas'},
        '253': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=253&sport=soccer', 'name': '🇦🇷 Español(Latinoamerica)\n      ManagerZone Habla'},
        '255': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=255&sport=soccer', 'name': '🇦🇷 Español(Latinoamerica)\n      Preguntas y Respuestas'},
        '10': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=10&sport=soccer', 'name': '🏴 English\n      ManagerZone Talk'},
        '12': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=12&sport=soccer', 'name': '🏴 English\n      Questions & Answers'},
        '387': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=387&sport=soccer', 'name': '🏴 English\n      Simulator Development Feedback'},
        '316': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=316&sport=soccer', 'name': '🇨🇳 Chinese\n      2 游戏热点以及官方杯赛讨论 MZ Talk'},
        '318': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=318&sport=soccer', 'name': '🇨🇳 Chinese\n      1 新手及疑问解答 Newbie and Q&A'},
        '1': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=1&sport=soccer', 'name': '🇸🇪 Svenska\n      Allmänt om ManagerZone [MZ Talk]'},
        '4': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=4&sport=soccer', 'name': '🇸🇪 Svenska\n      Frågor & Svar [Q&A]'},
        '26': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=26&sport=soccer', 'name': '🇵🇱 Polski\n      Rozmowy ManagerZone [MZ Talk]'},
        '25': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=25&sport=soccer', 'name': '🇵🇱 Polski\n      Pytania i Odpowiedzi [Q&A]'},
        '90': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=90&sport=soccer', 'name': '🇹🇷 Türkçe\n      ManagerZone muhabbetleri [MZ Talk]'},
        '91': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=91&sport=soccer', 'name': '🇹🇷 Türkçe\n      Sorular & Cevaplar [Q&A]'},
        '65': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=65&sport=soccer', 'name': '🇷🇴 Romanian\n      Vorbe despre ManagerZone [MZ Talk]'},
        '63': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=63&sport=soccer', 'name': '🇷🇴 Romanian\n      Intrebari si Raspunsuri [Q&A]'},
        '102': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=102&sport=soccer', 'name': '🇮🇹 Italiano\n      Chiacchiere su ManagerZone [MZ Talk]'},
        '105': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=105&sport=soccer', 'name': '🇮🇹 Italiano\n      Domande e Risposte [Q&A]'},
        '19': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=19&sport=soccer', 'name': '🇪🇦 Español(España)\n      ManagerZone habla'},
        '21': {'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=21&sport=soccer', 'name': '🇪🇦 Español(España)\n      Preguntas y Respuestas'}
        # ADICIONAR  Estonia e Grecia ???



    }

    prev = load_state()
    curr = {}
    is_first = len(prev) == 0

    if is_first:
        send_telegram_message(token, chat_id, "🚀 Monitor ManagerZone iniciado! (primeira execução)")
        logger.info("Primeira execução: estado inicial carregado.")

    for f_id, f_info in forums.items():
        topics = get_forum_topics(f_info['url'])
        curr[f_id] = [t['id'] for t in topics]

        if not is_first:
            new_topics = [t for t in topics if t['id'] not in prev.get(f_id, [])]
            for t in new_topics:
                msg = (f"<b>{f_info['name']}</b>\n\n"
                       f"<a href='{t['url']}'>{t['title']}</a>\n\n ")
                send_telegram_message(token, chat_id, msg)
                time.sleep(2)

    save_state(curr)

# ---------------- SERVIDOR FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "ManagerZone Monitor Online ✅"

def run_server():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    Thread(target=run_server).start()
    while True:
        try:
            monitor()
        except Exception as e:
            logger.error(f"Erro no monitor: {e}")
        logger.info("⏳ A aguardar 5 minutos para próxima verificação...")
        time.sleep(300)
