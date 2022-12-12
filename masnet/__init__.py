# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
import gzip
import os
import re
from struct import pack, unpack
import time
import networkit as nk

try:
    import importlib.resources as pkg_resources
except ImportError:
    import importlib_resources as pkg_resources

__version__ = '0.2'

def get_version():
    return __version__

def get_path(file_name):
    if file_name is None:
        return DIR
    else:
        return os.path.join(DIR, file_name)

def get_peers_file_name(domain):
    return '%s.peers.json' % domain.replace('/', '_')

def get_peers_file_path(domain):
    return get_path(get_peers_file_name(domain))

def get_error_file_name(domain):
    return '%s.error' % domain.replace('/', '_')

def get_error_file_path(domain):
    return get_path(get_error_file_name(domain))

EXCLUDED_PATTERNS = list()

def load_exclusion(exclude_file):
    global EXCLUDED_PATTERNS
    def load_exclusion_file(f):
        for line in f:
            line = line.strip()
            if line.startswith('#'):
                continue
            if len(line) == 0:
                continue
            verbose(line)
            EXCLUDED_PATTERNS.append(re.compile(line))
    verbose('--- start of exclusion patterns ---')
    if exclude_file is None:
        with pkg_resources.path('masnet',
                                'default_exclusion_patterns') as ipath:
            verbose('loading internal exclusion list from: %s' % ipath)
            with open(ipath, 'r') as file:
                load_exclusion_file(file)
    else:
        verbose('loading external exclusion list from: %s' % exclude_file)
        with open(exclude_file, 'r') as file:
            load_exclusion_file(file)
    verbose('--- end of exclusion patterns ---')

def is_excluded(domain):
    for pattern in EXCLUDED_PATTERNS:
        if pattern.search(domain, re.IGNORECASE) is not None:
            debug('%s excluded due to: %s' % (domain, pattern))
            return True
    return False

def get_excluded_patterns():
    return EXCLUDED_PATTERNS

VERBOSE = False
def set_verbose(verbose):
    global VERBOSE
    VERBOSE = verbose

def is_verbose():
    return VERBOSE

def verbose(s):
    if VERBOSE:
        print(s, flush=True)

DEBUG = False
def set_debug(debug):
    global DEBUG
    DEBUG = debug

def is_debug():
    return DEBUG

def debug(s):
    if DEBUG:
        print(s, flush=True)

DIR = None
def set_working_dir(wd):
    global DIR
    if wd is None:
        DIR = os.getcwd()
    else:
        DIR = os.path.abspath(wd)
        os.makedirs(DIR, exist_ok=True)


def percent_progress(x):
    if x == -1:
        percent_progress.last = 0
    elif x == 2:
        print('100%')
    elif (time.time() - percent_progress.last) > 1:
        print('%d%% ' % (x*100), end='', flush=True)
        percent_progress.last = time.time()


def save_graph(adjlists,
               file_path,
               progressfn=None):
    if progressfn:
        progressfn(-1)
    g = nk.Graph(n=len(adjlists),
                 directed=True)
    # pylint: disable=consider-using-enumerate
    # not enumerating to preserve the order 0...n
    for i in range(0, len(adjlists)):
        if progressfn:
            progressfn(i/len(adjlists))
        adjlist = adjlists[i]
        for adj_vertex_id in sorted(adjlist):
            g.addEdge(i, adj_vertex_id)
    # save graph
    nk.writeGraph(g,
                  file_path,
                  nk.Format.NetworkitBinary,
                  chunks=32,
                  NetworkitBinaryWeights=0) # 0=no weight
    if progressfn:
        progressfn(2)


def save_labels(id2labels, file_path):
    with open(get_path(file_path), 'w') as file:
        # pylint: disable=consider-using-enumerate
        # not enumerating to preserve the order 0...n
        for i in range(0, len(id2labels)):
            file.write('%s\n' % id2labels[i])


def load_labels(file_path):
    id2labels = {}
    i = 0
    with open(get_path(file_path), 'r') as file:
        for line in file:
            id2labels[i] = line.strip()
            i = i + 1
    return id2labels
