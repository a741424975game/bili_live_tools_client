import asyncio
import sys
from client import Client

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    limit = sys.argv[1]
    offset = sys.argv[2]
    client = Client(loop, 264, 'localhost', 8069, proxy_pool_host='localhost', proxy_pool_port=5010,
                    limit=int(limit), offset=int(offset))
    client.run()
