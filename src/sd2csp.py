#! /usr/local/bin/python3
# coding: utf-8

import sys
import logging
import yaml
import collections

def represent_odict(dumper, instance):
     return dumper.represent_mapping("tag:yaml.org,2002:map", instance.items())

def construct_odict(loader, node):
    return collections.OrderedDict(loader.construct_pairs(node))

yaml.add_representer(collections.OrderedDict, represent_odict)
yaml.add_constructor("tag:yaml.org,2002:map", construct_odict)

class SeqType:
    START       = "START"
    STOP        = "STOP"
    TRANSITION  = "TRANSITION"
    SMSGRECV    = "SMSGRECV"
    SMSGSEND    = "SMSGSEND"
    AMSGRECV    = "AMSGRECV"
    AMSGSEND    = "AMSGSEND"
    RETURN      = "RETURN"
    ALT         = "ALT"
    LOOP        = "LOOP"
    OPT         = "OPT"
    PAR         = "PAR"
    ELSE        = "ELSE"
    END         = "END"
    UPDATE      = "UPDATE"

def getArgs(strArgs):
    args = []
    arg = ""
    nestNum = 0
    for a in [ arg.strip() for arg in strArgs.split(",") if arg.strip() ]:
        arg += ", {0}".format(a) if nestNum != 0 else a
        nestNum += a.count("(") - a.count(")")
        if nestNum == 0:
            args.append(arg)
            arg = ""
    return args

def normalizeDefine(define, specPath, sysPath):
    if 'State' not in define:
        define['State'] = { 'System' : { 'Init' : collections.OrderedDict() } }
    if 'External' not in define:
        define['External'] = []
    if 'Internal' not in define:
        define['Internal'] = []
    for className in define['Class']:
        if className not in define['State']:
            define['State'][className] = { 'Init' : collections.OrderedDict() }
    with open(specPath, "r") as spec, open(sysPath, "r") as sys:
        specLine = spec.readlines()
        sysLine = sys.readlines()
        for line in specLine:
            token, _, remain = line.strip().partition(" ")
            if token.lower() in { "participant", "actor", "boundary", "control", "entity", "database" }:
                clsName, _, remain = remain.strip().partition(" ")
                if clsName not in { 'System' } and clsName not in define['External']:
                    define['External'].append(clsName)
        for line in sysLine:
            token, _, remain = line.strip().partition(" ")
            if token.lower() in { "participant", "actor", "boundary", "control", "entity", "database" }:
                clsName, _, remain = remain.strip().partition(" ")
                if clsName not in define['External'] and clsName not in define['Internal']:
                    define['Internal'].append(clsName)
        for line in specLine + sysLine:
            token, _, remain = line.strip().partition(" ")
            if token.lower() not in { "hnote" }:
                continue
            over, _, remain = remain.strip().partition(" ")
            if over != "over":
                continue
            clsName, _, remain = remain.strip().partition(" ")
            _, _, remain = remain.strip().partition(":")
            sttName, _, remain = remain.strip().partition("(")
            className = clsName.strip()
            stateName = sttName.strip()
            args = getArgs(remain[:-1])
            if stateName not in define['State'][className]:
                define['State'][className].update({ stateName: collections.OrderedDict() })
            for a in args:
                varName, _, typeName = a.partition(':')
                varName = varName.strip()
                typeName = typeName.strip()
                if varName not in define['State'][className][stateName] and typeName:
                    define['State'][className][stateName][varName] = typeName
    return define

def normalizeSpecList(specSeqList, sysSeqList):
    result = []
    for s in specSeqList:
        if s[0] in { 'SMSGRECV', 'AMSGRECV' }:
            calleeClass = s[4]
            calleeMethod = s[5]
            tmp = [ sys[1] for sys in sysSeqList if sys[4] == calleeClass and sys[5] == calleeMethod ]
            if len(set(tmp)) != 1:
                raise Exception()
            result.append((s[0], tmp[0], s[2], s[3], s[4], s[5], s[6], s[7], s[8]))
        else:
            result.append(s)
    return result

def parse(define, path):
    sequenceList = []   # (seqType, className, stateName, seqNo, relatedClassName, methodName, args, condition, nextStateName)
    className = None
    stateName = None
    seqNo = None
    lines = []
    with open(path, "r") as s:
        lines = s.readlines()
    for lineNo, line in enumerate(lines):
        if not line.strip():
            continue
        line = line.rstrip()
        lineNo += 1
        token, _, remain = line.strip().partition(" ")
        if token.lower() in { "participant", "actor", "boundary", "control", "entity", "database" } :
            clsName, _, remain = remain.strip().partition(" ")
            if clsName not in define['Class']:
                logging.debug('{clsName} is not defined. ignored'.format(**vars()))
                logging.debug('    at {path} line.{lineNo} : "{line}"'.format(**vars()))
                continue
        elif token.lower() in { "title" }:
            className, _, remain = remain.strip().partition(" ")
            className = 'System' if className == 'Spec' else className
            stateName = "Init"
            seqNo = 0
            sequenceList.append((SeqType.START, className, stateName, seqNo, None, None, [], None, None))
            seqNo += 1
        elif token.lower() in { "hnote" }:
            over, _, remain = remain.strip().partition(" ")
            if over != "over":
                logging.debug('"hnote {over}" is not supported. ignored'.format(**vars()))
                logging.debug('    at {path} line.{lineNo} : "{line}"'.format(**vars()))
                continue
            clsName, _, remain = remain.strip().partition(" ")
            _, _, remain = remain.strip().partition(":")
            sttName, _, remain = remain.strip().partition("(")
            args = getArgs(remain[:-1])
            clsName = clsName.strip()
            if className != clsName:
                raise Exception('{className} != {clsName}'.format(**vars()))
            sttName = sttName.strip()
            if stateName is None:
                stateName = sttName
                argList = []
                for a in args:
                    varName, _, typeName = a.partition(':')
                    varName = varName.strip()
                    argList.append(varName)
                seqNo = 0
                sequenceList.append((SeqType.START, className, stateName, seqNo, None, None, argList, None, None))
                seqNo += 1
            else:
                sequenceList.append((SeqType.TRANSITION, className, stateName, seqNo, None, None, args, None, sttName))
                seqNo += 1
        elif token.lower() in { "alt" }:
            condition = remain.strip() or None
            sequenceList.append((SeqType.ALT, className, stateName, seqNo, None, None, None, condition, None))
            seqNo += 1
        elif token.lower() in { "opt" }:
            condition = remain.strip() or None
            sequenceList.append((SeqType.OPT, className, stateName, seqNo, None, None, None, condition, None))
            seqNo += 1
        elif token.lower() in { "loop" }:
            condition = remain.strip() or None
            sequenceList.append((SeqType.LOOP, className, stateName, seqNo, None, None, None, condition, None))
            seqNo += 1
        elif token.lower() in { "par" }:
            sequenceList.append((SeqType.PAR, className, stateName, seqNo, None, None, None, None, None))
            seqNo += 1
        elif token.lower() in { "else" }:
            condition = remain.strip() or None
            sequenceList.append((SeqType.ELSE, className, stateName, seqNo, None, None, None, condition, None))
            seqNo += 1
        elif token.lower() in { "end" }:
            sequenceList.append((SeqType.END, className, stateName, seqNo, None, None, None, None, None))
            seqNo +=1
        elif token.lower() in { "note" }:
            over, _, remain = remain.strip().partition(" ")
            if over != "over":
                logging.debug('"note {over}" is not supported. ignored'.format(**vars()))
                logging.debug('    at {path} line.{lineNo} : "{line}"'.format(**vars()))
                continue
            clsName, _, remain = remain.strip().partition(" ")
            if clsName != className:
                logging.debug('"note over {className} : xxx=val" is expected. ignored'.format(**vars()))
                logging.debug('    at {path} line.{lineNo} : "{line}"'.format(**vars()))
                continue
            _, _, remain = remain.strip().partition(":")
            varName, _, value = remain.strip().partition("=")
            varName = varName.strip()
            value = value.strip()
            sequenceList.append((SeqType.UPDATE, className, stateName, seqNo, None, varName, value, None, None))
            seqNo += 1
        elif token.lower() in { "return" }:
            value = remain.strip()
            value = None if not value else value
            sequenceList.append((SeqType.RETURN, className, stateName, seqNo, None, None, value, None, None))
            seqNo += 1
        elif token[0:2] in { "==" } or token.lower() in { "@startuml", "@enduml" }:
            if stateName is not None and seqNo is not None:
                sequenceList.append((SeqType.STOP, className, stateName, seqNo, None, None, None, None, None))
                seqNo += 1
            stateName = None
            seqNo = None
        elif '<-' in remain or '->' in remain:
            left = token
            arrow, _, remain = remain.strip().partition(" ")
            right, _, remain = remain.strip().partition(" ")
            _, _, remain = remain.strip().partition(":")
            method, _, remain = remain.strip().partition("(")
            args = getArgs(remain[:-1])
            arrow = arrow.strip()
            right = right.strip()
            method = method.strip()
            seqType = None
            sourceClassName = None
            targetClassName = None
            if arrow == "<-":
                if left == className:
                    seqType = SeqType.SMSGRECV
                else:
                    seqType = SeqType.SMSGSEND
                sourceClassName = right
                targetClassName = left
            elif arrow == "->":
                if left == className:
                    seqType = SeqType.SMSGSEND
                else:
                    seqType = SeqType.SMSGRECV
                sourceClassName = left
                targetClassName = right
            elif arrow == "<<-":
                if left == className:
                    seqType = SeqType.AMSGRECV
                else:
                    seqType = SeqType.AMSGSEND
                sourceClassName = right
                targetClassName = left
            elif arrow == "->>":
                if left == className:
                    seqType = SeqType.AMSGSEND
                else:
                    seqType = SeqType.AMSGRECV
                sourceClassName = left
                targetClassName = right
            else:
                logging.debug('"{arrow}" is not supported. ignored'.format(**vars()))
                logging.debug('    at {path} line.{lineNo} : "{line}"'.format(**vars()))
                continue
            '''
            if method not in define['Class'][targetClassName]:
                logging.debug('"{targetClassName}#{method}" is not defined. ignored'.format(**vars()))
                logging.debug('    at {path} line.{lineNo} : "{line}"'.format(**vars()))
                continue
            expectedNum = len(define['Class'][targetClassName][method]['args'])
            if len(args) != expectedNum:
                logging.debug('Argument number of "{targetClassName}#{method}" is expected {expectedNum}. ignored'.format(**vars()))
                logging.debug('    at {path} line.{lineNo} : "{line}"'.format(**vars()))
                continue
            if seqType in { SeqType.AMSGSEND, SeqType.AMSGRECV } and 'return' in define['Class'][targetClassName][method]:
                logging.debug('"{targetClassName}#{method}" is expected no return. ignored'.format(**vars()))
                logging.debug('    at {path} line.{lineNo} : "{line}"'.format(**vars()))
                continue
            if seqType in { SeqType.SMSGSEND, SeqType.SMSGRECV } and 'return' not in define['Class'][targetClassName][method]:
                logging.debug('"{targetClassName}#{method}" is expected return. ignored'.format(**vars()))
                logging.debug('    at {path} line.{lineNo} : "{line}"'.format(**vars()))
                continue
            '''
            if className == sourceClassName:
                sequenceList.append((seqType, className, stateName, seqNo, targetClassName, method, args, None, None))
            else:
                sequenceList.append((seqType, className, stateName, seqNo, sourceClassName, method, args, None, None))
            seqNo += 1
        else:
            logging.debug('ignored')
            logging.debug('     at {path} line.{lineNo} : "{line}"'.format(**vars()))
    return sequenceList

def translate(define, specSeqList, sysSeqList):
    for l in sysSeqList:
        logging.debug(l)
    logging.debug(define)
    result = []
    if 'Name' in define:
        for typeName in define['Name']:
            result.append('nametype {0} = {1}'.format(typeName, define['Name'][typeName]))
        result.append('')
    if 'Data' in define:
        for typeName in define['Data']:
            result.append('datatype {0} = {1}'.format(typeName, ' | '.join(define['Data'][typeName])))
        result.append('')
    result.append('datatype Class_ = {0}'.format(' | '.join(list(define['Class'].keys()))))
    varList = []
    for className in define['State']:
        for stateName in define['State'][className]:
            for varName, value in define['State'][className][stateName].items():
                varList.append('{0}_{1}_{2}.{3}'.format(className, stateName, varName, value))
    result.append('datatype StateVariable_ = {0}'.format(' | '.join(varList)))
    methodList = []
    for className in define['Class']:
        for methodName in define['Class'][className]:
            method = define['Class'][className][methodName]
            args = method['args']
            methodList.append('{0}_{1}{2}{3}'.format(className, methodName, '.' if args else '', '.'.join(args)))
            if 'return' in method:
                val = '.' + method['return'] if method['return'] is not None else ''
                methodList.append('return_{0}_{1}{2}'.format(className, methodName, val))
    result.append('datatype Method_ = {0}'.format(' | '.join(methodList)))
    result.append('')
    result.append('channel msg_ : Class_.Class_.Method_')
    result.append('channel rcv_ : Class_.Class_.Method_')
    result.append('channel update_ : StateVariable_')
    result.append('channel init_ : StateVariable_')
    result.append('channel sync_ : StateVariable_')
    result.append('')
    for className in define['External']:
        for targetClassName in [ c for c in define['Class'] if c != className ]:
            dstCallMethod = set([ "productions({0}_{1})".format(s[1], s[5]) for s in sysSeqList if s[0] in { SeqType.SMSGRECV, SeqType.AMSGRECV } and s[1] == targetClassName and s[4] == className ])
            srcReturnMethod = set([ "productions(return_{0}_{1})".format(s[4], s[5]) for s in sysSeqList if s[0] in { SeqType.SMSGSEND } and s[1] == targetClassName and s[4] == className ])
            dstMethod = ", ".join(dstCallMethod | srcReturnMethod)
            if dstMethod:
                result.append('getCallMethod_({className}, {targetClassName}) = Union({{ {dstMethod} }})'.format(**vars()))
    for className in define['Internal']:
        for targetClassName in [ c for c in define['Class'] if c != className ]:
            dstCallMethod = set([ "productions({0}_{1})".format(s[4], s[5]) for s in sysSeqList if s[0] in { SeqType.SMSGSEND, SeqType.AMSGSEND } and s[1] == className and s[4] == targetClassName ])
            srcReturnMethod = set([ "productions(return_{0}_{1})".format(s[1], s[5]) for s in sysSeqList if s[0] in { SeqType.SMSGRECV } and s[1] == className and s[4] == targetClassName ])
            dstMethod = ", ".join(dstCallMethod | srcReturnMethod)
            if dstMethod:
                result.append('getCallMethod_({className}, {targetClassName}) = Union({{ {dstMethod} }})'.format(**vars()))
    result.append('getCallMethod_(_, _) = {}')
    sysUpdater = ''
    for className in define['State']:
        for stateName in define['State'][className]:
            stateUpdateList = []
            for varName in define['State'][className][stateName]:
                stateUpdateList.append('{className}_{stateName}_{varName}'.format(**vars()))
            if stateUpdateList:
                stateUpdate = ', '.join([ 'productions({0})'.format(s) for s in stateUpdateList ])
                if className == 'System':
                    sysUpdater = ', {{ update_.v, sync_.v, init_.v | v <- Union({{{stateUpdate}}})}}'.format(**vars())
                else:
                    result.append('getStateVariableUpdate_({className}) = Union({{{stateUpdate}}})'.format(**vars()))
    result.append('getStateVariableUpdate_(_) = {}')
    result.append('')
    result.append('interface_(c) = Union({{msg_.f.c.m | f <- diff(Class_, {c}), m <- getCallMethod_(f, c) }, {msg_.c.t.m | t <- diff(Class_, {c}), m <- getCallMethod_(c, t) }, {update_.v, sync_.v, init_.v | v <- getStateVariableUpdate_(c)}})')
    result.append('')
    result.append('externalRecvInterface_() = Union({{{{ f.c.m | f <- diff(Class_, {{c}}), m <- getCallMethod_(f, c) }} | c <- {{{0}}}}})'.format(', '.join(define['External'])))
    result.append('externalInterface_() = Union({{{0}{1}}})'.format(', '.join([ 'interface_({0})'.format(d) for d in define['External'] ]), sysUpdater))
    result.append('')
    result.append('ExternalRecv() = [] x : externalRecvInterface_() @ msg_.x -> rcv_.x -> ExternalRecv()')
    result.append('')
    specUpdaters = []
    for className in define['State']:
        for stateName in define['State'][className]:
            for varName, value in define['State'][className][stateName].items():
                result.append('Updater_{0}_{1}_{2}_Init = init_.{0}_{1}_{2}?v_ -> Updater_{0}_{1}_{2}(v_)'.format(className, stateName, varName))
                result.append('Updater_{0}_{1}_{2}(val) = init_.{0}_{1}_{2}?v_ -> Updater_{0}_{1}_{2}(v_) [] update_.{0}_{1}_{2}?v_ -> Updater_{0}_{1}_{2}(v_) [] sync_.{0}_{1}_{2}!val -> Updater_{0}_{1}_{2}(val)'.format(className, stateName, varName))
                if className == 'System':
                    specUpdaters.append('Updater_{0}_{1}_{2}_Init'.format(className, stateName, varName))
    result.append('')
    for i, className in enumerate(['System'] + define['Internal']):
        updaters = []
        for stateName in define['State'][className]:
            for varName, value in define['State'][className][stateName].items():
                updaters.append('Updater_{0}_{1}_{2}_Init'.format(className, stateName, varName))
        updtr = '[|{{| update_, sync_, init_ |}}|] ( {0} ) \ {{| update_, sync_, init_ |}}'.format(' ||| '.join(updaters)) if updaters else ''
        exRcv = '[| {| rcv_ |} |] ExternalRecv() \ {| rcv_ |}' if i == 0 else ''
        result.append('getClassProcFromIndex_({i}) = ( {className}_Init_0() {exRcv} ) {updtr}'.format(**vars()))
    result.append('getInterfaceFromIndex_(0) = externalInterface_()')
    for i, s in enumerate(define['Internal']):
        i += 1
        result.append('getInterfaceFromIndex_({i}) = interface_({s})'.format(**vars()))
    result.append('')
    result.append('System_ = (|| x:{{0..{0}}} @ [ getInterfaceFromIndex_(x) ] getClassProcFromIndex_(x)) \ diff(Events, externalInterface_())'.format(len(define['Internal'])))
    result.append('Spec_ = Spec_Init_0() {0}'.format(' [|{{| update_, sync_, init_ |}}|] ( {0} ) \ {{| update_, sync_, init_ |}}'.format(' ||| '.join(specUpdaters)) if specUpdaters else ''))
    result.append('')
    result.append('assert Spec_ [F= System_')
    for r in getSeqCspm('System', specSeqList, True):
        result.append(r)
    for r in getSeqCspm('System', specSeqList, False):
        result.append(r)
    for className in define['Internal']:
        for r in getSeqCspm(className, sysSeqList, False):
            result.append(r)
    result.append('')
    for l in result:
        logging.debug(l)
    return result

def getSeqCspm(targetClassName, sequenceList, spec):
    result = []
    result.append('')
    valList = []
    valListStack = []
    groupStack = []
    callerClassStack = []
    calleeClassStack = []
    calleeMethodStack = []
    seqList = [seq for seq in sequenceList if targetClassName == 'System' or seq[1]==targetClassName]
    for i, s in enumerate(seqList):
        seqType = s[0]
        className = s[1]
        stateName = s[2]
        seqNo = s[3]
        nextSeqNo = s[3] + 1
        val = ', '.join(valList)
        calleeClass = callerClass = createClassName = s[4]
        method = s[5]
        args = s[6]
        condition = s[7]
        nextState = s[8]
        procClassName = 'Spec' if spec else 'System' if targetClassName == 'System' else className
        recvMark = "$" if spec else "?"
        select = "|~|" if spec else "[]"
        sync = ''
        updaters = []
        al = ', '.join(args) if isinstance(args, list) else '' if args is None else args
        for varName in define['State'][className][stateName]:
            if condition is not None or (isinstance(args, list) and varName in args) or (isinstance(args, str) and varName == args):
                updaters.append('sync_.{className}_{stateName}_{varName}?{varName}'.format(**vars()))
        sync = ' -> '.join(updaters)
        sync += ' -> ' if sync else ''
        channel = 'msg_'
        if seqType == SeqType.START:
            valList = []
            callerClassStack = []
            calleeClassStack = []
            calleeMethodStack = []
            result.append('{procClassName}_{stateName}_{seqNo}() = {procClassName}_{stateName}_{nextSeqNo}()'.format(**vars()))
        elif seqType in { SeqType.SMSGRECV, SeqType.AMSGRECV }:
            newValList = valList.copy()
            for nv in [v for v in args if v not in valList]:
                newValList.append(nv)
            newVal = ', '.join(newValList)
            method = '{0}_{1}'.format(className, method)
            args = (recvMark if args else "") + recvMark.join(args)
            result.append('{procClassName}_{stateName}_{seqNo}({val}) = {channel}.{callerClass}.{className}.{method}{args} -> {procClassName}_{stateName}_{nextSeqNo}({newVal})'.format(**vars()))
            valList = newValList.copy()
            if seqType == SeqType.SMSGRECV:
                callerClassStack.append(callerClass)
                calleeClassStack.append(className)
                calleeMethodStack.append(method)
        elif seqType in { SeqType.SMSGSEND, SeqType.AMSGSEND }:
            method = '{0}_{1}'.format(calleeClass, method)
            args = ("!" if args else "") + "!".join(args)
            callerClass = className
            if targetClassName == 'System':
                if not spec:
                    channel = 'rcv_'
                result.append('{procClassName}_{stateName}_{seqNo}({val}) = {sync}{channel}{recvMark}caller_!{calleeClass}.{method}{args} -> {procClassName}_{stateName}_{nextSeqNo}({val})'.format(**vars()))
            else:
                result.append('{procClassName}_{stateName}_{seqNo}({val}) = {sync}{channel}.{callerClass}.{calleeClass}.{method}{args} -> {procClassName}_{stateName}_{nextSeqNo}({val})'.format(**vars()))
            if seqType == SeqType.SMSGSEND:
                callerClassStack.append(callerClass)
                calleeClassStack.append(calleeClass)
                calleeMethodStack.append(method)
        elif seqType == SeqType.RETURN:
            try:
                callerCls = calleeClassStack.pop()
                calleeCls = callerClassStack.pop()
                calleeMtd = calleeMethodStack.pop()
            except:
                errStr = ['Caller or Callee stack is empty', '    at {className} {stateName} {seqNo}'.format(**vars())]
                for e in errStr:
                    logging.error(e)
                raise Exception('\n'.join(errStr))
            newVal = val
            newValList = valList.copy()
            if calleeCls == className and args not in valList and args is not None and args[0].islower():
                newValList.append(args)
                newVal = ', '.join(newValList)
            args = "{0}{1}".format("!" if callerCls == className else recvMark if args[0].islower() else "." , args) if args else ""
            if not spec and calleeCls in define['External'] and targetClassName == 'System':
                channel = 'rcv_'
            sync = sync if callerCls == className else ''
            if targetClassName == 'System' and callerCls in define['External']:
                result.append('{procClassName}_{stateName}_{seqNo}({val}) = {sync}{channel}.{callerCls}{recvMark}callee_!return_{calleeMtd}{args} -> {procClassName}_{stateName}_{nextSeqNo}({newVal})'.format(**vars()))
            else:
                result.append('{procClassName}_{stateName}_{seqNo}({val}) = {sync}{channel}.{callerCls}.{calleeCls}.return_{calleeMtd}{args} -> {procClassName}_{stateName}_{nextSeqNo}({newVal})'.format(**vars()))
            valList = newValList.copy()
        elif seqType == SeqType.TRANSITION:
            newValList = args.copy()
            if nextState == 'End':
                result.append('{procClassName}_{stateName}_{seqNo}({val}) = SKIP'.format(**vars()))
            else:
                us = '{sync}'.format(**vars())
                updaters = []
                for _i, varName in enumerate(define['State'][className][nextState]):
                    value = newValList[_i]
                    updaters.append('init_.{className}_{nextState}_{varName}!{value}'.format(**vars()))
                us += ' -> '.join(updaters)
                us += ' -> ' if updaters else ''
                result.append('{procClassName}_{stateName}_{seqNo}({val}) = {us}{procClassName}_{nextState}_0()'.format(**vars()))
        elif seqType == SeqType.ALT:
            valListStack.append(valList.copy())
            groupStack.append(SeqType.ALT)
            endIndex, elseIndexes = getElseEndIndexes(seqList, i)
            endSeqNo = seqList[endIndex][3] + 1
            r = ''
            if condition is not None:
                r = '{sync}'.format(**vars())
                for (cond, nsn) in ([ (condition, nextSeqNo) ] + [ (seqList[_i][7], seqList[_i][3] + 1) for _i in elseIndexes ]):
                    if cond is not None:
                        r += 'if {cond}\n    then {procClassName}_{stateName}_{nsn}({val})\n    else '.format(**vars())
                    else:
                        r += '{procClassName}_{stateName}_{nsn}({val})'.format(**vars())
                if seqList[elseIndexes[-1]][7] is not None:
                    r += '{procClassName}_{stateName}_{endSeqNo}({val})'.format(**vars())
            else:
                f = '{procClassName}_{stateName}_{{0}}({val})'.format(**vars())
                r = "\n     {select} ".format(**vars()).join([ f.format(seqList[_i + 1][3]) for _i in [i] + elseIndexes ])
            result.append("{procClassName}_{stateName}_{seqNo}({val}) = {r}".format(**vars()))
        elif seqType == SeqType.OPT:
            valListStack.append(valList.copy())
            groupStack.append(SeqType.OPT)
            endIndex, _ = getElseEndIndexes(seqList, i)
            r = ''
            endSeqNo = seqList[endIndex][3] + 1
            if condition is not None:
                r = '{sync}if {condition} then {procClassName}_{stateName}_{nextSeqNo}({val})\n    else {procClassName}_{stateName}_{endSeqNo}({val})'.format(**vars())
            else:
                r = '{procClassName}_{stateName}_{nextSeqNo}({val})\n    {select} {procClassName}_{stateName}_{endSeqNo}({val})'.format(**vars())
            result.append("{procClassName}_{stateName}_{seqNo}({val}) = {r}".format(**vars()))
        elif seqType == SeqType.LOOP:
            valListStack.append(valList.copy())
            groupStack.append(SeqType.LOOP)
            endIndex, _ = getElseEndIndexes(seqList, i)
            r = ''
            endSeqNo = seqList[endIndex][3] + 1
            if condition is not None:
                r = '{sync}if {condition} then ({procClassName}_{stateName}_{nextSeqNo}({val});{procClassName}_{stateName}_{seqNo}({val}))\n    else {procClassName}_{stateName}_{endSeqNo}({val})'.format(**vars())
            else:
                r = '{sync}{procClassName}_{stateName}_{nextSeqNo}({val});{procClassName}_{stateName}_{seqNo}({val})'.format(**vars())
            result.append("{procClassName}_{stateName}_{seqNo}({val}) = {r}".format(**vars()))
        elif seqType == SeqType.PAR:
            valListStack.append(valList.copy())
            groupStack.append(SeqType.PAR)
            endIndex, elseIndexes = getElseEndIndexes(seqList, i)
            endSeqNo = seqList[endIndex][3] + 1
            seqNoList = [ seqList[_i + 1][3] for _i in [i] + elseIndexes ]
            f = '{procClassName}_{stateName}_{{0}}({val})'.format(**vars())
            r = '{0}'.format("\n    ||| ".join([ f.format(sn) for sn in seqNoList ]))
            updateList = []
            newVal = ', '.join([ v + '_' for v in valList])
            result.append("{procClassName}_{stateName}_{seqNo}({val}) = ({r}); {procClassName}_{stateName}_{endSeqNo}({newVal})".format(**vars()))
        elif seqType == SeqType.ELSE:
            newValList = valListStack[-1].copy()
            group = groupStack[-1]
            if group == SeqType.PAR:
                result.append('{procClassName}_{stateName}_{seqNo}({val}) = SKIP'.format(**vars()))
            else:
                newVal = ', '.join(newValList)
                endIndex, _ = getElseEndIndexes(seqList, i)
                endSeqNo = seqList[endIndex][3] + 1
                result.append('{procClassName}_{stateName}_{seqNo}({val}) = {procClassName}_{stateName}_{endSeqNo}({newVal})'.format(**vars()))
            valList = newValList.copy()
        elif seqType == SeqType.END:
            newValList = valListStack.pop()
            group = groupStack.pop()
            if group in { SeqType.PAR, SeqType.LOOP }:
                result.append('{procClassName}_{stateName}_{seqNo}({val}) = SKIP'.format(**vars()))
            else:
                newVal = ', '.join(newValList)
                result.append('{procClassName}_{stateName}_{seqNo}({val}) = {procClassName}_{stateName}_{nextSeqNo}({newVal})'.format(**vars()))
            valList = newValList.copy()
        elif seqType == SeqType.UPDATE:
            newVal = val.replace(method, args)
            result.append('{procClassName}_{stateName}_{seqNo}({val}) = {sync}update_.{className}_{stateName}_{method}.{args} -> {procClassName}_{stateName}_{nextSeqNo}({newVal})'.format(**vars()))
        elif seqType == SeqType.STOP:
            result.append('{procClassName}_{stateName}_{seqNo}({val}) = STOP'.format(**vars()))
    return result

def getElseEndIndexes(seqList, index):
    elseIndexes = []
    endIndex = None
    nestNum = 0
    for i, s in enumerate(seqList):
        if i <= index:
            continue
        if s[0] == SeqType.END:
            if nestNum == 0:
                endIndex = i
                break
            else:
                nestNum -= 1
        elif nestNum == 0 and s[0] == SeqType.ELSE:
            elseIndexes.append(i)
        elif s[0] in { SeqType.OPT, SeqType.ALT, SeqType.PAR }:
            nestNum += 1
        else:
            continue
    return endIndex, elseIndexes


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)-8s: %(message)s', level=logging.WARNING)
    if len(sys.argv) < 5:
        logging.error('Usage: %s inSpecFile inImplFile inDefineFile outCspmFile' % sys.argv[0])
        quit()
    with open(sys.argv[3], "r") as d, open(sys.argv[4], "w") as out:
        define = yaml.load(d)
        define = normalizeDefine(define, sys.argv[1], sys.argv[2])
        specSeqList = parse(define, sys.argv[1])
        sysSeqList = parse(define, sys.argv[2])
        specSeqList = normalizeSpecList(specSeqList, sysSeqList)
        out.write("\n".join(translate(define, specSeqList, sysSeqList)))

