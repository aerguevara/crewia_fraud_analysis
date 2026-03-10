import os
import time
import requests
import threading
from collections import deque
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from crewai_fraud_analysis.crew import CrewaiFraudAnalysis

class TelegramChat:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        # Soporta múltiples IDs separados por comas
        raw_ids = os.getenv("TELEGRAM_CHAT_ID", "")
        self.authorized_ids = [s.strip() for s in raw_ids.split(",") if s.strip()]
        
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        
        # Diccionario de historiales aislados por chat_id
        # chat_id -> deque(maxlen=3)
        self.histories = {}

    def get_updates(self):
        url = f"{self.base_url}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 30}
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get("result", [])
        except Exception as e:
            print(f"Error al obtener actualizaciones: {e}")
        return []

    def send_chat_action(self, chat_id, stop_event):
        """Mantiene el estado 'typing' cada 4 segundos."""
        url = f"{self.base_url}/sendChatAction"
        payload = {"chat_id": chat_id, "action": "typing"}
        while not stop_event.is_set():
            try:
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                print(f"Error al enviar acción: {e}")
            time.sleep(4)

    def send_message(self, chat_id, text):
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code != 200:
                print(f"Error de Telegram ({response.status_code}): {response.text}")
                if "can't parse" in response.text:
                    payload["parse_mode"] = ""
                    requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Error al enviar mensaje: {e}")

    def _get_history(self, chat_id):
        """Obtiene o crea el historial para un chat específico."""
        if chat_id not in self.histories:
            self.histories[chat_id] = deque(maxlen=3)
        return self.histories[chat_id]

    def _build_history_context(self, chat_id):
        """Construye un string con los últimos intercambios del chat_id."""
        history = self._get_history(chat_id)
        if not history:
            return "Sin historial previo."
        lines = []
        for user_msg, bot_msg in history:
            lines.append(f"Usuario: {user_msg}")
            lines.append(f"Bot: {bot_msg}")
        return "\n".join(lines)

    def chat_with_model(self, chat_id, user_text):
        print(f"Invocando CrewAI para chat_id: {chat_id}...")
        
        stop_typing = threading.Event()
        typing_thread = threading.Thread(target=self.send_chat_action, args=(chat_id, stop_typing))
        typing_thread.daemon = True
        typing_thread.start()
        
        try:
            crew_instance = CrewaiFraudAnalysis().crew_for_chat()
            history_ctx = self._build_history_context(chat_id)
            result = crew_instance.kickoff(inputs={
                "user_input": user_text,
                "chat_history": history_ctx,
            })
            
            ai_content = str(result.raw if hasattr(result, 'raw') else result)
            
            prefixes_to_strip = [
                "Thought:", "Action:", "Action Input:", "Observation:", 
                "Final Answer:", "Final Answer", "<|im_start|>", "<|im_end|>",
                "I now know the final answer", "I will now answer"
            ]
            
            prefixes_to_strip = [
                "Thought:", "Action:", "Action Input:", "Observation:", 
                "Final Answer:", "Final Answer", "<|im_start|>", "<|im_end|>",
                "I now know the final answer", "I will now answer"
            ]
            
            for prefix in prefixes_to_strip:
                if prefix in ai_content:
                    if "Final Answer:" in ai_content:
                        ai_content = ai_content.split("Final Answer:")[-1].strip()
                    else:
                        ai_content = ai_content.replace(prefix, "").strip()
            
            import re
            ai_content = re.sub(r'<[^>]+>', '', ai_content).strip()
            
            print(f"DEBUG: Resultado limpio: {ai_content}")
            
            # Guardar en su historial propio
            history = self._get_history(chat_id)
            history.append((user_text[:200], ai_content[:200]))
            
            return ai_content
        except Exception as e:
            print(f"Error en el chat de CrewAI: {e}")
            return f"Problema técnico: {str(e)[:100]}. ¿Intentamos de nuevo?"
        finally:
            stop_typing.set()
            typing_thread.join(timeout=0.5)

    def run(self):
        print(f"🤖 Bot Multi-Agente iniciado. IDs autorizados: {self.authorized_ids}")
        
        print("Sincronizando mensajes antiguos...")
        updates = self.get_updates()
        if updates:
            self.last_update_id = updates[-1]["update_id"]
            print(f"Ignorando {len(updates)} mensajes antiguos.")

        while True:
            updates = self.get_updates()
            for update in updates:
                self.last_update_id = update["update_id"]
                message = update.get("message", {})
                chat_id = str(message.get("chat", {}).get("id"))
                
                if chat_id in self.authorized_ids and "text" in message:
                    user_text = message["text"]
                    
                    if user_text.startswith('/'):
                        if user_text == '/start':
                            self.send_message(chat_id, "¡Buenas! Soy tu asistente de Adventure Streak. ¿Qué quieres analizar?")
                        elif user_text == '/clear':
                            if chat_id in self.histories:
                                self.histories[chat_id].clear()
                            self.send_message(chat_id, "🧹 Tu historial ha sido borrado.")
                        continue

                    response = self.chat_with_model(chat_id, user_text)
                    self.send_message(chat_id, response)
                elif "text" in message:
                    print(f"Acceso denegado para chat_id: {chat_id}")
            time.sleep(1)

if __name__ == "__main__":
    chat = TelegramChat()
    chat.run()
