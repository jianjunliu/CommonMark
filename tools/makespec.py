#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
from subprocess import *
from string import Template

def out(str):
    sys.stdout.buffer.write(str.encode('utf-8'))

def err(str):
    sys.stderr.buffer.write(str.encode('utf-8'))

if len(sys.argv) == 2:
    specformat = sys.argv[1]
    if not (specformat in ["html", "markdown"]):
        err("Format must be html or markdown\n")
        exit(1)
else:
    err("Usage:  makespec.py [html|markdown]\n")
    exit(1)

def toIdentifier(s):
   return re.sub(r'\s+', '-', re.sub(r'\W+', ' ', s.strip().lower()))

def parseYaml(yaml):
    metadata = {}
    def parseField(match):
        key = match.group(1)
        val = match.group(2).strip()
        if re.match(r'^\'', val):
            val = val[1:len(val) - 1]
        metadata[key] = val
    fieldre = re.compile('^(\w+):(.*)$', re.MULTILINE)
    re.sub(fieldre, parseField, yaml)
    return metadata

def pipe_through_prog(prog, text):
    result = check_output(prog.split(), input=text.encode('utf-8'))
    return result.decode('utf-8')

def replaceAnchor(match):
    refs.append("[{0}]: #{1}".format(match.group(1), match.group(2)))
    if specformat == "html":
        return '<a id="{1}" href="#{1}" class="definition">{0}</a>'.format(match.group(1), match.group(2))
    else:
        return match.group(0)

stage = 0
example = 0
section = ""
sections = []
mdlines = []
refs = []
lastnum = []
finishedMeta = False
yamllines = []

with open('spec.txt', 'r', encoding='utf-8') as spec:
    for ln in spec:
        if not finishedMeta:
            yamllines.append(ln)
            if re.match(r'^\.\.\.$', ln):
                finishedMeta = True
        elif re.match(r'^\.$', ln):
            if stage == 0:
                example += 1
                mdlines.append("\n<div class=\"example\" id=\"example-{0}\" data-section=\"{1}\">\n".format(example, section))
                mdlines.append("<div class=\"examplenum\"><a href=\"#example-{0}\">Example {0}</a>".format(example))
                if specformat == "html":
                    mdlines.append("&nbsp;&nbsp;<a class=\"dingus\" title=\"open in interactive dingus\">(interact)</a>")
                mdlines.append("</div>\n<div class=\"column\">\n\n")
                mdlines.append("````````````````````````````````````````````````````````` markdown\n")
                stage = 1
            elif stage == 1:
                mdlines.append("`````````````````````````````````````````````````````````\n\n")
                mdlines.append("\n</div>\n\n<div class=\"column\">\n\n")
                mdlines.append("````````````````````````````````````````````````````````` html\n")
                stage = 2
            elif stage == 2:
                mdlines.append("`````````````````````````````````````````````````````````\n\n")
                mdlines.append("</div>\n</div>\n")
                stage = 0
            else:
                sys.stderr.out("Encountered unknown stage {0}\n".format(stage))
                sys.exit(1)
        else:
            if stage == 0:
                match = re.match(r'^(#{1,6}) *(.*)', ln)
                if match:
                    section = match.group(2)
                    lastlevel = len(lastnum)
                    level = len(match.group(1))
                    if re.search(r'{-}$', section):
                        section = re.sub(r' *{-} *$', '', section)
                        if specformat == 'html':
                            ln = re.sub(r' *{-} *$', '', ln)
                        number = ''
                    else:
                        if lastlevel == level:
                            lastnum[level - 1] = lastnum[level - 1] + 1
                        elif lastlevel < level:
                            while len(lastnum) < level:
                                lastnum.append(1)
                        else: # lastlevel > level
                            lastnum = lastnum[0:level]
                            lastnum[level - 1] = lastnum[level - 1] + 1
                        number = '.'.join([str(x) for x in lastnum])
                    ident = toIdentifier(section)
                    ln = re.sub(r' ', ' <span class="number">' + number + '</span> ', ln, count=1)
                    sections.append(dict(level=level,
                                         contents=section,
                                         ident=ident,
                                         number=number))
                    refs.append("[{0}]: #{1}".format(section, ident))
                    ln = re.sub(r'# +', '# <a id="{0}"></a>'.format(ident),
                                ln, count=1)
                else:
                    ln = re.sub(r'\[([^]]*)\]\(@([^)]*)\)', replaceAnchor, ln)
            else:
                ln = re.sub(r' ', '␣', ln)
            mdlines.append(ln)

mdtext = ''.join(mdlines) + '\n\n' + '\n'.join(refs) + '\n'
yaml = ''.join(yamllines)
metadata = parseYaml(yaml)

if specformat == "markdown":
    out(yaml + '\n\n' + mdtext)
elif specformat == "html":
    with open("tools/template.html", "r", encoding="utf-8") as templatefile:
        template = Template(templatefile.read())
    toclines = []
    for section in sections:
        indent = '    ' * (section['level'] - 1)
        toclines.append(indent + '* [' + section['number'] + ' ' +
                        section['contents'] + '](#' + section['ident'] + ')')
    toc = '<div id="TOC">\n\n' + '\n'.join(toclines) + '\n\n</div>\n\n'
    prog = "cmark --smart"
    result = pipe_through_prog(prog, toc + mdtext)
    if result == '':
        err("Error converting markdown version of spec to HTML.\n")
        exit(1)
    else:
        result = re.sub(r'␣', '<span class="space"> </span>', result)
        result = re.sub(r'<h([1-6])><a id="([^\"]*)"><\/a> ',
                        "<h\\1 id=\"\\2\">", result)
        # put plural s inside links for better visuals:
        result = re.sub(r'<\/a>s', "s</a>", result)
        out(template.substitute(metadata, body=result))

        # check for errors:
        idents = []
        for ident in re.findall(r'id="([^"]*)"', result):
            if ident in idents:
                err("WARNING: duplicate identifier '" + ident + "'\n")
            else:
                idents.append(ident)
        for href in re.findall(r'href="#([^"]*)"', result):
            if not (href in idents):
                err("WARNING: internal link with no anchor '" + href + "'\n")
        reftexts = []
        for ref in refs:
            ref = re.sub('].*',']',ref).upper()
            if ref in reftexts:
                err("WARNING: duplicate reference link '" + ref + "'\n")
            else:
                reftexts.append(ref)


exit(0)
