import asyncio
import async_timeout
import aiohttp
import requests
import time
import re
from pybililive.bililive import BiliLive

QUERY_RAFFLE_URL = 'http://api.live.bilibili.com/activity/v1/Raffle/check'
RAFFLE_URL = 'http://api.live.bilibili.com/activity/v1/Raffle/join'
TV_URL = 'http://api.live.bilibili.com/gift/v2/smalltv/join'
IP_PORT_REGEX = '[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}:[0-9]{1,5}'


class Client(object):
    __slots__ = ['loop', 'bili_live', 'cookies_pool', 'odoo_address', 'proxy_pool_address']

    def __init__(self, loop, room_id, odoo_host, odoo_port=80, proxy_pool_host=None, proxy_pool_port=80):
        self.loop = loop
        self.odoo_address = 'http://%s:%s' % (odoo_host, odoo_port)
        self.proxy_pool_address = 'http://%s:%s' % (proxy_pool_host, proxy_pool_port) if proxy_pool_host else None
        self.cookies_pool = self.get_cookies()
        self.bili_live = BiliLive(
            room_id=room_id,
            cmd_func_dict={
                'SYS_MSG': self.join_small_tv,
                'SYS_GIFT': self.join_raffle
            },
        )

    def _get_proxy(self):
        try:
            proxy = requests.get("http://127.0.0.1:5010/get/").content.decode('utf-8')
        except:
            return None
        else:
            if re.match(IP_PORT_REGEX, proxy):
                return 'http://%s' % proxy
            else:
                return None

    async def get_proxy(self, session):
        if not self.proxy_pool_address:
            return None

        try:
            async with session.get('%s/get/' % self.proxy_pool_address) as response:
                if response.status == 200:
                    proxy = await response.content.read()
                else:
                    proxy = None
        except Exception as e:
            print(e)
            return None
        else:
            if re.match(IP_PORT_REGEX, proxy.decode('utf-8')):
                return 'http://%s' % proxy.decode('utf-8')
            else:
                return None

    def _get_account_amount(self):
        r = requests.get('%s/account/amount' % self.odoo_address).json()
        return r['data']

    def get_cookies(self):
        account_amount = self._get_account_amount()
        last = account_amount % 100
        account_cookies = []
        range_index = int(account_amount / 100)
        i = 0
        while range_index > i:
            r = requests.get(
                '%s/account/cookies' % self.odoo_address,
                params={'offset': i * 100, 'limit': 100}
            ).json()
            account_cookies += r['data']
            i += 1
        else:
            r = requests.get(
                '%s/account/cookies' % self.odoo_address,
                params={'offset': i * 100, 'limit': last}
            ).json()
            account_cookies += r['data']
        print("账号总数: %s" % len(account_amount))
        return {e['id']: e['cookies'] for e in account_cookies}

    def update_cookies_pool(self):
        pass

    async def _get(self, session, url, params=None, headers=None, proxy_times=5):
        headers = headers if headers else {}
        try_times = 0
        proxy = await self.get_proxy(session)
        data = {}
        while proxy and proxy_times > try_times:
            try:
                proxy = await self.get_proxy(session)
                async with session.get(url, proxy=proxy, params=params, headers=headers, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        break
            except Exception as e:
                print(e)
        else:
            try:
                async with session.get(url, params=params, headers=headers, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
            except Exception as e:
                print(e)
        return data

    async def _post(self, url, data=None, headers=None):
        try:
            headers = headers if headers else {}
            async with aiohttp.ClientSession() as session:
                with async_timeout.timeout(10):
                    async with session.post(
                            url=url,
                            data=data,
                            headers=headers
                    ) as res:
                        r = await res.json()
        except Exception as e:
            return None
        else:
            return r

    async def join_raffle(self, live, msg):
        if 'roomid' in msg.keys():
            params = {
                'roomid': msg['roomid']
            }
            r = requests.get(QUERY_RAFFLE_URL, params=params).json()
            if r:
                for d in r['data']:
                    raffle_id = d['raffleId']
                    try:
                        await self._join_raffle(msg['roomid'], raffle_id)
                    except Exception:
                        pass
                    print(u'Join %s Raffle' % msg['roomid'])

    async def _join_raffle(self, room_id, raffle_id):
        params = {
            'roomid': room_id,
            'raffleId': raffle_id
        }
        headers = {
            'Host': 'api.live.bilibili.com',
            'Origin': 'http://live.bilibili.com',
            'Referer': 'http://live.bilibili.com/%s' % room_id,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:57.0) Gecko/20100101 Firefox/57.0'
        }
        print(time.time())
        async with aiohttp.ClientSession(loop=self.loop) as session:
            for uid, cookie in self.cookies_pool.items():
                try:
                    await self._get(session, RAFFLE_URL, params, headers=headers)
                    await  self._get(
                        session,
                        '%s/raffle/join' % self.odoo_address,
                        params={
                            'account_id': uid,
                            'room_id': room_id,
                            'raffle_extend_id': raffle_id
                        },
                        proxy_times=0
                    )
                    print('用户id: %s 加入抽奖' % uid)
                except Exception as e:
                    print(e)
        print(time.time())
        return True

    async def join_small_tv(self, live, msg):
        if 'roomid' in msg.keys():
            params = {
                'roomid': msg['roomid'],
                'raffleId': msg['tv_id'],
                '_': int(time.time() * 100)
            }
            try:
                await self._join_small_tv(params)
            except Exception:
                pass

    async def _join_small_tv(self, params):
        print(u'Join %s SmallTV' % params['roomid'])
        print(time.time())
        async with aiohttp.ClientSession(loop=self.loop) as session:
            for uid, cookies in self.cookies_pool.items():
                await self._get(session, TV_URL, params, headers={'Cookie': cookies})
                await  self._get(
                    session,
                    '%s/raffle/join' % self.odoo_address,
                    params={
                        'account_id': uid,
                        'room_id': params['roomid'],
                        'raffle_extend_id': params['tv_id']
                    }
                )
                print('用户id: %s 加入小电视' % uid)
        print(time.time())

    def run(self):
        asyncio.ensure_future(self.bili_live.connect())
        self.loop.set_debug(True)
        try:
            self.loop.run_forever()
        except:
            self.loop.close()
