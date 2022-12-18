# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name
# pylint: disable=global-statement
# pylint: disable=bare-except,broad-except
import argparse
import asyncio
import json
import signal
import time
import traceback
import aiodns
import aiofile
import aiohttp
from tabulate import tabulate
from masnet import get_peers_file_path, get_error_file_path, load_exclusion
from masnet import get_version, set_verbose, set_working_dir, debug, verbose
from masnet import set_debug, is_excluded, get_path, is_debug, is_verbose
from masnet import get_excluded_patterns


RUN = True
num_nodes = 0
num_links = 0
num_errors = 0
num_skips = 0
num_timeouts = 0


# pylint: disable=unused-argument
def signal_handler(sig, frame):
    global RUN
    RUN = False


async def save_error(domain, error):
    async with aiofile.async_open(get_path('masnet.download.errors'),
                                  'a') as afp:
        await afp.write('%s %s\n' % (domain, error))


async def save_skip(domain):
    async with aiofile.async_open(get_path('masnet.download.skips'),
                                  'a') as afp:
        await afp.write('%s\n' % domain)


async def save_time(domain, download_time):
    async with aiofile.async_open(get_path('masnet.download.times'),
                                  'a') as afp:
        await afp.write('%s %d\n' % (domain, download_time))


async def save_visit(domain):
    async with aiofile.async_open(get_path('masnet.download.visits'),
                                  'a') as afp:
        await afp.write('%s\n' % domain)


# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
async def fetch(session, domain, timeout, scheduled, q):
    global num_errors, num_nodes, num_skips, num_links, num_timeouts
    url = 'https://%s/api/v1/instance/peers' % domain
    try:
        start = time.time()
        async with session.get(url, timeout=timeout) as resp:
            if resp.status == 200:
                resp_as_text = await resp.text()
                await save_time(domain,
                                int((time.time() - start) * 1000))
                peers = json.loads(resp_as_text)
                if peers is None:
                    num_errors = num_errors + 1
                    await save_error(domain, 'peers is None')
                elif not isinstance(peers, list):
                    num_errors = num_errors + 1
                    await save_error(domain, 'peers is not list')
                else:
                    doc = {'domain': domain,
                           'peers': peers}
                    async with aiofile.async_open(get_path('%s.peers.json' % domain),
                                                  'w') as afp:
                        await afp.write(json.dumps(doc))
                    num_nodes = num_nodes + 1
                    await save_visit(domain)
                    for peer in peers:
                        if peer is None:
                            continue
                        if len(peer.strip()) == 0:
                            continue
                        if is_excluded(peer):
                            await save_skip(peer)
                            num_skips = num_skips + 1
                            continue
                        num_links = num_links + 1
                        if peer not in scheduled:
                            scheduled.add(peer)
                            await q.put(peer)
            else:
                num_errors = num_errors + 1
                await save_error(domain, 'HTTP: %d' % resp.status)
    except aiohttp.ClientError as e:
        num_errors = num_errors + 1
        error = e.__class__.__name__
        await save_error(domain, error)
    except aiodns.error.DNSError as e:
        num_errors = num_errors + 1
        error = e.__class__.__name__
        await save_error(domain, error)
    except asyncio.exceptions.TimeoutError as e:
        num_errors = num_errors + 1
        num_timeouts = num_timeouts + 1
        error = e.__class__.__name__
        await save_error(domain, error)
    except asyncio.CancelledError as e:
        num_errors = num_errors + 1
        error = e.__class__.__name__
        await save_error(domain, error)
    except json.decoder.JSONDecodeError as e:
        num_errors = num_errors + 1
        error = e.__class__.__name__
        await save_error(domain, error)
    except UnicodeError as e:
        num_errors = num_errors + 1
        error = e.__class__.__name__
        await save_error(domain, error)
    except Exception as e:
        num_errors = num_errors + 1
        error = e.__class__.__name__
        await save_error(domain, error)
        if is_verbose():
            traceback.print_exc()


# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-locals
# pylint: disable=too-many-statements
async def download(start_domain,
                   timeout,
                   num_tasks):

    start = time.time()
    barrier = asyncio.Semaphore(num_tasks)
    scheduled = set()
    q = asyncio.Queue()
    resolver = aiohttp.resolver.AsyncResolver(nameservers=['8.8.8.8',
                                                           '8.8.4.4'])
    conn = aiohttp.TCPConnector(limit=2*num_tasks,
                                force_close=True, # no need for keep-alive
                                use_dns_cache=False,
                                resolver=resolver)
    async with aiohttp.ClientSession(connector=conn,
                                     timeout=timeout) as session:
        domain_counts = {}
        scheduled.add(start_domain)
        q.put_nowait(start_domain)
        last = time.time()
        signal.signal(signal.SIGINT, signal_handler)
        cnt = 0
        cnt_threshold = 5
        top5 = []
        def print_status():
            elapsed = time.time() - start
            hours = int(elapsed / 3600)
            minutes = int((elapsed - hours * 3600) / 60)
            seconds = elapsed - minutes * 60 - hours * 3600
            print('q:%06d a:%06d s:%06d ' \
                  'N:%06d L:%09d ' \
                  'e:%08d s:%08d to:%04d ' \
                  't:%02d:%02d:%02d' % (q.qsize(), len(asyncio.all_tasks()),
                                        len(scheduled),
                                        num_nodes, num_links,
                                        num_errors, num_skips, num_timeouts,
                                        hours, minutes, seconds), flush=True)
            verbose(tabulate(top5))
        global RUN
        while RUN and (cnt < cnt_threshold):
            if (time.time() - last) > 1:
                print_status()
                last = time.time()
                if len(asyncio.all_tasks()) == 1:
                    cnt = cnt + 1
                else:
                    cnt = 0

            if q.qsize() > 0:
                if not barrier.locked():
                    async with barrier:
                        domain = await q.get()
                        debug(domain)
                        if is_verbose():
                            parts = domain.split('.')
                            if len(parts) > 2:
                                count_key = '.'.join(parts[-(len(parts)-1):])
                                domain_counts[count_key] = domain_counts.get(count_key,
                                                                             0) + 1
                                top5 = list(sorted(domain_counts.items(),
                                                   key=lambda t: t[1], reverse=True))[:5]
                        asyncio.create_task(fetch(session,
                                                  domain,
                                                  timeout,
                                                  scheduled,
                                                  q))
            # this is needed to give time to async loop operation
            await asyncio.sleep(0)

        print_status()

        if RUN:
            print('traversal finished. data is complete.')
        else:
            print('traversal terminated early. data is incomplete !!!')

        current_task = asyncio.current_task()

        print('cancelling tasks...')
        running_tasks = filter(lambda x: x != current_task,
                               asyncio.all_tasks())
        for task in running_tasks:
            try:
                task.cancel()
            except:
                pass

        print('waiting for tasks...')
        running_tasks = set(filter(lambda x: x != current_task,
                                   asyncio.all_tasks()))
        for task in running_tasks:
            try:
                await task
            except:
                pass
        print('bye.')


# pylint: disable=too-many-statements
def main():
    print('masnet v%s' % get_version())
    parser = argparse.ArgumentParser(prog='masnet.download',
                                     description='',
                                     epilog='')

    parser.add_argument('-d', '--dir',
                        help='use specified directory for files',
                        default=None,
                        required=False)

    parser.add_argument('--debug',
                        help='enables debug logging',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('-v', '--verbose',
                        help='enable verbose logging, mostly for development',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('-e', '--exclude-file',
                        help='exclude the domains and all of their ' \
                             'subdomains in the file specified',
                        required=False)

    parser.add_argument('-n', '--num-tasks',
                        help='use specified number of Python asyncio tasks for download',
                        type=int,
                        required=False,
                        default=100)

    parser.add_argument('-s', '--start-domain',
                        help='domains to start traversal from (default: mastodon.social)',
                        required=False,
                        default='mastodon.social')

    parser.add_argument('-t', '--timeout',
                        help='use specified number of seconds for timeout ' \
                             '(default: system default)',
                        type=int,
                        required=False,
                        default=60)

    args = parser.parse_args()
    set_debug(args.debug)
    set_verbose(args.verbose)
    debug(str(args))
    load_exclusion(args.exclude_file)
    set_working_dir(args.dir)

    # truncate fixed name output files
    with open(get_path('masnet.download.errors'), 'w'):
        pass
    with open(get_path('masnet.download.visits'), 'w'):
        pass
    with open(get_path('masnet.download.skips'), 'w'):
        pass
    with open(get_path('masnet.download.times'), 'w'):
        pass

    asyncio.run(download(args.start_domain,
                         args.timeout,
                         args.num_tasks))


if __name__ == '__main__':
    main()
