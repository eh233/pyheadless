import argparse
import asyncio
import base64
import codecs
import json
import logging
import os
import platform
import random
import re
import sched
import threading
import time
from concurrent import futures
from os.path import dirname, realpath

import pyquery
import requests
from pyppeteer import launch
from requests.cookies import cookiejar_from_dict

BIN_URL = 'http://soft.vpser.net/lnmp/lnmp0.6-full.tar.gz'
BASE_URL = 'https://cnplus.xyz'
USER_URL = '{}/user'.format(BASE_URL)
ROOT_PATH = dirname(realpath(__file__))
DATA_PATH = os.path.join(ROOT_PATH, 'data')
ACCOUNT_LIST = {'haha@dmeo666.cn': 1081, 'atcaoyufei+2@gmail.com': 1082, 'liuming@demo666.cn': 1083,
                'atcaoyufei@alumni.albany.edu': 1084, '20130444229@mail.sdufe.edu.cn': 1085, 'neeyuese@163.com': 1086}
sess = requests.session()

lock = threading.Lock()

_scheduler = sched.scheduler(time.time, time.sleep)
_USER_NODE = {}
_run_count = 0
_max_count = 50


async def close_dialog(dialog):
    await dialog.dismiss()


async def accept_dialog(dialog):
    await dialog.accept()


def decode(string):
    if len(string) % 4 != 0:
        string = string + (4 - len(string) % 4) * '='
    return str(base64.urlsafe_b64decode(string.encode()), 'UTF-8')


def to_date(timestamp):
    time_struct = time.localtime(timestamp)
    return time.strftime('%Y-%m-%d', time_struct)


def generate_config(subscribe_link, port, config_file):
    html = requests.get(subscribe_link, timeout=5).text
    string = decode(html)
    lines = string.split('\n')
    nodes = []
    for line in lines:
        line = line.replace('vmess://', '')
        vmess = decode(line)
        if not vmess or vmess.find('倍率0|') != -1:
            continue
        rate = re.search(r'倍率([0-9.]+)', vmess)
        nodes.append((rate.group(1), json.loads(vmess)))

    if not len(nodes):
        raise Exception(f'find node fail. {subscribe_link}')

    nodes.sort(key=lambda k: k[0])
    node = nodes[-1][1]
    config = get_default_config()
    config['inbounds'][0]['port'] = port
    config['outbounds'][0]['settings']['vnext'][0]['address'] = node['add']
    config['outbounds'][0]['streamSettings']['wsSettings']['path'] = node['path']
    config['outbounds'][0]['streamSettings']['wsSettings']['headers']['host'] = node['add']
    config['outbounds'][0]['settings']['vnext'][0]['port'] = int(node['port'])
    config['outbounds'][0]['settings']['vnext'][0]['users'][0]['id'] = node['id']
    with codecs.open(config_file, 'w', 'utf-8') as f:
        f.write(json.dumps(config))
    return node


def get_default_config():
    with codecs.open(os.path.join(DATA_PATH, 'defaults', 'default_client.json')) as f:
        return json.loads(f.read())


def download(port):
    _PROXIES = {
        'http': 'http://127.0.0.1:%s' % port,
        'https': 'http://127.0.0.1:%s' % port,
    }
    n = 0
    t = (random.randint(1024, 2048)) * 1024
    with requests.get(BIN_URL, stream=True, proxies=_PROXIES, timeout=10) as res:
        for chunk in res.iter_content(1024):
            n += len(chunk)
            if n > t:
                break
    return n


def start_v2ray(config_file, port):
    data = []
    _cmd = 'nohup /usr/bin/v2ray/v2ray -config {} > /dev/null 2>&1 &'.format(config_file)
    data.append(_cmd)

    os.popen(_cmd)
    time.sleep(2)

    try:
        info = download(port)
        data.append(info)
    except Exception as e:
        pass

    # time.sleep(2)
    # cmd = "kill -9 $(ps -ef |grep '%s' |grep -v grep | awk '{print $2}')" % config_file
    # os.popen(cmd)
    return data


def user_info(username, cookies):
    sess.cookies = cookies
    html = sess.get(USER_URL).text
    doc = pyquery.PyQuery(html)
    elements = doc('.la-top')
    element_user = doc('.user-info-main').eq(0)
    element_user_money = doc('.user-info-main').eq(1)

    data = [username, element_user('.nodetype dd').text(), element_user_money('.nodetype').text()]
    for element in elements.items():
        name = element('.traffic-info').text().strip()
        val = element('.card-tag').text().strip()
        data.append('%s:%s' % (name, val))

    user_level = doc('#days-level-expire').parents('.dl-horizontal')
    a = user_level('dt').eq(0).text().strip()
    b = user_level('dd').eq(0).text().strip().replace('event', '').strip()

    data.append(a)
    data.append(b)
    return data


def main(param):
    t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    user_name, port = param
    cookie_file = os.path.join(DATA_PATH, '{}.cookie'.format(user_name))
    config_file = os.path.join(DATA_PATH, '{}.json'.format(user_name))

    data = [t, user_name, _USER_NODE.get(user_name)]
    if os.path.exists(cookie_file):
        with codecs.open(cookie_file, 'r', 'utf-8') as f:
            cookies = f.read()
        cookies = cookiejar_from_dict(json.loads(cookies))
        data.extend(user_info(user_name, cookies))

    if os.path.exists(config_file):
        data.extend(start_v2ray(config_file, port))
    return data


async def get_subscribe_link(user_name):
    subscribe_link = ''
    headless = False if platform.system() == 'Windows' else True
    browser = await launch(ignorehttpserrrors=True, headless=headless,
                           args=['--disable-infobars', '--no-sandbox'])
    page = await browser.newPage()
    try:
        page.on('dialog', lambda dialog: asyncio.ensure_future(close_dialog(dialog)))
        await page.goto('{}/auth/login'.format(BASE_URL), {'waitUntil': 'load'})
        await page.type('#email', user_name)
        await page.type('#passwd', 'hack3321')
        await page.click('#login')

        await page.waitForSelector('.user-info-main', {'visible': True})

        # print(await page.JJeval('.nodetype', '(elements => elements.map(e => e.innerText))'))

        user_level = await page.Jeval('.nodetype', 'el => el.innerText')
        user_level = str(user_level).strip()
        print('{}: {}'.format(user_name, user_level))
        if user_level.find('普通') != -1:
            await page.goto('{}/user/shop'.format(BASE_URL), {'waitUntil': 'load'})
            shop_btn = await page.xpath('//a[@class="btn btn-brand-accent shop-btn"]')
            await shop_btn[1].click()
            await asyncio.sleep(1)
            await page.click('#coupon_input')
            await asyncio.sleep(1)
            await page.click('#order_input')
            await asyncio.sleep(3)
            await page.goto(USER_URL, {'waitUntil': 'load'})
            user_level = await page.Jeval('.nodetype', 'el => el.innerText')
            user_level = str(user_level).strip()
            print('{}: {}'.format(user_name, user_level))

        traffic = ','.join(await page.JJeval('.progressbar', '(elements => elements.map(e => e.innerText))'))
        print('{}: {}'.format(user_name, traffic.replace('\n', '')))

        check_in = await page.querySelector('#checkin')
        if check_in:
            await page.click('#checkin')
            await asyncio.sleep(3)
            await page.click('#result_ok')

        cookies = await page.cookies()
        new_cookies = {}
        for cookie in cookies:
            new_cookies[cookie['name']] = cookie['value']

        with codecs.open(os.path.join(DATA_PATH, '{}.cookie'.format(user_name)), 'w', 'utf-8') as f:
            f.write(json.dumps(new_cookies))

        subscribe_link = await page.Jeval('#all_v2ray_windows input', 'el => el.value')
    except Exception as e1:
        logging.exception(e1)

    await page.close()
    await browser.close()

    return subscribe_link


def test():
    nodes = generate_config('https://rss.cnrss.xyz/link/iLebuiG9PURb6dDK?mu=2', 1081,
                            os.path.join(DATA_PATH, 'hah.json'))
    print(nodes)


def init_config():
    os.popen('rm -f {}/*'.format(DATA_PATH))
    for _user_name, _port in ACCOUNT_LIST.items():
        config_file = os.path.join(DATA_PATH, '{}.json'.format(_user_name))
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(get_subscribe_link(_user_name))
        print('')
        node = generate_config(res, _port, config_file)
        print(node)
        _USER_NODE[_user_name] = node['ps']


def script_main():
    global _run_count
    _run_count += 1

    tasks = []
    for k, v in ACCOUNT_LIST.items():
        tasks.append([k, v])

    n = int(len(tasks) / 2)
    print('------------------------------------------------')
    with futures.ThreadPoolExecutor(n) as executor:
        try:
            for result in executor.map(main, tasks, chunksize=n):
                print(result)
                print()
        except Exception as e:
            logging.exception(e)

    cmd = "kill -9 $(ps -ef |grep '%s' |grep -v grep | awk '{print $2}')" % DATA_PATH
    os.popen(cmd)

    if _run_count < _max_count:
        _scheduler.enter(100, 0, script_main)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', nargs='?')
    parser.add_argument('--max', default=30, type=int)
    parser.add_argument('--init', action='store_true', default=False)

    args = parser.parse_args()
    params = vars(args)

    _max_count = params.get('max')
    _action = params.get('action')

    if _action:
        eval(_action)()
    elif params.get('init'):
        _scheduler.enter(0, 0, init_config)
        _scheduler.enter(100, 0, script_main)
        _scheduler.run()
    else:
        _scheduler.enter(0, 0, script_main)
        _scheduler.run()
