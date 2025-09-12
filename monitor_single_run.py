#!/usr/bin/env python3
import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging
import time
import hashlib

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def send_telegram_message(token, chat_id, message):
    """Envia mensagem para o Telegram"""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        response = requests.post(url, data=data, timeout=10)
        return response.json().get('ok', False)
    except Exception as e:
        logger.error(f"Erro Telegram: {e}")
        return False

def get_forum_topics(url, max_retries=2):
    """Busca APENAS os tópicos principais de um fórum (não respostas)"""
    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-PT,pt;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(url, headers=headers, timeout=25)
            
            if response.status_code != 200:
                logger.error(f"HTTP {response.status_code} para {url}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            topics = []
            
            # Procura especificamente por tópicos na estrutura do ManagerZone
            topic_links = soup.find_all('a', href=lambda x: x and ('topic_id=' in x or 'thread_id=' in x))
            
            if not topic_links:
                # Fallback: procura por links que parecem ser tópicos
                all_links = soup.find_all('a', href=True)
                topic_links = [link for link in all_links 
                              if link.get('href') and ('topic' in link.get('href').lower() or 'thread' in link.get('href').lower())
                              and len(link.get_text(strip=True)) > 10]
            
            seen_titles = set()
            
            for link in topic_links:
                try:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # Filtros para garantir que é um tópico principal
                    if (len(title) < 5 or
                        title.lower() in ['ver', 'reply', 'responder', 'last post', 'último post', 'view', 'read'] or
                        'javascript:' in href or
                        '#' in href or
                        title in seen_titles or
                        any(word in title.lower() for word in ['page', 'página', 'next', 'previous', 'anterior', 'seguinte'])):
                        continue
                    
                    # Constrói URL completa
                    if href.startswith('?'):
                        full_url = f"https://www.managerzone.com/{href}"
                    elif href.startswith('/'):
                        full_url = f"https://www.managerzone.com{href}"
                    elif not href.startswith('http'):
                        continue
                    else:
                        full_url = href
                    
                    # Cria ID único baseado no título e URL
                    unique_string = f"{title}|{full_url}"
                    topic_id = hashlib.md5(unique_string.encode()).hexdigest()[:12]
                    
                    topics.append({
                        'id': topic_id,
                        'title': title.strip()[:120],
                        'url': full_url
                    })
                    
                    seen_titles.add(title)
                    
                    if len(topics) >= 8:  # Máximo 8 tópicos por fórum
                        break
                        
                except Exception as e:
                    logger.debug(f"Erro ao processar link: {e}")
                    continue
            
            logger.info(f"✅ Encontrados {len(topics)} tópicos únicos")
            return topics
            
        except Exception as e:
            logger.error(f"❌ Erro ao acessar fórum (tentativa {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(3)
            continue
    
    return []

def load_state():
    """Carrega estado anterior"""
    try:
        if os.path.exists('forum_state.json'):
            with open('forum_state.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"📂 Estado carregado: {len(data)} fóruns")
                return data
    except Exception as e:
        logger.error(f"Erro ao carregar estado: {e}")
    
    return {}

def save_state(state):
    """Salva estado atual"""
    try:
        with open('forum_state.json', 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        logger.info("💾 Estado salvo com sucesso")
    except Exception as e:
        logger.error(f"Erro ao salvar estado: {e}")

def main():
    # Configurações
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHAT_ID')
    
    if not token or not chat_id:
        logger.error("❌ TELEGRAM_TOKEN e CHAT_ID são obrigatórios!")
        return
    
    logger.info("🤖 Iniciando Monitor ManagerZone Expandido...")
    
    # Configuração completa dos fóruns com nomes baseados na estrutura típica do MZ
    forums = {
        # Fóruns Portugueses Existentes
        '125': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=125&sport=soccer',
            'name': 'Português(Portugal) » Discussão Geral'
        },
        '126': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=126&sport=soccer', 
            'name': 'Português(Portugal) » Discussão sobre as Selecções Nacionais'
        },
        '388': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=388&sport=soccer',
            'name': 'Português(Portugal) » Outros Desportos'
        },
        
        # Novos Fóruns Adicionados
        '47': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=47&sport=soccer',
            'name': 'Deutsch » Allgemeine ManagerZone Diskussion'
        },
        '49': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=49&sport=soccer',
            'name': 'Deutsch » Nationalmannschaft Diskussion'
        },
        '253': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=253&sport=soccer',
            'name': 'Español(Latinoamerica) » ManagerZone Habla'
        },
        '255': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=255&sport=soccer',
            'name': 'Español(Latinoamerica) » Selecciones Nacionales'
        },
        '10': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=10&sport=soccer',
            'name': 'English » ManagerZone Talk'
        },
        '12': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=12&sport=soccer',
            'name': 'English » National Teams Discussion'
        },
        '387': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=387&sport=soccer',
            'name': 'English » Other Sports'
        },
        '318': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=318&sport=soccer',
            'name': 'Türkçe » ManagerZone Konuşmaları'
        },
        '316': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=316&sport=soccer',
            'name': 'Türkçe » Milli Takım Tartışmaları'
        },
        '19': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=19&sport=soccer',
            'name': 'Français » Discussion Générale ManagerZone'
        },
        '21': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=21&sport=soccer',
            'name': 'Français » Équipes Nationales'
        },
        '26': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=26&sport=soccer',
            'name': 'Italiano » Discussione Generale ManagerZone'
        },
        '25': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=25&sport=soccer',
            'name': 'Italiano » Squadre Nazionali'
        },
        '1': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=1&sport=soccer',
            'name': 'Svenska » Allmänt om ManagerZone'
        },
        '4': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=4&sport=soccer',
            'name': 'Svenska » Landslag Diskussion'
        },
        '90': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=90&sport=soccer',
            'name': 'Nederlands » Algemene ManagerZone Discussie'
        },
        '91': {
            'url': 'https://www.managerzone.com/?p=forum&sub=topics&forum_id=91&sport=soccer',
            'name': 'Nederlands » Nationale Teams'
        }
    }
    
    # Carrega estado anterior
    previous_state = load_state()
    current_state = {}
    
    # Verifica se é primeira execução
    is_first_run = len(previous_state) == 0
    total_new_topics = 0
    forums_checked = 0
    forums_failed = 0
    
    # Mensagem de inicialização (apenas na primeira vez)
    if is_first_run:
        msg = "🚀 <b>Monitor ManagerZone Expandido Iniciado!</b>\n\n"
        msg += f"📍 <b>Monitorando {len(forums)} fóruns:</b>\n"
        msg += "• Português (Portugal)\n"
        msg += "• English\n"
        msg += "• Deutsch\n"
        msg += "• Español (Latinoamérica)\n"
        msg += "• Français\n"
        msg += "• Italiano\n"
        msg += "• Svenska\n"
        msg += "• Nederlands\n"
        msg += "• Türkçe\n\n"
        msg += "🔔 <i>Apenas novos tópicos serão notificados</i>\n"
        msg += f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        if send_telegram_message(token, chat_id, msg):
            logger.info("📱 Mensagem de inicialização enviada")
    
    # Verifica cada fórum com pausa entre requests
    for i, (forum_id, forum_info) in enumerate(forums.items()):
        logger.info(f"🔍 ({i+1}/{len(forums)}) Verificando: {forum_info['name']}")
        
        # Pausa entre requests para evitar sobrecarga
        if i > 0:
            time.sleep(2)
        
        current_topics = get_forum_topics(forum_info['url'])
        
        if not current_topics:
            logger.warning(f"⚠️  Nenhum tópico encontrado em {forum_info['name']}")
            # Mantém estado anterior se não conseguir buscar
            current_state[forum_id] = previous_state.get(forum_id, [])
            forums_failed += 1
            continue
        
        forums_checked += 1
        
        # IDs dos tópicos atuais
        current_topic_ids = [topic['id'] for topic in current_topics]
        current_state[forum_id] = current_topic_ids
        
        # Se não é primeira execução, verifica novos tópicos
        if not is_first_run:
            previous_topic_ids = set(previous_state.get(forum_id, []))
            new_topic_ids = set(current_topic_ids) - previous_topic_ids
            
            # Encontra os tópicos novos
            new_topics = [topic for topic in current_topics if topic['id'] in new_topic_ids]
            
            if new_topics:
                logger.info(f"🆕 {len(new_topics)} novos tópicos em {forum_info['name']}")
                
                for topic in new_topics:
                    msg = f"🆕 <b>Novo tópico em {forum_info['name']}</b>\n\n"
                    msg += f"📝 <b>{topic['title']}</b>\n\n"
                    msg += f"🔗 <a href='{topic['url']}'>Ver tópico</a>\n"
                    msg += f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                    
                    if send_telegram_message(token, chat_id, msg):
                        logger.info(f"✅ Notificação enviada: {topic['title'][:50]}...")
                        total_new_topics += 1
                        time.sleep(3)  # Pausa entre mensagens para evitar spam
                    else:
                        logger.error(f"❌ Falha ao enviar: {topic['title'][:50]}...")
            else:
                logger.debug(f"📋 Nenhum tópico novo em {forum_info['name']}")
        else:
            logger.info(f"📋 Primeira execução - {len(current_topics)} tópicos registrados")
    
    # Salva estado atual
    save_state(current_state)
    
    # Log final
    if is_first_run:
        logger.info(f"🎯 Primeira execução concluída - baseline estabelecido para {forums_checked} fóruns")
        if forums_failed > 0:
            logger.warning(f"⚠️  {forums_failed} fóruns não puderam ser acessados")
    else:
        logger.info(f"✅ Verificação concluída - {total_new_topics} novos tópicos encontrados")
        logger.info(f"📊 Estatísticas: {forums_checked} fóruns verificados, {forums_failed} falharam")
        
        if total_new_topics == 0:
            logger.info("📝 Nenhum novo tópico nos fóruns monitorados")

if __name__ == "__main__":
    main()