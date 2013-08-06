import re
import subprocess
import string

import sys, os

from itertools import imap, ifilter, groupby
from datetime import datetime 
from lxml import etree
from lxml import objectify

class DateParseException(Exception):
    pass

class ConversionException(Exception):
    pass

# The mini-parser classes that workon lines/paras
class Parslet(object):
    text = None

    def __init__(self, **kwargs):
        self.text  = kwargs.pop('text')
        if len(kwargs):
            raise Exception("Unknown parameters %s" % str(kwargs.keys()))

    @classmethod
    def handle_match(cls, parser, p):
        ret = cls._handle_match(parser, p)
        if ret:
            return cls(**ret)

class SingleLineParslet(Parslet):
    @classmethod
    def _handle_match(cls, parser, p):
        if len(p) != 1:
            return None
        return cls.match(parser, p[0])

class ParaParslet(Parslet):
    @classmethod
    def _handle_match(cls, parser, p):
        jp = re.sub(
                r'\s+', 
                ' ', 
                ' '.join(p))
        return cls.match(parser, jp)

class DateParslet(SingleLineParslet):
    date = None
    date_xml = None

    def __init__(self, **kwargs):
        self.date     = kwargs.pop('date')
        self.date_xml = kwargs.pop('date_xml')

    @classmethod
    def match(cls, parser, line):
        if parser.hasDate:
            return None

        match = re.compile(r'(\d+)[ ,]+(\w+)[ ,]+(\d+)$').search(line)
        if not match:
            # we are assuming that *every* document has a date as first
            # thing, and throw an exception instead of simply returning
            # None.  This assumption seems good for now.  (Note that
            # later steps require the presence of a date)
            raise DateParseException("Couldn't match date in %s" % line)

        date = datetime.strptime(' '.join(match.groups()), '%d %B %Y')
        date_xml = date.strftime('%Y-%m-%d')

        parser.hasDate = True

        return {
                'text': line,
                'date': date,
                'date_xml': date_xml,
                }

    def output(self, parser, E):

        date = self.date
        date_xml = self.date_xml

        elem = E.p(
                    datetime.strftime(date, '%A, '),
                    E.docDate(date.strftime('%d %B %Y'),
                        date=date_xml))
        parser.current.append(elem)
        parser.date = date

        identification = parser.akomaNtoso.debate.meta.identification
        identification.FRBRWork.FRBRthis.set('value', '/za/debaterecord/%s/main' % date_xml)
        identification.FRBRWork.FRBRuri.set('value', '/za/debaterecord/%s' % date_xml)
        identification.FRBRExpression.FRBRthis.set('value', '/za/debaterecord/%s/eng@/main' % date_xml)
        identification.FRBRExpression.FRBRuri.set('value', '/za/debaterecord/%s/eng@' % date_xml)
        identification.FRBRManifestation.FRBRthis.set('value', '/za/debaterecord/%s/eng@/main.xml' % date_xml)
        identification.FRBRManifestation.FRBRuri.set('value', '/za/debaterecord/%s/eng@.akn' % date_xml)

class TitleParslet(ParaParslet):

    @classmethod
    def match(cls, parser, p):
        line = re.sub('\s+', ' ', ' '.join(p))
        mline = line.replace('see col', '')
        if re.search(r'[a-z]', mline):
            return None
        return { 'text': line }
    
    def output(self, parser, E):
        line = self.text
        if parser.hasTitle:
            parser.createSubsection(line)
        else:
            parser.setTitle(line)

# Line parslet, because only sufficiently short lines are candidates for adding to a header,
# (we assume)
class ParensParslet(SingleLineParslet):

    @classmethod
    def match(cls, parser, line):
        if re.match(r'\s*\(.*\)\.?$', line):
            return { 'text': line.lstrip() }
        return None

    def output(self, parser, E):
        if etree.QName(parser.current.tag).localname == 'debateSection':
            # munging existing text in Objectify seems to be frowned upon.  Ideally refactor
            # this to be more functionl to avoid having to do call private _setText method...
            parser.current.heading._setText( '%s %s' % 
                    (parser.current.heading.text, self.text ))

class AssembledParslet(ParaParslet):

    assembled = None
    time = None
    time_iso = None

    def __init__(self, **kwargs):
        self.assembled = kwargs.pop('assembled')
        self.time = kwargs.pop('time')
        self.time_iso = kwargs.pop('time_iso')

    @classmethod
    def match(cls, parser, p):
        if parser.hasAssembled:
            return None

        ret = re.search(r'^(.*(?:assembled|met)(?: in .*)? at )(\d+:\d+)\.?$', p)
        if ret:
            groups = ret.groups()
            time = datetime.strptime(groups[1], '%H:%M').time()
            # time = datetime.combine(self.date, time).replace(tzinfo=self.tz)

            return {
                    'text': p,
                    'assembled': groups[0],
                    'time': groups[1],
                    'time_iso': time.isoformat(),
                    }
        else:
            return None

    def output(self, parser, E):
        elem = E.p(
                self.assembled,
                E.recordedTime(
                    self.time,
                    time= self.time_iso,
                ))
        parser.current.append(elem)
        parser.hasAssembled = True

# TODO refactor this with AssembledParslet
class AroseParslet(ParaParslet):

    assembled = None
    time = None
    time_iso = None

    def __init__(self, **kwargs):
        self.arose = kwargs.pop('arose')
        self.time = kwargs.pop('time')
        self.time_iso = kwargs.pop('time_iso')

    @classmethod
    def match(cls, parser, p):
        if parser.hasArisen:
            return None

        ret = re.search(r'^(.*(?:rose) at )(\d+:\d+)\.?$', p)
        if ret:
            groups = ret.groups()
            time = datetime.strptime(groups[1], '%H:%M').time()
            # arose = datetime.combine(self.date, time).replace(tzinfo = self.tz)

            return {
                    'text': p,
                    'arose': groups[0],
                    'time': groups[1],
                    'time_iso': time.isoformat(),
                    }

    def output(self, parser, E):
        elem = E.adjournment(
                E.p(
                    self.arose,
                    E.recordedTime(
                        self.time,
                        time= self.time_iso,
                    )),
                id='adjournment')
        parser.current.getparent().append(elem)
        parser.hasArisen = True

class PrayersParslet(ParaParslet):

    @classmethod
    def match(cls, parser, p):
        if parser.hasPrayers:
            return None

        if re.search(r'^(.* prayers or meditation.)$', p):
            return { 'text': p }

    def output(self, parser, E):
        elem = E.prayers(
            E.p(self.text), 
            id='prayers')
        parser.current.append(elem)
        parser.hasPrayers = True

class SpeechParslet(ParaParslet):

    name = None
    speech = None
    id = None

    def __init__(self, **kwargs):
        self.name = kwargs.pop('name')
        self.speech = kwargs.pop('speech')
        self.id = kwargs.pop('id')

    @classmethod
    def match(cls, parser, p):
        name_regexp = r'((?:[A-Z][a-z]+ )[A-Z -]+(?: \(\w+\))?):\s*(.*)'
        ret = re.match(name_regexp, p)
        if ret:
            (name, speech) = ret.groups()
            id = parser.getOrCreateSpeaker(name) # TODO match with popit here

            return {
                    'text': p,
                    'name': name,
                    'speech': speech.lstrip(),
                    'id': id,
                    }

    def output(self, parser, E):
        elem = E.speech(
                    E('from',  self.name ),
                    E.p(self.speech),
                    by='#%s' % self.id)
            
        if etree.QName(parser.current.tag).localname == 'speech':
            parser.current = parser.current.getparent()
        parser.current.append(elem)
        parser.current = elem

class ContinuationParslet(ParaParslet):

    @classmethod
    def match(cls, parser, p):
        return { 'text': p }

    def output(self, parser, E):
        if not parser.hasTitle:
            parser.setTitle(self.text.upper())
        elif not parser.subSectionCount:
            parser.createSubsection(self.text.upper())
        else:
            # TODO: this needs some more thought to emit subheadings if appropriate
            tag = 'p'
            parser.current.append( E(tag, self.text.lstrip() ) )

class ZAHansardParser(object):

    E = objectify.ElementMaker(
            annotate=False,
            namespace="http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03",
            nsmap={None : "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03"},
            )

    def __init__(self):
        E = self.E
        self.akomaNtoso = E.akomaNtoso(
                E.debate(
                    E.meta(),
                    E.preface()))
        self.current = self.akomaNtoso.debate.preface

        self.hasDate = False
        self.date = None
        self.hasTitle = False
        self.hasAssembled = False
        self.hasArisen = False
        self.hasPrayers = False
        self.subSectionCount = 0
        self.speakers = {}

    @classmethod
    def parse(cls, document_path):
        
        antiword = subprocess.Popen(
                ['antiword', document_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        (stdoutdata, stderrdata) = antiword.communicate()
        if antiword.returncode:
            # e.g. not 0 (success) or None (still running) so presumably an error
            raise ConversionException("Could not convert %s (%s)" % (document_path, stdoutdata.rstrip()))

        def cleanLine(line):
            line = line.rstrip(' _\n')
            # NB: string.printable won't filter unicode correctly...
            line = filter(lambda x: x in string.printable, line)
            return line

        # lines = imap(cleanLine, iter(antiword.stdout.readline, b''))
        lines = imap(cleanLine, iter(stdoutdata.split('\n')))

        def break_paras(line):
            # FIRST we handle exceptions:
            # NB: these lines should probably actually be included with their respective heading
            if re.match( r'\s*\((Member\'?s? [sS]tatement|Minister\'s? [Rr]esponse\))', line ):
                return line # distinct from True or False, but a True value

            # An ALL CAPS heading might be on the first line of a new page and therefore not be separated
            # by blank lines
            if re.match( r'\s*[A-Z]+', line ) and not re.search( r'[a-z]', line ):
                return "TITLE"

            # FINALLY we just swap between True and False for full and blank lines, to chunk into paragraphs
            return len(line) > 0

        fst = lambda(a,_): a
        snd = lambda(_,b): b

        groups = groupby(lines, break_paras)
        nonEmpty = ifilter(fst, groups)
        paras = imap(snd, nonEmpty)

        obj = ZAHansardParser()

        E = obj.E
        # TODO: instead of ctime use other metadata from source document?
        # ctime = datetime.fromtimestamp(os.path.getctime(document_path)).strftime('%Y-%m-%d')
        today = datetime.now().date().strftime('%Y-%m-%d')

        obj.akomaNtoso.debate.meta.append(
            E.identification(
                E.FRBRWork(
                    E.FRBRthis(),
                    E.FRBRuri(),
                    E.FRBRdate( date=today,  name='generation' ),
                    E.FRBRauthor( href='#za-parliament'), # as='#author' # XXX
                    E.FRBRcountry( value='za' ),
                ),
                E.FRBRExpression(
                    E.FRBRthis(),
                    E.FRBRuri(),
                    E.FRBRdate( date=today,  name='markup' ),
                    E.FRBRauthor( href='#za-parliament'), # as='#editor' # XXX
                    E.FRBRlanguage( language='eng' ),
                ),
                E.FRBRManifestation(
                    E.FRBRthis(),
                    E.FRBRuri(),
                    E.FRBRdate( date=today, name='markup' ),
                    E.FRBRauthor( href='#mysociety'), # as='#editor' # XXX
                ),
                source='#mysociety'),
            )
        obj.akomaNtoso.debate.meta.append( 
                E.references(
                    E.TLCOrganization(
                        id='za-parliament',
                        showAs='ZA Parliament',
                        href='http://www.parliament.gov.za/',
                        ),
                    E.TLCOrganization(
                        id='mysociety',
                        showAs='MySociety',
                        href='http://www.mysociety.org/',
                        ),
                    source='#mysociety'))

        classes = [
                DateParslet,
                TitleParslet,
                ParensParslet,
                AssembledParslet,
                AroseParslet,
                PrayersParslet,
                SpeechParslet,
                ContinuationParslet,
                ]

        def match(p):
            #try:
                m = ifilter(
                        lambda x: x != None, 
                        imap(
                            lambda cls: cls.handle_match(obj, p),
                            classes)
                        ).next()
                return m
            #except Exception as e:
                #raise e
                #raise Exception("Parsing failed at '%s'" % p[:50])

        nodes = [match(list(p)) for p in paras]

        # TODO transformation step here! (i.e. the whole point of this refactor)

        for n in nodes:
            n.output(obj, obj.E)

        return obj

    def setTitle(self, line):
        E = self.E
        line = line.lstrip().replace( '\n', '')
        elem = E.debateBody(
                E.debateSection(
                    E.heading(line, id='dbh0'),
                    id='db0',
                    name=self.slug(line)))
        self.akomaNtoso.debate.append( elem )
        self.akomaNtoso.debate.set('name', line)
        self.current = elem.debateSection
        self.hasTitle = True

    def createSubsection(self, line):
        E = self.E
        line = line.lstrip().replace( '\n', '')
        self.subSectionCount += 1
        elem = E.debateSection(
            E.heading(line,
                id='dbsh%d'% self.subSectionCount),
            id='dbs%d' % self.subSectionCount,
            name=self.slug(line))
        self.akomaNtoso.debate.debateBody.debateSection.append(elem)
        self.current = elem


    def getOrCreateSpeaker(self, name):
        speaker = self.speakers.get(name)
        if speaker:
            return speaker
        slug = self.slug(name)
        self.speakers[name] = slug
        E = self.E
        self.akomaNtoso.debate.meta.references.append(
                E.TLCPerson(
                    id=slug,
                    showAs=name,
                    href='http://dummy/popit/path/%s' % slug ))
        return slug

    def slug(self, line):
        return re.sub('\W+', '-', line.lower())

