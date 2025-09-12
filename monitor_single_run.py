import requests
import json
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedManagerZoneMonitor:
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
        
        # Arquivos para armazenar estado
        self.state_file = 'forum_state.json'
        self.status_file = 'monitor_status.json'
        self.load_state()
        self.load_status()
        
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
    
    def load_status(self):
        """Carrega status do monitor"""
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    self.status = json.load(f)
            else:
                self.status = {
                    'first_run': True,
                    'total_runs': 0,
                    'total_notifications': 0,
                    'last_run': None,
                    'last_success': None,
                    'errors': [],
                    'forum_status': {}
                }
        except Exception as e:
            logger.error(f"Erro ao carregar status: {e}")
            self.status = {
                'first_run': True,
                'total_runs': 0,
                'total_notifications': 0,
                'last_run': None,
                'last_success': None,
                'errors': [],
                'forum_status': {}
            }
            
    def save_state(self):
        """Salva o estado atual dos tópicos"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.previous_topics, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
    
    def save_status(self):
        """Salva status do monitor"""
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(self.status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar status: {e}")
    
    def add_error(self, error_msg):
        """Adiciona erro ao log de status"""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'error': str(error_msg)
        }
        self.status['errors'].append(error_entry)
        
        # Mantém apenas os últimos 10 erros
        if len(self.status['errors']) > 10:
            self.status['errors'] = self.status['errors'][-10:]
    
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
            self.add_error(f"Telegram: {e}")
            return False
    
    def send_status_report(self):
        """Envia relatório de status diário"""
        now = datetime.now()
        
        # Verifica se deve enviar relatório (uma vez por dia)
        last_report = self.status.get('last_daily_report')
        if last_report:
            last_report_date = datetime.fromisoformat(last_report).date()
            if last_report_date == now.date():
                return  # Já enviou hoje
        
        # Calcula estatísticas
        total_topics_monitored = sum(len(topics) for topics in self.previous_topics.values())
        
        # Monta relatório
        report = f"📊 <b>Relatório Diário - Monitor ManagerZone</b>\n\n"
        report += f"📈 <b>Estatísticas:</b>\n"
        report += f"• Execuções: {self.status['total_runs']}\n"
        report += f"• Notificações enviadas: {self.status['total_notifications']}\n"
        report += f"• Tópicos monitorados: {total_topics_monitored}\n"
        report += f"• Última verificação: {self.status['last_run']}\n\n"
        
        # Status dos fóruns
        report += f"🏟️ <b>Status dos Fóruns:</b>\n"
        for forum_id, status in self.status.get('forum_status', {}).items():
            forum_name = f"Fórum {forum_id}"
            status_emoji = "✅" if status.get('accessible', False) else "❌"
            topic_count = status.get('topic_count', 0)
            report += f"• {forum_name}: {status_emoji} ({topic_count} tópicos)\n"
        
        # Erros recentes
        recent_errors = [e for e in self.status['errors'] if 
                        (now - datetime.fromisoformat(e['timestamp'])).days < 1]
        
        if recent_errors:
            report += f"\n⚠️ <b>Erros nas últimas 24h:</b> {len(recent_errors)}\n"
        else:
            report += f"\n✅ <b>Sem erros nas últimas 24h</b>\n"
        
        report += f"\n🤖 Monitor funcionando desde {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        if self.send_telegram_message(report):
            self.status['last_daily_report'] = now.isoformat()
    
    def run_single_check(self):
        """Executa uma única verificação"""
        start_time = datetime.now()
        logger.info(f"Iniciando verificação #{self.status['total_runs'] + 1}")
        
        self.status['total_runs'] += 1
        self.status['last_run'] = start_time.isoformat()
        
        forum_names = {
            125: "Fórum 125",
            126: "Fórum 126", 
            388: "Fórum 388"
        }
        
        new_topics_found = 0
        forums_checked = 0
        
        # Mensagem de primeira execução
        if self.status['first_run']:
            welcome_msg = f"🚀 <b>Monitor ManagerZone Iniciado!</b>\n\n"
            welcome_msg += f"✅ Monitorando 3 fóruns do ManagerZone\n"
            welcome_msg += f"🔔 Você será notificado sobre novos tópicos\n"
            welcome_msg += f"📊 Relatórios diários automáticos\n\n"
            welcome_msg += f"🕐 Primeira execução: {start_time.strftime('%d/%m/%Y %H:%M')}"
            
            self.send_telegram_message(welcome_msg)
            self.status['first_run'] = False
        
        for url in self.forum_urls:
            try:
                forum_id = url.split('forum_id=')[1].split('&')[0]
                forum_name = forum_names.get(int(forum_id), f"Fórum {forum_id}")
                
                logger.info(f"Verificando {forum_name}...")
                
                current_topics = self.get_forum_topics(url)
                forums_checked += 1
                
                # Atualiza status do fórum
                self.status['forum_status'][forum_id] = {
                    'accessible': len(current_topics) > 0,
                    'topic_count': len(current_topics),
                    'last_check': start_time.isoformat()
                }
                
                if not current_topics:
                    logger.warning(f"Nenhum tópico encontrado em {forum_name}")
                    continue
                
                previous_topics = self.previous_topics.get(forum_id, [])
                previous_ids = {topic['id'] if isinstance(topic, dict) else topic for topic in previous_topics}
                current_ids = {topic['id'] for topic in current_topics}
                
                new_topic_ids = current_ids - previous_ids
                new_topics = [topic for topic in current_topics if topic['id'] in new_topic_ids]
                
                if new_topics:
                    new_topics_found += len(new_topics)
                    logger.info(f"Encontrados {len(new_topics)} novos tópicos em {forum_name}")
                    
                    for topic in new_topics:
                        message = f"🆕 <b>Novo tópico em {forum_name}</b>\n\n"
                        message += f"📝 <b>{topic['title']}</b>\n"
                        message += f"🔗 <a href='{topic['link']}'>Ver tópico</a>\n\n"
                        message += f"🕐 {start_time.strftime('%d/%m/%Y %H:%M')}"
                        
                        if self.send_telegram_message(message):
                            logger.info(f"Notificação enviada: {topic['title']}")
                            self.status['total_notifications'] += 1
                
                self.previous_topics[forum_id] = current_topics
                
            except Exception as e:
                logger.error(f"Erro ao verificar fórum {url}: {e}")
                self.add_error(f"Forum {forum_id}: {e}")
        
        # Atualiza status geral
        if forums_checked > 0:
            self.status['last_success'] = start_time.isoformat()
        
        # Salva estados
        self.save_state()
        self.save_status()
        
        # Log final
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Verificação concluída em {duration:.1f}s - {forums_checked} fóruns, {new_topics_found} novos tópicos")
        
        # Envia relatório diário se necessário
        self.send_status_report()
        
        if new_topics_found == 0:
            logger.info("Nenhum novo tópico encontrado")

def main():
    telegram_token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHAT_ID')
    
    if not telegram_token or not chat_id:
        logger.error("TELEGRAM_TOKEN e CHAT_ID devem estar definidos")
        return
    
    monitor = EnhancedManagerZoneMonitor(telegram_token, chat_id)
    monitor.run_single_check()

if __name__ == "__main__":
    main()
