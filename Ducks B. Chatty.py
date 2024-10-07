import requests
import tkinter as tk
from tkinter import messagebox
import threading
import time
import json
import os

CONFIG_FILE = 'Ducks B. Chatty.json'

class ChatRelay:
    def __init__(self, api_key, webhooks):
        self.api_key = api_key
        self.webhooks = webhooks
        self.last_checked_id = {'global': 0, 'trade': 0, 'cartel': 0}
        self.active = {'global': False, 'trade': False, 'cartel': False}
        self.sent_messages = set()  # Track sent messages to avoid duplicates

    def fetch_all_messages(self, chat_type):
        url = f"https://cartelempire.online/api/chat?type={chat_type}&key={self.api_key}"
        response = requests.get(url)
        if response.ok:
            data = response.json()
            return data.get(f"{chat_type}Chat", [])
        return []

    def send_recent_messages(self, chat_type):
        messages = self.fetch_all_messages(chat_type)
        if messages:
            messages_sorted = sorted(messages, key=lambda x: int(x['posted']))
            recent_messages = messages_sorted[-5:]  # Get the last 5
            for msg in sorted(recent_messages, key=lambda x: int(x['posted'])):
                self.send_message(chat_type, msg)

    def listen_for_messages(self, chat_type):
        self.send_recent_messages(chat_type)
        while self.active[chat_type]:
            url = f"https://cartelempire.online/api/chat?type={chat_type}&key={self.api_key}"
            response = requests.get(url)
            if response.ok:
                data = response.json()
                self.handle_response(data, chat_type)
            time.sleep(2)  # Poll every 2 seconds

    def handle_response(self, data, chat_type):
        messages = data.get(f"{chat_type}Chat", [])
        for msg in messages:
            if msg['id'] > self.last_checked_id[chat_type]:
                self.last_checked_id[chat_type] = msg['id']
                self.send_message(chat_type, msg)

    def send_message(self, chat_type, msg):
        message_id = msg['id']
        if message_id in self.sent_messages:
            return  # Skip if already sent

        self.sent_messages.add(message_id)  # Mark message as sent
        timestamp = time.strftime('%H:%M', time.localtime(int(msg['posted'])))
        formatted_message = f"{timestamp} **{msg['name']}**: {msg['message']}"
        self.send_to_discord(chat_type, formatted_message)

    def send_to_discord(self, chat_type, message):
        webhook_url = self.webhooks[chat_type]
        if webhook_url:
            requests.post(webhook_url, json={"content": message})

class ChatRelayApp:
    def __init__(self, master):
        self.master = master
        master.title("Ducks B. Chatty")
        master.geometry("275x320")  # Set the window size (width x height)

        self.api_key_label = tk.Label(master, text="API Key:")
        self.api_key_label.pack()
        self.api_key_entry = tk.Entry(master)
        self.api_key_entry.pack()

        self.webhook_labels = {}
        self.webhook_entries = {}
        self.status_labels = {}
        chat_types = ['global', 'trade', 'cartel']
        for chat_type in chat_types:
            label = tk.Label(master, text=f"{chat_type.capitalize()} Webhook:")
            label.pack()
            entry = tk.Entry(master)
            entry.pack()
            self.webhook_labels[chat_type] = label
            self.webhook_entries[chat_type] = entry
            
            status_label = tk.Label(master, text="Status: Stopped", fg="red")
            status_label.pack()
            self.status_labels[chat_type] = status_label

            button = tk.Button(master, text=f"Toggle {chat_type.capitalize()} Relay", command=lambda ct=chat_type: self.toggle_relay(ct))
            button.pack()

        self.chat_relay = None

        self.load_config()

        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self.api_key_entry.insert(0, config.get('api_key', ''))
                for chat_type in ['global', 'trade', 'cartel']:
                    self.webhook_entries[chat_type].insert(0, config.get('webhooks', {}).get(chat_type, ''))

    def save_config(self):
        config = {
            'api_key': self.api_key_entry.get(),
            'webhooks': {chat_type: self.webhook_entries[chat_type].get() for chat_type in ['global', 'trade', 'cartel']}
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

    def toggle_relay(self, chat_type):
        api_key = self.api_key_entry.get()
        webhook_url = self.webhook_entries[chat_type].get()
        if not api_key or not webhook_url:
            messagebox.showwarning("Input Error", "API Key and Webhook URL must be provided.")
            return

        if self.chat_relay is None:
            self.chat_relay = ChatRelay(api_key, {ct: self.webhook_entries[ct].get() for ct in ['global', 'trade', 'cartel']})
        
        # Toggle the active state
        self.chat_relay.active[chat_type] = not self.chat_relay.active[chat_type]

        if self.chat_relay.active[chat_type]:
            self.chat_relay.send_recent_messages(chat_type)  # Fetch and send recent messages
            self.status_labels[chat_type].config(text="Status: Running", fg="green")
            threading.Thread(target=self.chat_relay.listen_for_messages, args=(chat_type,), daemon=True).start()
        else:
            self.chat_relay.active[chat_type] = False  # Stop listening
            self.status_labels[chat_type].config(text="Status: Stopped", fg="red")

    def on_closing(self):
        if self.chat_relay:
            # Stop all relays
            for chat_type in self.chat_relay.active.keys():
                self.chat_relay.active[chat_type] = False
        self.save_config()  # Save configuration before closing
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatRelayApp(root)
    root.geometry("275x320")  # Ensure size is set again after creation
    root.mainloop()
