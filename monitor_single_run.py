import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ManagerZoneMonitor:
    def __init__(self, telegram_token, chat_id):
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.session = requests.Session()
        
        # URLs dos fóruns para monitorar
        self.forum_urls = [
            "https://www.managerzone.com/?p=forum&sub=topics&forum_id=125&sport=soccer",
            "https://www.managerzone.com/?p=forum&sub=topics&forum_id=126&sport=soccer", 
            "https://www.managerzone.com/?p=forum&sub=topics&forum_id=388&sport=soccer"
        ]
        
        # Headers para simular um navegador
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Arquivo para armazenar estado dos tópicos
        self.state_file = 'forum_state.json'
        self.load_state()
        
    def load_state(self):
        """Carrega o estado anterior dos tópicos"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.previous_topics = json.load(f)
            else:
                self.previous_topics = {}
        except Exception as e:
            logger.error(f"Erro ao carregar estado: {e}")
            self.previous_topics = {}
            
    def save_state(self):
        """Salva o estado atual dos tópicos"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.previous_topics, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
    
    def get_forum_topics(self, url):
        """Extrai os tópicos de uma página de fórum"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            topics = []
            
            # Procura por elementos que contenham tópicos
            topic_elements = soup.find_all(['a', 'tr', 'div'], class_=lambda x: x and ('topic' in x.lower() or 'thread' in x.lower()))
            
            if not topic_elements:
                topic_elements = soup.select('table tr td a[href*="topic"]')
                if not topic_elements:
                    topic_elements = soup.select('a[href*="topic"]')
            
            for element in topic_elements[:10]:
                try:
                    if element.name == 'a':
                        title = element.get_text(strip=True)
                        link = element.get('href')
                    else:
                        link_elem = element.find('a')
                        if link_elem:
                            title = link_elem.get_text(strip=True)
                            link = link_elem.get('href')
                        else:
                            continue
                    
                    if title and link and len(title) > 3:
                        if link.startswith('?'):
                            link = f"https://www.managerzone.com/{link}"
                        elif link.startswith('/'):
                            link = f"https://www.managerzone.com{link}"
                        elif not link.startswith('http'):
                            link = f"https://www.managerzone.com/{link}"
                            
                        topics.append({
                            'title': title[:100],
                            'link': link,
                            'id': str(hash(title + link))
                        })
                except Exception as e:
                    logger.debug(f"Erro ao processar elemento: {e}")
                    continue
                    
            return topics
            
        except Exception as e:
            logger.error(f"Erro ao buscar tópicos de {url}: {e}")
            return []
    
    def send_telegram_message(self, message):
        """Envia mensagem para o Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem Telegram: {e}")
            return False
    
    def run_single_check(self):
        """Executa uma única verificação (para GitHub Actions)"""
        logger.info("Executando verificação única...")
        
        forum_names = {
            125: "Fórum 125",
            126: "Fórum 126", 
            388: "Fórum 388"
        }
        
        new_topics_found = False
        
        for url in self.forum_urls:
            try:
                forum_id = url.split('forum_id=')[1].split('&')[0]
                forum_name = forum_names.get(int(forum_id), f"Fórum {forum_id}")
                
                logger.info(f"Verificando {forum_name}...")
                
                current_topics = self.get_forum_topics(url)
                previous_topics = self.previous_topics.get(forum_id, [])
                
                previous_ids = {topic['id'] if isinstance(topic, dict) else topic for topic in previous_topics}
                current_ids = {topic['id'] for topic in current_topics}
                
                new_topic_ids = current_ids - previous_ids
                new_topics = [topic for topic in current_topics if topic['id'] in new_topic_ids]
                
                if new_topics:
                    new_topics_found = True
                    logger.info(f"Encontrados {len(new_topics)} novos tópicos em {forum_name}")
                    
                    for topic in new_topics:
                        message = f"🆕 <b>Novo tópico em {forum_name}</b>\n\n"
                        message += f"📝 <b>{topic['title']}</b>\n"
                        message += f"🔗 <a href='{topic['link']}'>Ver tópico</a>\n"
                        message += f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                        
                        if self.send_telegram_message(message):
                            logger.info(f"Notificação enviada: {topic['title']}")
                
                self.previous_topics[forum_id] = current_topics
                
            except Exception as e:
                logger.error(f"Erro ao verificar fórum {url}: {e}")
        
        # Salva estado
        self.save_state()
        
        if not new_topics_found:
            logger.info("Nenhum novo tópico encontrado")

def main():
    telegram_token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHAT_ID')
    
    if not telegram_token or not chat_id:
        logger.error("TELEGRAM_TOKEN e CHAT_ID devem estar definidos")
        return
    
    monitor = ManagerZoneMonitor(telegram_token, chat_id)
    monitor.run_single_check()

if __name__ == "__main__":
    main()
