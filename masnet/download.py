# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name
# pylint: disable=global-statement
# pylint: disable=bare-except,broad-except
import argparse
from concurrent.futures import ThreadPoolExecutor
import http
import gzip
import json
import os
import socket
import sys
import time
from threading import Lock
import traceback
from urllib.error import URLError, HTTPError
import urllib.request


LOCK = Lock()
RUN = True
VERBOSE = False
OUTPUT_DIR = None


def verbose(s):
    if VERBOSE:
        print(s, flush=True)


def get_path(fname):
    return os.path.join(OUTPUT_DIR, fname)


# pylint: disable=too-many-return-statements, too-many-branches
def download_and_cache(json_url,
                       file_path,
                       discard,
                       timeout=-1):
    try:
        res = None

        # the reason of download flag is to redownload if the file cannot be
        # read or decoded for some reason
        download = True

        # even if file exists, it has to be read to find peers, thus graph
        if not discard and os.path.exists(file_path):
            try:
                with gzip.open(file_path, 'rb') as f:
                    res = json.load(f)
                    download = False
            except:
                download = True

        if download:
            if timeout > 0:
                with urllib.request.urlopen(json_url, timeout=timeout) as req:
                    res = json.load(req)
            else:
                with urllib.request.urlopen(json_url) as req:
                    res = json.load(req)
            with gzip.open(file_path, 'wb') as f:
                f.write(json.dumps(res).encode('utf-8'))

        return res, None

    # return normally from expected errors
    # re-raise only KeyboardInterrupt which is handled in caller
    #           or  unexpected erros

    except KeyboardInterrupt:
        raise
    except HTTPError as e:
        return None, '%s %d' % (e.__class__.__name__, e.code)
    except URLError as e:
        return None, '%s %s' % (e.__class__.__name__, e.reason)
    except json.decoder.JSONDecodeError as e:
        return None, e.__class__.__name__
    except http.client.RemoteDisconnected as e:
        return None, e.__class__.__name__
    except socket.timeout as e:
        return None, e.__class__.__name__
    except ConnectionError as e:
        return None, e.__class__.__name__
    except UnicodeDecodeError as e:
        return None, e.__class__.__name__
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return None, e.__class__.__name__


# pylint: disable=too-many-arguments,too-many-locals
def process(domain,
            skipsfp,
            errorsfp,
            visitsfp,
            discard,
            domains,
            visits_pending,
            visits_done,
            skips,
            excluded,
            errors,
            timeout=-1):

    global RUN
    if not RUN:
        return

    # no idea why some domains are actually URL
    peers_file = '%s.peers.json.gz' % (domain.replace('/', '_'))
    peers_file_path = get_path(peers_file)
    peers_url = 'https://%s/api/v1/instance/peers' % domain
    peers, err = download_and_cache(peers_url,
                                    peers_file_path,
                                    discard=discard,
                                    timeout=timeout)

    # lock needed because skips, domains, visits are shared
    with LOCK:
        if err is not None:
            print('ERROR: %s %s' % (domain, err), file=sys.stderr)
            errors.append((domain, err))
            errorsfp.write(domain)
            errorsfp.write(' ')
            errorsfp.write(err)
            errorsfp.write('\n')
        elif peers is not None:
            # skip excluded peers
            peers_set = set()
            for peer in peers:
                peer = peer.strip()
                if len(peer) > 0:
                    for excluded_domain in excluded:
                        if peer.endswith(excluded_domain):
                            skips.add(peer)
                            skipsfp.write(peer)
                            skipsfp.write('\n')
                        else:
                            peers_set.add(peer)
            # insert items to domains
            # items that exists in peers but not in pending visits
            # so effectively add domains that are not seen yet
            # no need to filter skip list here, it is done above
            domains.update(peers_set.difference(visits_pending))
        visits_done.add(domain)
        visitsfp.write(domain)
        visitsfp.write('\n')

# pylint: disable=too-many-statements
def main():
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
                        help='use specified directory for files (default: current directory)',
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

    if args.timeout > 0:
        socket.setdefaulttimeout(args.timeout)

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

    # reset files
    errorsfp = open(get_path(args.output_errors), 'w')
    skipsfp = open(get_path(args.output_skips), 'w')
    visitsfp = open(get_path(args.output_visits), 'w')

    # domains to visit, populated by peers
    domains = set()
    # domains visited (done) and scheduled to be visited (pending)
    visits_pending = set()
    # domains visited (done)
    visits_done = set()
    # domains skipped due to exclusion
    skips = set()
    # errors key: err, value: number of this err
    errors = list()
    # start visiting from start domain
    domains.add(args.start_domain)
    executor = ThreadPoolExecutor(max_workers=args.num_threads)
    futures = list()
    every_5second = 0
    start = time.time()
    def print_status():
        elapsed = int(time.time() - start)
        seconds = elapsed % 60
        minutes = (elapsed-seconds) / 60
        progress = 0 if (len(visits_done) == 0 or
                         len(visits_pending) == 0) else (100*
                                                         len(visits_done)/
                                                         len(visits_pending))
        print('vp:%06d vd:%06d e:%06d ' \
              'd:%06d ' \
              's:%08d ' \
              'p:%.1f%% ' \
              't:%04d:%02d' % (len(visits_pending),
                               len(visits_done),
                               len(errors),
                               len(domains),
                               len(skips),
                               progress,
                               minutes, seconds))
    global RUN
    try:
        while RUN:
            try:
                # do this block every 5 seconds
                if (time.time() - every_5second) > 5:
                    print_status()
                    visitsfp.flush()
                    skipsfp.flush()
                    errorsfp.flush()

                    # number of running/pending futures
                    npf = len(list(filter(lambda x: x.running(), futures)))

                    # no pending futures and no domains to visit
                    if (npf == 0) and (len(domains) == 0):
                        RUN = False

                    every_5second = time.time()

                if len(domains) > 0:
                    domain = domains.pop()
                    visits_pending.add(domain)
                    future = executor.submit(process,
                                             domain=domain,
                                             errorsfp=errorsfp,
                                             skipsfp=skipsfp,
                                             visitsfp=visitsfp,
                                             discard=args.discard,
                                             domains=domains,
                                             visits_pending=visits_pending,
                                             visits_done=visits_done,
                                             skips=skips,
                                             excluded=excluded,
                                             errors=errors,
                                             timeout=args.timeout)
                    futures.append(future)

                # terminate after 60 seconds in demo run
                if args.demo and (time.time() - start) > 60:
                    RUN = False

            except KeyboardInterrupt:
                RUN = False

            except:
                traceback.print_exc()
                RUN = False

    finally:
        try:
            errorsfp.close()
        except:
            pass
        try:
            skipsfp.close()
        except:
            pass
        try:
            visitsfp.close()
        except:
            pass

    print_status()

    print('waiting for scheduled tasks to terminate... (this may take a while)')
    for future in futures:
        future.cancel()
    executor.shutdown(wait=False)

    if VERBOSE:
        first = None
        while True:
            cnt = 0
            for future in futures:
                if future.running():
                    cnt = cnt + 1
            if first is None:
                first = cnt
            if cnt == 0:
                break
            print('%d%%' % (100*cnt/first), end=' ', flush=True)
            time.sleep(1)
        print()

    print('bye.')

if __name__ == '__main__':
    main()
