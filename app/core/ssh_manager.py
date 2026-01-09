import paramiko
import uuid
from typing import Dict

# Session Storage
# session_id -> {"client": SSHClient, "sftp": SFTPClient}
sessions: Dict[str, Dict] = {}

class SSHManager:
    def __init__(self):
        pass

    def create_session(self, host, user, password, port=22):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=host, port=port, username=user, password=password)
            sftp = client.open_sftp()
            session_id = str(uuid.uuid4())
            sessions[session_id] = {
                "client": client,
                "sftp": sftp,
                "host": host,
                "user": user
            }
            return session_id
        except Exception as e:
            print(f"Connection failed: {e}")
            return None

    def get_session(self, session_id):
        return sessions.get(session_id)

    def close_session(self, session_id):
        if session_id in sessions:
            try:
                sessions[session_id]["sftp"].close()
                sessions[session_id]["client"].close()
            except:
                pass
            del sessions[session_id]

manager = SSHManager()
