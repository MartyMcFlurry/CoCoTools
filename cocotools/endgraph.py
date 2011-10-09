from networkx import DiGraph
import numpy as np


class EndGraphError(Exception):
    pass


class EndGraph(DiGraph):

    def add_edge(self, source, target, new_attr, method):
        if method == 'dan':
            add_edge = DiGraph.add_edge.im_func
            if not self.has_edge(source, target):
                add_edge(self, source, target, new_attr)
            else:
                for key, value in new_attr.iteritems():
                    try:
                        self[source][target][key] += value
                    except KeyError:
                        self[source][target][key] = value
        elif method == 'ort':
            _assert_valid_attr(new_attr)
            add_edge = DiGraph.add_edge.im_func
            if not self.has_edge(source, target):
                add_edge(self, source, target, new_attr)
            else:
                old_attr = self[source][target]
                for ec in ('EC_Source', 'EC_Target'):
                    for bmap in new_attr[ec]:
                        try:
                            old_attr[ec][bmap] += new_attr[ec][bmap]
                        except KeyError:
                            old_attr[ec][bmap] = new_attr[ec][bmap]
        else:
            raise EndGraphError('Invalid method supplied.')

    def add_edges_from(self, ebunch, method):
        for (source, target, new_attr) in ebunch:
            self.add_edge(source, target, new_attr, method)

    def add_translated_edges(self, mapp, conn, desired_bmap, method='ort'):
        if method == 'dan':
            self.dan_translate(mapp, conn, desired_bmap)
        elif method == 'ort':
            self.ort_translate(mapp, conn, desired_bmap)

    def dan_translate(self, mapp, conn, desired_bmap):
        num_edges = conn.number_of_edges()
        conn_edges = conn.edges()
        while conn_edges:
            s, t = conn_edges.pop()
            s_map, t_map = s.split('-')[0], t.split('-')[0]
            ebunch = []
            for new_s, new_t in mapp._translate_edge(s, t, desired_bmap):
                old_edges = mapp._translate_edge(new_s, new_t, s_map, t_map)
                incomplete = False
                for old_s, old_t in old_edges:
                    try:
                        degree = conn[old_s][old_t]['Degree']
                    except KeyError:
                        incomplete = True
                        continue
                    if degree != '0':
                        attr = {'ebunches_for': [(s_map, t_map)]}
                        break
                else:
                    if incomplete:
                        attr = {'ebunches_incomplete': [(s_map, t_map)]}
                    else:
                        attr = {'ebunches_against': [(s_map, t_map)]}
                for processed_edge in old_edges:
                    try:
                        conn_edges.remove(processed_edge)
                    except ValueError:
                        pass
                ebunch.append((new_s, new_t, attr))
            self.add_edges_from(ebunch, 'dan')

    def ort_translate(self, mapp, conn, desired_bmap):
        for s, t in conn.edges_iter():
            s_map = s.split('-')[0]
            # new_sources will have regions from desired_bmap
            # coextensive with source as keys and (ec, pdc) tuples as
            # values.
            new_sources = {}
            for new_s in mapp._translate_node(s, desired_bmap):
                single_steps, multi_steps = mapp._separate_rcs(new_s, s_map)
                new_sources[new_s] = []
                for old_s, rc in single_steps:
                    new_sources[new_s].append(conn._single_ec_step(old_s, rc,
                                                                   t,
                                                                   'Source'))
                if multi_steps:
                    ec = 'B'
                    pdc_sum = 0.0
                    for old_s, rc in multi_steps:
                        ec, pdc_sum = conn._multi_ec_step(old_s, rc, t,
                                                          'Source', ec,
                                                          pdc_sum)
                    avg_pdc = pdc_sum / (2 * len(multi_steps))
                    new_sources[new_s].append((ec, avg_pdc))
            t_map = t.split('-')[0]
            new_targets = {}
            for new_t in mapp._translate_node(t, desired_bmap):
                single_steps, multi_steps = mapp._separate_rcs(new_t, t_map)
                new_targets[new_t] = []
                for old_t, rc in single_steps:
                    new_targets[new_t].append(conn._single_ec_step(s, rc,
                                                                   old_t,
                                                                   'Target'))
                if multi_steps:
                    ec = 'B'
                    pdc_sum = 0.0
                    for old_t, rc in multi_steps:
                        ec, pdc_sum = conn._multi_ec_step(s, rc, old_t,
                                                          'Target', ec,
                                                          pdc_sum)
                    avg_pdc = pdc_sum / (2 * len(multi_steps))
                    new_targets[new_t].append((ec, avg_pdc))
            for new_s, s_values in new_sources.iteritems():
                for new_t, t_values in new_targets.iteritems():
                    for s_value in s_values:
                        for t_value in t_values:
                            self.add_edge(new_s, new_t,
                                          {'EC_Source': {s_map: [s_value[0]]},
                                           'EC_Target': {t_map: [t_value[0]]}},
                                          'ort')

    def add_controversy_scores(self):
        for source, target in self.edges_iter():
            edge_dict = self[source][target]
            for group in ('for', 'against'):
                try:
                    exec '%s_ = len(edge_dict["ebunches_%s"])' % (group, group)
                except KeyError:
                    exec '%s_ = 0' % group
            try:
                edge_dict['score'] = (for_ - against_) / float(for_ + against_)
            except ZeroDivisionError:
                edge_dict['score'] = 0


def _assert_valid_attr(attr):
    for key in ('EC_Source', 'EC_Target'):
        values = attr[key].values()
        for value_list in values:
            for value in value_list:
                assert value in ('Up', 'Ux', 'N', 'Nc', 'Np', 'Nx', 'C', 'P',
                                 'X')
