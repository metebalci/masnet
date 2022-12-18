# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name
# pylint: disable=global-statement
# pylint: disable=bare-except,broad-except
import argparse
import time
import matplotlib.pyplot as plt
import networkit as nk
import networkit.vizbridges as nkvz
import numpy
from tabulate import tabulate, SEPARATING_LINE
from masnet import get_version, set_verbose, set_debug, debug, set_working_dir
from masnet import load_labels, get_path, pltpause

# pylint: disable=too-many-statements
# pylint: disable=too-many-locals
def main():
    print('masnet v%s' % get_version())
    parser = argparse.ArgumentParser(prog='masnet.analyze',
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

    parser.add_argument('--directed',
                        help='use directed graph (default: use undirected)',
                        action='store_true',
                        required=False,
                        default=False)

    parser.add_argument('--card',
                        help='shows the network card',
                        metavar='CARDS_FILE',
                        nargs='?',
                        const='',
                        required=False,
                        default=None)

    parser.add_argument('--strongly-connected-components',
                        help='(experimental)',
                        action='store_true',
                        default=None,
                        required=False)

    parser.add_argument('--local-clustering-coefficients',
                        help='(experimental)',
                        action='store_true',
                        default=None,
                        required=False)

    parser.add_argument('--cut-clusters',
                        help='(experimental)',
                        action='store_true',
                        default=None,
                        required=False)

    parser.add_argument('--core-decomposition',
                        help='(experimental)',
                        action='store_true',
                        default=None,
                        required=False)

    parser.add_argument('--detect-communities',
                        help='(experimental)',
                        action='store_true',
                        default=None,
                        required=False)

    parser.add_argument('--prune',
                        help='(experimental)',
                        choices=['out-degree'],
                        default=None,
                        required=False)

    parser.add_argument('--prune-cutoff',
                        help='(experimental)',
                        type=int,
                        default=0,
                        required=False)

    parser.add_argument('--prune-out',
                        help='(experimental)',
                        default='mastodon.partition.graph',
                        required=False)

    parser.add_argument('--degree-centrality',
                        help='(experimental)',
                        action='store_true',
                        required=False,
                        default=False)

    args = parser.parse_args()
    set_debug(args.debug)
    set_verbose(args.verbose)
    debug(str(args))
    set_working_dir(args.dir)

    id2label = load_labels(get_path('mastodon.labels'))
    print('node labels loaded.')
    start = time.time()
    g = None
    if args.directed:
        print('reading directed graph into networkit...')
        g = nk.readGraph(get_path('mastodon.networkit.directed'),
                         nk.graphio.Format.NetworkitBinary)
        if not g.isDirected():
            print('mastodon.networkit.directed is undirected ?!')
            sys.exit(-1)
    else:
        print('reading undirected graph into networkit...')
        g = nk.readGraph(get_path('mastodon.networkit.undirected'),
                        nk.graphio.Format.NetworkitBinary)
        if g.isDirected():
            print('mastodon.networkit.undirected is directed ?!')
            sys.exit(-1)
    print('graph read in %.1f seconds.' % (time.time() - start))

    if args.card is not None:

        print('generating the network card...')

        N = g.numberOfNodes()
        L = g.numberOfEdges()

        k_avg = 0
        k_min = N-1
        k_max = 0
        for node_id in g.iterNodes():
            k = g.degree(node_id)
            if k < k_min:
                k_min = k
            if k > k_max:
                k_max = k
            k_avg = k_avg + k
        k_avg = k_avg / N

        component_sizes = None
        strongly_connected = False
        weakly_connected = False

        if g.isDirected():
            components_run = nk.components.StronglyConnectedComponents(g)
            components_run.run()
            component_sizes = components_run.getComponentSizes()
            if len(component_sizes) == 1:
                strongly_connected = True
            else:
                components_run = nk.components.WeaklyConnectedComponents(g)
                components_run.run()
                component_sizes = components_run.getComponentSizes()
                if len(component_sizes) == 1:
                    weakly_connected = True
        else:
            components_run = nk.components.ConnectedComponents(g)
            components_run.run()
            component_sizes = components_run.getComponentSizes()

        card = []
        card.append(['Name', 'Mastodon peers network'])
        card.append(['Kind', '%s, %s' % ('directed' if g.isDirected() else 'undirected',
                                         'weighted' if g.isWeighted() else 'unweighted')])
        card.append(['Nodes are', 'Mastodon instances'])
        card.append(['Links are', 'Peer relationship'])
        card.append(SEPARATING_LINE)
        card.append(['Number of nodes', N])
        card.append(['Number of links', L])
        card.append(['Degree*', '%.3f [%d, %d]' % (k_avg,
                                                   k_min,
                                                   k_max)])

        if g.isDirected():
            card.append(['Clustering', 'n/a'])
        else:
            lcc_run = nk.centrality.LocalClusteringCoefficient(g,
                                                               turbo=True)
            lcc_run.run()
            avg_clustering = sum(lcc_run.scores()) / N
            card.append(['Clustering', '%.3f' % avg_clustering])

        if len(component_sizes) == 1:

            if g.isDirected():
                if strongly_connected:
                    card.append(['Connected', 'Strongly connected'])
                    apsp = nk.distance.APSP(g)
                    apsp.run()
                    diameter = 0
                    for u in g.numberOfNodes():
                        for v in g.numberOfNodes():
                            d = apsp.getDistance(u, v)
                            if d > diameter:
                                max_distance = diameter
                    card.append(['Diameter', '%d' % diameter])
                elif weakly_connected:
                    card.append(['Connected', 'Weakly connected'])
                    card.append(['Diameter', 'n/a'])
                else:
                    raise Exception('This should be unreachable !!!')
            else:
                card.append(['Connected', 'Yes'])
                diameter_run = nk.distance.Diameter(g,
                                                    algo=nk.distance.DiameterAlgo.Exact)
                diameter_run.run()
                diameter = diameter_run.getDiameter()[0]
                card.append(['Diameter', '%d' % diameter])

        else:

            if g.isDirected():
                card.append(['Connected', 'Disconnected'])
                card.append(['Diameter', 'n/a'])
            else:
                comp_sizes = component_sizes.values()
                Nmaxcomp = max(comp_sizes)
                card.append(['Connected',
                             '%d components [%.1f%% in largest]' % (len(component_sizes),
                                                                    100*Nmaxcomp/N)])
                Nmincomp = min(comp_sizes)
                Navgcomp = sum(comp_sizes) / len(comp_sizes)
                card.append(['Component size*', '%.1f [%d, %d]' % (Navgcomp,
                                                                   Nmincomp,
                                                                   Nmaxcomp)])
                card.append(['Diameter', 'n/a'])

                largest_component = components_run.extractLargestConnectedComponent(g,
                                                                                    False)
                diameter_run = nk.distance.Diameter(largest_component,
                                                    algo=nk.distance.DiameterAlgo.Exact)
                diameter_run.run()
                diameter = diameter_run.getDiameter()[0]
                card.append(['Largest component\'s diameter', '%d' % diameter])

        card.append(SEPARATING_LINE)
        card.append(['Data generating process', 'masnet.download, masnet.generate'])

        print(tabulate(card))
        print('*: avg [min, max]')
        if g.isDirected():
            print('Weakly connected components are shown.')

        if len(args.card) > 0:
            with open(get_path(args.card), 'w') as f:
                f.write(tabulate(card))
                f.write('\n')
                f.write('*: avg [min, max]\n')
                if g.isDirected():
                    f.write('Weakly connected components are shown.\n')

    elif args.strongly_connected_components:

        scc = nk.components.StronglyConnectedComponents(g)
        scc.run()
        print('# of strongly connected components: %d' % scc.numberOfComponents())
        print('component sizes: %s' % scc.getComponentSizes().values())

    elif args.local_clustering_coefficients:

        lcc = nk.centrality.LocalClusteringCoefficient(ug,
                                                       turbo=True)
        lcc.run()
        ranks = lcc.ranking()[:100]
        for rank in ranks:
            domain = id2label[rank[0]]
            local_clustering_coefficient = rank[1]
            print('%s %0.3f' % (domain, local_clustering_coefficient))

    elif args.cut_clusters:

        for alpha in [0, 0.25, 0.5, 0.75, 1]:
            cc = nk.community.CutClustering(g, alpha)
            cc.run()

    elif args.detect_communities:

        #cs = nk.community.detectCommunities(ug)
        cs = nk.community.detectCommunities(ug,
                                            algo=nk.community.PLM(ug, True))
        print(cs.subsetSizes())

    elif args.degree_centrality:

        dc = sorted(nk.centrality.DegreeCentrality(g,
                                                   normalized=False,
                                                   outDeg=True).run().scores(),
                    reverse=True)

        degrees, number_of_nodes = numpy.unique(dc, return_counts=True)

        plt.xscale('log')
        plt.xlabel('degree')
        plt.yscale('log')
        plt.ylabel('number of nodes')
        plt.title('degree distribution')
        plt.plot(degrees, number_of_nodes)
        plt.show(block=False)
        pltpause()

    elif args.core_decomposition:

        cd = nk.centrality.CoreDecomposition(ug)
        cd.run()
        scores = cd.scores()
        max_score = max(scores)
        print('max score: %s' % max_score)
        snodes = list()
        for node_id in g.iterNodes():
            if scores[node_id] == max_score:
                snodes.append(node_id)

        sg = nk.graphtools.subgraphFromNodes(ug, snodes)
        print(sg.numberOfNodes())
        print(sg.numberOfEdges())
        nk.writeGraph(sg,
                      'core-decomposition.gml',
                      nk.graphio.Format.GML)

    elif args.prune is not None:
        degrees = list()
        for node_id in g.iterNodes():
            kin = g.degreeIn(node_id)
            kout = g.degreeOut(node_id)
            degrees.append((kin, kout, node_id))
        degrees = sorted(degrees, key=lambda x: x[1], reverse=True)
        kept_nodes = list(map(lambda x: x[2], degrees[0:100]))
        pruned_graph = nk.graphtools.subgraphFromNodes(g, kept_nodes)
        nk.writeGraph(pruned_graph,
                      'mastodon.partition.gml',
                      nk.graphio.Format.GML)

    else:
        parser.print_help()

if __name__ == '__main__':
    main()
