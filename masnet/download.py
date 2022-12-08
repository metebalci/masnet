# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name
# pylint: disable=global-statement
# pylint: disable=bare-except,broad-except
import argparse
from collections import deque
import http
import gzip
import json
import math
import os
import socket
import sys
import time
from threading import Thread, Lock
import traceback
from urllib.error import URLError, HTTPError
import urllib.request
from masnet import __version__


VERBOSE = False
OUTPUT_DIR = None
THREADS_RUN = True
ERROR_HANDLER_TERMINATED = False
SKIP_HANDLER_TERMINATED = False
DOWNLOAD_TERMINATED = {}
DECODE_TERMINATED = False
PROCESS_TERMINATED = False

num_domains = 0
num_errors = 0
num_errors_lock = Lock()
num_skips = 0
num_downloads = 0
avg_download = 0
sum_download = 0

def get_peers_filename(domain):
    return '%s.peers.json.gz' % domain.replace('/', '_')

def get_error_filename(domain):
    return '%s.error' % domain.replace('/', '_')

def get_thread_status(num_threads):
    cnt = num_threads
    for t in DOWNLOAD_TERMINATED.values():
        if t:
            cnt = cnt - 1
    p = math.ceil(10*cnt/num_threads)
    return '%s%s%s%s%s' % ('.' if ERROR_HANDLER_TERMINATED else 'X',
                           '.' if SKIP_HANDLER_TERMINATED else 'X',
                           '.' if cnt == 0 else ('X' if p == 10 else str(p)),
                           '.' if DECODE_TERMINATED else 'X',
                           '.' if PROCESS_TERMINATED else 'X')


def are_all_downloads_terminated():
    global DOWNMLOAD_TERMINATED
    for t in DOWNLOAD_TERMINATED.values():
        if not t:
            return False
    return True


def verbose(s):
    if VERBOSE:
        print(s, flush=True)


def get_path(fname):
    return os.path.join(OUTPUT_DIR, fname)


def skip_handler(idx,
                 qskip,
                 skips_filepath):

    global THREADS_RUN, SKIP_HANDLER_TERMINATED, num_skips

    with open(skips_filepath, 'w') as fp:
        try:
            while THREADS_RUN:
                time.sleep(0)
                try:
                    req = qskip.popleft()
                    domain = req['domain']
                    num_skips = num_skips + 1
                    fp.write(domain)
                    fp.write('\n')
                except IndexError as e:
                    pass
        except:
            traceback.print_exc()

    SKIP_HANDLER_TERMINATED = True

def error_handler(idx,
                  qerror,
                  errors_filepath):

    global THREADS_RUN, ERROR_HANDLER_TERMINATED, num_errors, num_errors_lock

    with open(errors_filepath, 'w') as fp:
        try:
            while THREADS_RUN:
                time.sleep(0)
                try:
                    req = qerror.popleft()
                    domain = req['domain']
                    with num_errors_lock:
                        num_errors = num_errors + 1
                    err = req['err']
                    fp.write(domain)
                    fp.write('\n')
                    error_file_path = get_path(get_error_filename(domain))
                    with open(error_file_path, 'w') as f:
                        f.write(err)
                except IndexError as e:
                    pass
        except:
            traceback.print_exc()

    ERROR_HANDLER_TERMINATED = True

def download(idx,
             qerror,
             qdownload,
             qdecode,
             qprocess,
             dtimes,
             discard,
             timeout=-1):

    global THREADS_RUN, DOWNLOAD_TERMINATED
    global num_downloads, avg_download, sum_download
    global num_errors, num_errors_lock

    DOWNLOAD_TERMINATED[idx] = False

    try:
        while THREADS_RUN:
            time.sleep(0)
            try:
                req = qdownload.popleft()
                domain = req['domain']
                error_file_path = get_path(get_error_filename(domain))
                if os.path.exists(error_file_path):
                    with num_errors_lock:
                        num_errors = num_errors + 1
                    continue
                # if not discarding, try to load existing file first
                if not discard:
                    peers_file_path = get_path(get_peers_filename(domain))
                    if os.path.exists(peers_file_path):
                        try:
                            with gzip.open(peers_file_path, 'rb') as f:
                                res = json.load(f)
                                qprocess.append({'domain': domain,
                                                 'peers': res['peers']})
                                continue
                        except:
                            pass
                peers_url = 'https://%s/api/v1/instance/peers' % domain
                res = None
                err = None
                elapsed = -1
                try:
                    num_downloads = num_downloads + 1
                    start = time.perf_counter()
                    if timeout > 0:
                        with urllib.request.urlopen(peers_url,
                                                    timeout=timeout) as req:
                            res = req.read().decode('utf-8')
                    else:
                        with urllib.request.urlopen(peers_url) as req:
                            res = req.read().decode('utf-8')
                    elapsed = time.perf_counter() - start
                    dtimes.append(elapsed)
                    sum_download = sum_download + elapsed
                    avg_download = sum_download / num_downloads
                except HTTPError as e:
                    err = '%s %s' % (e.__class__.__name__, e.code)
                except URLError as e:
                    err = '%s %s' % (e.__class__.__name__, e.reason)
                # this became an alias to TimeoutError
                except socket.timeout as e:
                    err = e.__class__.__name__
                except TimeoutError as e: # this
                    err = e.__class__.__name__
                except ConnectionError as e:
                    err = e.__class__.__name__
                except UnicodeError as e:
                    err = '%s %s %s' % (e.__class__.__name__,
                                        e.encoding,
                                        e.reason)
                if err is not None:
                    qerror.append({'domain': domain, 'err': err})
                elif res is not None:
                    qdecode.append({'domain': domain,
                                    'elapsed': elapsed,
                                    'peers_json': res})
                else:
                    raise Exception('why res is None?')
            except IndexError as e:
                pass
    except:
        traceback.print_exc()

    DOWNLOAD_TERMINATED[idx] = True


def decode(idx,
           qerror,
           qdecode,
           qprocess,
           visits_filepath):

    global THREADS_RUN, DECODE_TERMINATED

    with open(visits_filepath, 'w') as fp:
        try:
            while THREADS_RUN:
                time.sleep(0)
                try:
                    req = qdecode.popleft()
                    domain = req['domain']
                    elapsed = req['elapsed']
                    peers_file_path = get_path(get_peers_filename(domain))
                    try:
                        peers = json.loads(req['peers_json'])
                        peers_json = {'domain': domain,
                                      'elapsed': elapsed,
                                      'peers': peers}
                        with gzip.open(peers_file_path, 'wb') as f:
                            f.write(json.dumps(peers_json).encode('utf-8'))
                        fp.write(domain)
                        fp.write('\n')
                        qprocess.append({'domain': domain, 'peers': peers})
                    except json.JSONDecodeError as e:
                        err = e.__class__.__name__
                        qerror.append({'domain': domain, 'err': err})
                except IndexError as e:
                    pass
        except:
            traceback.print_exc()

    DECODE_TERMINATED = True

def process(idx,
            qerror,
            qskip,
            qprocess,
            qdownload,
            excluded,
            start_domain):

    global THREADS_RUN, PROCESS_TERMINATED, num_domains


    domains = set()

    # send start domain
    domains.add(start_domain)
    qdownload.append({'domain': start_domain})

    try:
        while THREADS_RUN:
            time.sleep(0)
            try:
                req = qprocess.popleft()
                domain = req['domain']
                num_domains = num_domains + 1
                peers = req['peers']
                cnt_new_peers = 0
                skip = False
                for peer in peers:
                    # this is not needed, but just to handle bad responses safely
                    if peer is not None and len(peer) > 0:
                        for exclude_suffix in excluded:
                            if peer.endswith(exclude_suffix):
                                qskip.append({'domain': peer})
                                skip = True
                        if not skip and peer not in domains:
                            cnt_new_peers = cnt_new_peers + 1
                            domains.add(peer)
                            qdownload.append({'domain': peer})
            except IndexError as e:
                pass
    except:
        traceback.print_exc()

    PROCESS_TERMINATED = True

# pylint: disable=too-many-statements
def main():
    print('masnet v%s' % __version__)
    parser = argparse.ArgumentParser(prog='masnet.download',
                                     description='',
                                     epilog='')

    parser.add_argument('-d', '--discard',
                        help='discard cached files, redownloads everything (default: false)',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('--demo',
                        help='run for a minute then no new visits is scheduled, use for demo',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('-e', '--exclude-file',
                        help='exclude the domains and all of their ' \
                             'subdomains in the file specified (default: ' \
                             'None but activitypub-troll.cf, ' \
                             'misskey-forkbomb.cf, repl.co is excluded)',
                        required=False)

    parser.add_argument('-n', '--num-threads',
                        help='use specified number of Python threads (default: 100)',
                        type=int,
                        required=False,
                        default=100)

    parser.add_argument('-o', '--output-dir',
                        help='use specified directory for files, it creates ' \
                             'the directory if not exists ' \
                             '(default: current directory)',
                        required=False)

    parser.add_argument('--output-errors',
                        help='save list of errors encountered to file (default: errors.out)',
                        required=False,
                        default='errors.out')

    parser.add_argument('--output-skips',
                        help='save list of skipped domains due to exclusion (default: skips.out)',
                        required=False,
                        default='skips.out')

    parser.add_argument('--output-visits',
                        help='save list of visited domains to file (default: visits.out)',
                        required=False,
                        default='visits.out')

    parser.add_argument('-s', '--start-domain',
                        help='domains to start traversal from (default: mastodon.social)',
                        required=False,
                        default='mastodon.social')

    parser.add_argument('-t', '--timeout',
                        help='use specified number of seconds for timeout ' \
                             '(default: system default)',
                        type=int,
                        required=False,
                        default=-1)

    parser.add_argument('-v', '--verbose',
                        help='enable verbose logging, mostly for development',
                        action='store_true',
                        required=False,
                        default=False)

    args = parser.parse_args()

    global VERBOSE
    VERBOSE = args.verbose

    verbose(str(args))

    excluded = []
    if args.exclude_file is None:
        excluded = ['.activitypub-troll.cf',
                    '.misskey-forkbomb.cf',
                    '.repl.co']
    else:
        with open(args.exclude_file, 'r') as f:
            excluded.append(f.readline())

    if VERBOSE:
        verbose('--- start of excluded domains list ---')
        for excluded_domain in excluded:
            verbose(excluded_domain)
        verbose('--- end of excluded domains ---')

    global OUTPUT_DIR
    if args.output_dir is None:
        OUTPUT_DIR = os.getcwd()
    else:
        OUTPUT_DIR = os.path.abspath(args.output_dir)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    # reset files
    errors_filepath = get_path(args.output_errors)
    skips_filepath = get_path(args.output_skips)
    visits_filepath = get_path(args.output_visits)

    print('starting threads... (might take a while)')

    qcontrol = deque()
    qerror = deque()
    qdownload = deque()
    qdecode = deque()
    qprocess = deque()
    qskip = deque()
    dtimes = deque()

    t_downloads = list()

    for i in range(0, args.num_threads):
        t_downloads.append(Thread(target=download,
                                    args=[i,
                                          qerror,
                                          qdownload,
                                          qdecode,
                                          qprocess,
                                          dtimes,
                                          args.discard,
                                          args.timeout]))

    t_decode = Thread(target=decode,
                        args=[i,
                              qerror,
                              qdecode,
                              qprocess,
                              visits_filepath])

    t_process = Thread(target=process,
                        args=[0,
                              qerror,
                              qskip,
                              qprocess,
                              qdownload,
                              excluded,
                              args.start_domain])

    t_error_handler = Thread(target=error_handler,
                                args=[0,
                                      qerror,
                                      errors_filepath])

    t_skip_handler = Thread(target=skip_handler,
                            args=[0,
                                  qskip,
                                  skips_filepath])

    t_error_handler.start()
    t_skip_handler.start()
    for t_download in t_downloads:
        t_download.start()
    t_decode.start()
    t_process.start()

    global THREADS_RUN
    global ERROR_HANDLER_TERMINATED, SKIP_HANDLER_TERMINATED
    global DECODE_TERMINATED, PROCESS_TERMINATED
    global num_domains, num_errors, num_skips

    def print_status(start):
        elapsed = time.time() - start
        hours = int(elapsed / 3600)
        minutes = int((elapsed - hours * 3600) / 60)
        seconds = elapsed - minutes * 60 - hours * 3600
        print('d:%06d e:%06d s:%08d qd:%08d ' \
              'e:%02d:%02d:%02d ' \
              'da:%.2f' % (num_domains,
                           num_errors,
                           num_skips,
                           len(qdownload),
                           hours, minutes, seconds,
                           avg_download))
    start = time.time()

    try:
        while True:
            time.sleep(1)
            if (ERROR_HANDLER_TERMINATED or
                SKIP_HANDLER_TERMINATED or
                DECODE_TERMINATED or
                PROCESS_TERMINATED or
                are_all_downloads_terminated()):
                print('something unexpectedly terminated, quitting...')
                break
            if args.demo:
                if (time.time() - start) > 60:
                    break
            print_status(start)
    except KeyboardInterrupt:
        pass

    print('wait for threads to terminate... (might take a while)')
    # terminate threads
    THREADS_RUN = False

    # wait until they are all terminated
    while not (ERROR_HANDLER_TERMINATED and
               SKIP_HANDLER_TERMINATED and
               DOWNLOAD_TERMINATED and
               DECODE_TERMINATED and
               PROCESS_TERMINATED and
               are_all_downloads_terminated()):
        print(get_thread_status(args.num_threads))
        time.sleep(1)

    # write final state
    print(get_thread_status(args.num_threads))
    print_status(start)

    if VERBOSE:
        print('saving download queue to qdownload.dump')
        with open(get_path('qdownload.dump'), 'w') as f:
            try:
                while True:
                    doc = qdownload.popleft()
                    f.write(doc['domain'])
                    f.write('\n')
            except IndexError as e:
                pass
        print('saving download times to download.times')
        with open(get_path('download.times'), 'w') as f:
            try:
                while True:
                    f.write('%.2f' % dtimes.popleft())
                    f.write('\n')
            except IndexError as e:
                pass

    print('masnet.download quit.')

if __name__ == '__main__':
    main()
