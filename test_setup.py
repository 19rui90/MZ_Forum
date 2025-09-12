import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_telegram_connection(token, chat_id):
    """Testa conexão com o Telegram"""
    print("🤖 Testando conexão com Telegram...")
    
    try:
        # Testa o bot
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(url, timeout=10)
        bot_info = response.json()
        
        if bot_info["ok"]:
            print(f"✅ Bot conectado: {bot_info['result']['first_name']} (@{bot_info['result']['username']})")
        else:
            print(f"❌ Erro no bot: {bot_info}")
            return False
        
        # Testa envio de mensagem
        test_message = f"🧪 <b>Teste de Conexão</b>\n\n✅ Bot funcionando!\n🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        
        send_url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': test_message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(send_url, data=data, timeout=10)
        result = response.json()
        
        if result["ok"]:
            print(f"✅ Mensagem de teste enviada com sucesso!")
            return True
        else:
            print(f"❌ Erro ao enviar mensagem: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na conexão: {e}")
        return False

def test_managerzone_access():
    """Testa acesso aos fóruns do ManagerZone"""
    print("\n⚽ Testando acesso aos fóruns do ManagerZone...")
    
    urls = [
        "https://www.managerzone.com/?p=forum&sub=topics&forum_id=125&sport=soccer",
        "https://www.managerzone.com/?p=forum&sub=topics&forum_id=126&sport=soccer", 
        "https://www.managerzone.com/?p=forum&sub=topics&forum_id=388&sport=soccer"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    success_count = 0
    
    for i, url in enumerate(urls, 1):
        try:
            print(f"  Testando Fórum {125 if i==1 else (126 if i==2 else 388)}...", end=" ")
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Procura por elementos de tópicos
                topic_elements = soup.find_all('a', href=lambda x: x and 'topic' in str(x))
                
                if topic_elements:
                    print(f"✅ OK ({len(topic_elements)} tópicos encontrados)")
                    success_count += 1
                else:
                    print("⚠️  Acessível mas sem tópicos detectados")
            else:
                print(f"❌ Erro HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro: {str(e)[:50]}...")
    
    print(f"\n📊 Resultado: {success_count}/3 fóruns acessíveis")
    return success_count > 0

def create_test_state():
    """Cria um estado de teste para simular novos tópicos"""
    print("\n🔧 Criando estado de teste...")
    
    test_state = {
        "125": [
            {"id": "test123", "title": "Tópico de Teste Antigo", "link": "https://example.com"}
        ],
        "126": [],
        "388": []
    }
    
    with open('forum_state.json', 'w', encoding='utf-8') as f:
        json.dump(test_state, f, ensure_ascii=False, indent=2)
    
    print("✅ Estado de teste criado em forum_state.json")

def simulate_manual_run():
    """Simula uma execução manual do monitor"""
    print("\n🏃‍♂️ Simulando execução manual...")
    
    # Verifica se as variáveis estão definidas
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHAT_ID')
    
    if not token or not chat_id:
        print("❌ TELEGRAM_TOKEN e CHAT_ID não estão definidos")
        print("💡 Configure-os como variáveis de ambiente ou no arquivo .env")
        return False
    
    try:
        # Importa e executa o monitor
        from monitor_single_run import ManagerZoneMonitor
        
        monitor = ManagerZoneMonitor(token, chat_id)
        monitor.run_single_check()
        
        print("✅ Execução manual concluída!")
        return True
        
    except ImportError:
        print("❌ Arquivo monitor_single_run.py não encontrado")
        return False
    except Exception as e:
        print(f"❌ Erro na execução: {e}")
        return False

def check_github_actions_status():
    """Fornece informações sobre como verificar GitHub Actions"""
    print("\n📊 Como verificar GitHub Actions:")
    print("1. Vá para seu repositório no GitHub")
    print("2. Clique na aba 'Actions'")
    print("3. Veja o histórico de execuções")
    print("4. Clique em uma execução para ver os logs detalhados")
    print("5. Procure por:")
    print("   ✅ 'Execução manual concluída!'")
    print("   📝 'X novos tópicos encontrados'")
    print("   ❌ Mensagens de erro")

def comprehensive_test():
    """Executa todos os testes de uma vez"""
    print("🧪 TESTE COMPLETO DO MONITOR MANAGERZONE")
    print("=" * 50)
    
    # Carrega configurações
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHAT_ID')
    
    if not token or not chat_id:
        print("⚠️  Configurando variáveis de teste...")
        print("Defina TELEGRAM_TOKEN e CHAT_ID como variáveis de ambiente")
        return False
    
    # Executa testes
    telegram_ok = test_telegram_connection(token, chat_id)
    managerzone_ok = test_managerzone_access()
    
    print(f"\n📋 RESUMO DOS TESTES:")
    print(f"🤖 Telegram: {'✅ OK' if telegram_ok else '❌ FALHA'}")
    print(f"⚽ ManagerZone: {'✅ OK' if managerzone_ok else '❌ FALHA'}")
    
    if telegram_ok and managerzone_ok:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("✅ Seu monitor deve funcionar corretamente")
        
        # Oferece criar estado de teste
        create_test = input("\n🔧 Criar estado de teste para simular novos tópicos? (s/n): ")
        if create_test.lower() == 's':
            create_test_state()
            print("💡 Execute o monitor novamente para ver notificações de 'novos' tópicos")
            
    else:
        print("\n❌ ALGUNS TESTES FALHARAM")
        print("🔧 Verifique as configurações antes de fazer o deploy")
    
    print(f"\n🕐 Teste executado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    return telegram_ok and managerzone_ok

if __name__ == "__main__":
    comprehensive_test()
    check_github_actions_status(), 
