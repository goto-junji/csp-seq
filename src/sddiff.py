#! /usr/local/bin/python3
# coding: utf-8

import sys
import difflib
import logging

if __name__ == "__main__":
    if len(sys.argv) < 5:
        logging.error('Usage: %s inSd1File inSd2File outSd1File outSd2File' % sys.argv[0])
        quit()
    with open(sys.argv[1], "r") as inSd1, open(sys.argv[2], "r") as inSd2, open(sys.argv[3], "w") as outSd1, open(sys.argv[4], "w") as outSd2:
        d = difflib.Differ()
        diff = d.compare(inSd1.readlines(), inSd2.readlines())
        for line in diff:
            m = line[0:2]
            l = line[2:]
            if m == '  ':
                outSd1.write(l.strip() + '\n')
                outSd2.write(l.strip() + '\n')
            elif m in { '- ', '+ ' }:
                t = l.split(' ')
                if len(t) > 3 and t[3] == ':':
                    color = 'Blue'
                    v = ' '.join(t[4:]).strip()
                    v = '<color {0}>{1}</color>'.format(color, v) if v and '<color' not in v else v
                    y = t[1].replace('>', '[#{0}]>'.format(color)) if '#' not in t[1] else t[1]
                    l = '{0} {1} {2} : {3}\n'.format(t[0], y, t[2], v)
                if t[0] in { 'note' }:
                    (outSd1 if m != '- ' else outSd2).write('||34||\n')
                elif (len(t) > 3 and t[1] in {'->', '-->'}):
                    if t[4] != '\n':
                        (outSd1 if m != '- ' else outSd2).write('||30||\n')
                    else:
                        (outSd1 if m != '- ' else outSd2).write('||13||\n')
                (outSd1 if m == '- ' else outSd2).write(l.strip() + '\n')
