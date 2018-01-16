import asyncio
from client import Client

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    client = Client(loop, 264, 'localhost', 8069, proxy_pool_host='localhost', proxy_pool_port=5010)
    client.run()
