# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name
# pylint: disable=global-statement
# pylint: disable=bare-except,broad-except
import argparse
import time
import networkit as nk
from masnet import get_version, set_verbose, set_debug, debug, set_working_dir
from masnet import load_labels, get_path

# pylint: disable=too-many-statements
# pylint: disable=too-many-locals
def main():
    print('masnet v%s' % get_version())
    parser = argparse.ArgumentParser(prog='masnet.generate',
                                     description='',
                                     epilog='')

    parser.add_argument('-d', '--dir',
                        help='use specified directory for files ' \
                             '(default: current directory)',
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

    parser.add_argument('--degrees',
                        help='saves kin, kout and label to mastodon.degrees',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('--degree-centrality-ranks',
                        help='',
                        nargs='?',
                        type=int,
                        const=10,
                        required=False)

    parser.add_argument('--detect-communities',
                        help='',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('--degree-centrality',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('--greedy-modularity',
                        action='store_true',
                        required=False,
                        default=False)

    args = parser.parse_args()
    set_debug(args.debug)
    set_verbose(args.verbose)
    debug(str(args))
    set_working_dir(args.dir)

    id2label = load_labels(get_path('mastodon.labels'))
    print('vertex labels loaded.')
    print('reading graph into networkit...')
    start = time.time()
    g = nk.readGraph(get_path('mastodon.graph'),
                     nk.graphio.Format.NetworkitBinary)
    print('graph read in %.1f seconds.' % (time.time() - start))

    if args.degrees:

        print('calculating degrees...')
        l = list()
        for vertex_id in range(0, g.numberOfNodes()):
            vertex_label = id2label[vertex_id]
            kin = g.degreeIn(vertex_id)
            kout = g.degreeOut(vertex_id)
            l.append((kin, kout, vertex_label))

        print('saving degrees...')
        with open(get_path('mastodon.degrees'), 'w') as degf:
            for (kin, kout, vertex_label) in sorted(l,
                                                    key=lambda x: x[0]+x[1],
                                                    reverse=True):
                degf.write('%d %d %s\n' % (kin, kout, vertex_label))

        print('done.')

    if args.degree_centrality_ranks is not None:

        print('calculating degree centrality...')
        deg = nk.centrality.DegreeCentrality(g,
                                             normalized=True,
                                             outDeg=True)
        deg.run()
        ranks = deg.ranking()[:args.degree_centrality_ranks]
        print('done.')
        for rank in ranks:
            domain = id2label[rank[0]]
            centrality = rank[1]
            print('%s %0.3f' % (domain, centrality))

    print('bye.')

if __name__ == '__main__':
    main()
