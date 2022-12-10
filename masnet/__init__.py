# pylint: disable=missing-module-docstring
import gzip
import os
import re
from struct import pack, unpack

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

excluded_patterns = []

def load_exclusion(exclude_file):
    global excluded_patterns
    def load_exclusion_file(f):
        for line in f:
            line = line.strip()
            if line.startswith('#'):
                continue
            if len(line) == 0:
                continue
            verbose(line)
            excluded_patterns.append(re.compile(line))
    verbose('--- start of exclusion patterns ---')
    if exclude_file is None:
        with pkg_resources.path('masnet',
                                'default_exclusion_patterns') as ipath:
            verbose('loading internal exclusion list from: %s' % ipath)
            with open(ipath, 'r') as f:
                load_exclusion_file(f)
    else:
        verbose('loading external exclusion list from: %s' % exclude_file)
        with open(exclude_file, 'r') as f:
            load_exclusion_file(f)
    verbose('--- end of exclusion patterns ---')

def is_excluded(domain):
    for pattern in excluded_patterns:
        if pattern.search(domain, re.IGNORECASE) is not None:
            debug('%s excluded due to: %s' % (domain, pattern))
            return True
    return False

def get_excluded_patterns():
    return excluded_patterns

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


def write_graph(nodes, edges, file_path):
    with open(file_path, 'wb') as f:
        f.write(pack('!I', len(nodes)))
        for domain, doc in nodes.items():
            _id = doc['id']
            domain_bytes = domain.encode('utf-8')
            f.write(pack('!II', _id, len(domain_bytes)))
            f.write(domain_bytes)
        f.write(pack('!I', len(edges)))
        for src, dst in edges:
            f.write(pack('!II', src, dst))


# returns nodes list of (id -> str), edges list of (src id, dst id)
def read_graph(file_path):
    nodes = {}
    edges = list()
    with open(file_path, 'rb') as f:
        data = f.read()
        off = 0
        (len_nodes,) = unpack('!I', data[off:off+4])
        off += 4
        for _ in range(0, len_nodes):
            (_id, len_domain) = unpack('!II', data[off:off+8])
            off += 8
            domain = data[off:off+len_domain].decode('utf-8')
            off += len_domain
            nodes[_id] = domain
        (len_edges,) = unpack('!I', data[off:off+4])
        off += 4
        for _ in range(0, len_edges):
            (src, dst) = unpack('!II', data[off:off+8])
            off += 8
            edges.append((src, dst))
    return nodes, edges
