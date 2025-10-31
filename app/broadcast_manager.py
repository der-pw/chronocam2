import asyncio

# === Globale Liste der verbundenen Clients ===
clients = set()

async def broadcast(message: dict):
    """Sendet Nachricht an alle verbundenen SSE-Clients."""
    dead = []
    for client in clients:
        try:
            await client.put(message)
        except Exception:
            dead.append(client)
    for d in dead:
        clients.remove(d)
