# main.py - Ultimate Phone Scanner + AI Chat (Bug-Free & Error Handled)
import os
import sys
import json
import subprocess
import threading
import queue
import time
import sqlite3
import requests
from datetime import datetime
from pathlib import Path

import kivy
kivy.require('2.1.0')
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.core.window import Window
from kivy.utils import platform

# طلب صلاحيات أندرويد تلقائياً عند الفتح
if platform == 'android':
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.INTERNET,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE
        ])
        from jnius import autoclass
        AndroidContext = autoclass('android.content.Context')
        PackageManager = autoclass('android.content.pm.PackageManager')
    except Exception as e:
        Logger.warning(f"Error loading Android modules: {e}")

# مفتاح Gemini API
API_KEY = "AIzaSyD3HVHPPbP29YqwXNDEp4yhMIHGFzL7Pyw"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API_KEY}"

cmd_queue = queue.Queue()
result_store = {}

def scan_directory(path, pattern=None):
    results = []
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                if pattern and not f.endswith(pattern) and not pattern in f:
                    continue
                full = os.path.join(root, f)
                try:
                    size = os.path.getsize(full)
                    mtime = os.path.getmtime(full)
                    results.append({'name': f, 'path': full, 'size': size, 'mtime': mtime})
                except: pass
    except Exception as e:
        results.append({'error': str(e)})
    return results

def read_file_content(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read(10000)
    except:
        try:
            with open(filepath, 'rb') as f:
                return f.read(1000).hex()
        except:
            return "Cannot read file"

def get_system_info():
    info = {}
    try: info['battery'] = subprocess.check_output(['dumpsys', 'battery'], text=True)
    except: pass
    try: info['memory'] = subprocess.check_output(['dumpsys', 'meminfo'], text=True)
    except: pass
    try: info['properties'] = subprocess.check_output(['getprop'], text=True)
    except: pass
    try: info['disk'] = subprocess.check_output(['df', '-h'], text=True)
    except: pass
    return info

def execute_command(action, params):
    if action == 'file_search':
        return scan_directory(params.get('path', '/sdcard'), params.get('pattern', ''))
    elif action == 'read_file':
        return read_file_content(params.get('path')) if params.get('path') else "No path provided"
    elif action == 'system_info':
        return get_system_info()
    elif action == 'run_shell':
        cmd = params.get('cmd')
        if cmd:
            try: return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
            except Exception as e: return str(e)
        return "No command"
    elif action == 'list_apps':
        if platform == 'android':
            try:
                pm = AndroidContext.getPackageManager()
                apps = pm.getInstalledApplications(PackageManager.GET_META_DATA)
                return [app.loadLabel(pm) for app in apps]
            except Exception as e: return f"Error listing apps: {e}"
        return "Android only feature"
    return f"Unknown action: {action}"

def parse_user_query(query):
    prompt = f"""
You are a command parser for a phone scanner. Given a user request, output a JSON with 'action' and 'params'.
Actions: file_search (params: path, pattern), read_file (path), system_info (no params), run_shell (cmd), list_apps (no params).
User request: {query}
Output only valid JSON.
"""
    try:
        response = requests.post(
            GEMINI_URL, 
            headers={'Content-Type': 'application/json'}, 
            json={"contents": [{"parts": [{"text": prompt}]}]}, 
            timeout=15
        )
        response.raise_for_status()
        text = response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        if text.startswith('```json'): text = text[7:]
        elif text.startswith('```'): text = text[3:]
        if text.endswith('```'): text = text[:-3]
        return json.loads(text.strip())
    except requests.exceptions.RequestException:
        return {'action': 'run_shell', 'params': {'cmd': 'echo "Network Error: Please check your internet connection or VPN."'}}
    except Exception as e:
        return {'action': 'run_shell', 'params': {'cmd': f'echo "Parse Error: {str(e)}"'}}

def worker():
    while True:
        try: query = cmd_queue.get(timeout=1)
        except queue.Empty: continue
            
        parsed = parse_user_query(query)
        action = parsed.get('action')
        params = parsed.get('params', {})
        result = execute_command(action, params)
        
        result_store[time.time()] = {'query': query, 'action': action, 'result': result}
        
        try:
            conn = sqlite3.connect('scanner_history.db')
            c = conn.cursor()
            c.execute('CREATE TABLE IF NOT EXISTS history (timestamp REAL, query TEXT, action TEXT, result TEXT)')
            c.execute('INSERT INTO history VALUES (?, ?, ?, ?)', (time.time(), query, action, json.dumps(result)))
            conn.commit()
            conn.close()
        except: pass
            
        Clock.schedule_once(lambda dt: update_ui(query, result), 0)

def update_ui(query, result):
    app = App.get_running_app()
    if app: app.root.ids.log_label.text += f"\n> {query}\n{str(result)[:500]}\n"

class ScannerApp(App):
    def build(self):
        self.title = "Phone Scanner AI"
        layout = BoxLayout(orientation='vertical')
        
        scroll = ScrollView()
        self.log_label = Label(text="Ready. Type your command below.\n", size_hint_y=None, text_size=(Window.width, None))
        self.log_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        self.log_label.id = 'log_label'
        scroll.add_widget(self.log_label)
        layout.add_widget(scroll)
        
        layout.ids = {'log_label': self.log_label}
        self.root = layout
        
        input_box = BoxLayout(size_hint_y=0.15)
        self.input_text = TextInput(hint_text='e.g., scan Downloads for pdf')
        send_btn = Button(text='Send', size_hint_x=0.2)
        send_btn.bind(on_press=self.send_command)
        input_box.add_widget(self.input_text)
        input_box.add_widget(send_btn)
        layout.add_widget(input_box)
        
        threading.Thread(target=worker, daemon=True).start()
        return layout

    def send_command(self, instance):
        query = self.input_text.text.strip()
        if query:
            cmd_queue.put(query)
            self.input_text.text = ''
            self.log_label.text += f"\n[Queued] {query}"

if __name__ == '__main__':
    ScannerApp().run()
