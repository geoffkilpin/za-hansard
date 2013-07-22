
# This script changed extensively when the Kenyan Parliament website changed after the 2013 Election.
#
# The previous version can be seen at:
#
#    https://github.com/mysociety/mzalendo/blob/7181e30519b140229e3817786e4a7440ac08288d/mzalendo/hansard/management/commands/hansard_check_for_new_sources.py

import pprint
import httplib2
import re
import datetime
import time
import sys

from bs4 import BeautifulSoup
from lxml import etree

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from optparse import make_option

from zah.models import Source, SourceUrlCouldNotBeRetrieved
from zah.parse import ZAHansardParser

class FailedToRetrieveSourceException (Exception):
    pass

class Command(BaseCommand):
    help = 'Parse unparsed'
    option_list = BaseCommand.option_list + (
        make_option('--redo',
            default=False,
            action='store_true',
            help='Redo already completed parses',
        ),
        make_option('--retry',
            default=False,
            action='store_true',
            help='Retry attempted (but not completed) parses',
        ),
        make_option('--retry-download',
            default=False,
            action='store_true',
            help='Retry download of previously 404\'d documents',
        ),
        make_option('--limit',
            default=10,
            type='int',
            help='limit query (default 10)',
        ),
    )

    def handle(self, *args, **options):
        limit = options['limit']

        if options['redo']:
            if options['retry_download']:
                sources = Source.objects.all()
            else:
                sources = Source.objects.filter(is404 = False)
        elif options['retry']:
            sources = Source.objects.all().requires_completion( options['retry_download'] )
        else:
            sources = Source.objects.all().requires_processing()

        sources.defer('xml')
        for s in sources[:limit]:
        # for s in sources[:limit].iterator():
            if s.language != 'English':
                self.stdout.write("Skipping non-English for now...") # fails date parsing, hehehe
                continue
            s.last_processing_attempt = datetime.datetime.now().date()
            s.save()
            try:
                try:
                    filename = s.file()
                except SourceUrlCouldNotBeRetrieved as e:
                    s.is404 = True
                    s.save()
                    raise e
                obj = ZAHansardParser.parse(filename)
                s.xml = etree.tostring(obj.akomaNtoso)
                s.last_processing_success = datetime.datetime.now().date()
                open('%s.xml' % filename, 'w').write(s.xml)
                s.save()
                self.stdout.write( "Processed %s (%d)" % (s.document_name, s.document_number) )
            except Exception as e:
                # raise CommandError("Failed to run parsing: %s" % str(e))
                self.stderr.write("WARN: Failed to run parsing: %s" % str(e))
