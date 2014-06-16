#! /usr/local/bin/python3
# coding: utf-8

import sys
import logging
import yaml
import collections
import os

def represent_odict(dumper, instance):
     return dumper.represent_mapping("tag:yaml.org,2002:map", instance.items())

def construct_odict(loader, node):
    return collections.OrderedDict(loader.construct_pairs(node))

yaml.add_representer(collections.OrderedDict, represent_odict)
yaml.add_constructor("tag:yaml.org,2002:map", construct_odict)

class EventType:
    MSG       = "MSG"
    UPD       = "UPD"

def parseEvent(event):
    if event in { 0, "τ" }:
        return None
    e, _, remain = event.partition(".")
    if e in { 'msg_' }:
        f, _, remain = remain.partition(".")
        t, _, m = remain.partition(".")
        a = None
        if m.find("return_") > -1:
            _, _, a = m.partition(".")
            y = "-->"
            m = a
        else:
            _, _, m = m.partition("_")
            m, _, a = m.partition(".")
            y = "->"
            m = '{0}({1})'.format(m, ', '.join(a.split('.')))
        return (EventType.MSG, f, y, t, m)
    elif e in { 'update_' }:
        remain, _, value = remain.partition(".")
        v = remain.split('_')
        if v[0] == 'System':
            return None
        else:
            return (EventType.UPD, v[0], v[2], value)
    else:
        return None

def getResult(cx, event):
    result = []
    accept = {}
    error = set([])
    if 'trace' in cx:
        for t in cx['trace']:
            result.append(parseEvent(event[int(str(t).replace(',', ''))]))
    if 'error_event' in cx:
        t = cx['error_event']
        e = parseEvent(event[int(str(t).replace(',', ''))])
        if e is not None and e[0] == EventType.MSG:
            error.add((e[1], e[2].replace('>', '[#red]>'), e[3], '<color red>{0}</color>'.format(e[4])))
    if 'child_behaviours' in cx:
        for c in cx['child_behaviours']:
            ret, acc, err = getResult(c, event)
            for i, r in enumerate(ret):
                if ret[i] is not None:
                    result[i] = ret[i]
            for c in acc:
                if c not in accept:
                    accept[c] = set([])
                accept[c] = accept[c].union(acc[c])
            error = error.union(err)
    return result, accept, error

def translate(cx, style, sn):
    event = cx['event_map']
    c = cx['results'][0]['counterexamples'][0]['implementation_behaviour']
    ret, acc, err = getResult(c, event)
    result = []
    result.append('@startuml svg/{0}.svg'.format(sn))
    result.append('title {0}'.format(sn))
    for name in style['Object']:
        result.append('{0} {1}'.format(style['Object'][name], name))
    result.append('')
    for r in [ _r for _r in ret if _r is not None ]:
        if r[0] == EventType.MSG:
            result.append('{0} {1} {2} : {3}'.format(r[1], r[2], r[3], r[4]))
            if r[2] == '-->':
                result.append('deactivate {0}'.format(r[1]))
            else:
                result.append('activate {0}'.format(r[3]))
        elif r[0] == EventType.UPD:
            result.append('note over {0} : {1} = {2}'.format(r[1], r[2], r[3]))
    if err:
        result.append('group neg\n')
        result.append('else\n'.join(['    {0} {1} {2} : {3}\n'.format(*a) for a in err]))
        result.append('end')
    result.append('@enduml')
    return result

if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)-8s: %(message)s', level=logging.WARNING)
    if len(sys.argv) < 4:
        logging.error('Usage: %s inCounterExampleFile styleFile outSdFile' % sys.argv[0])
        quit()
    with open(sys.argv[1], "r") as c, open(sys.argv[2], "r") as s, open(sys.argv[3], "w") as o:
        o.writelines('\n'.join(translate(yaml.load(c), yaml.load(s), os.path.splitext(os.path.basename(sys.argv[3]))[0])))

