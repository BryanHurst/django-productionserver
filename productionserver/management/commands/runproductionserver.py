import sys
import os

from django.core.management.base import BaseCommand

from optparse import make_option


class Command(BaseCommand):
    help = r"""Run the Django project using CherryPy as the server.
    Taking place of the 'manage.py runserver', which is for development purposes only, this is suitable for small to medium server deployments.

    CherryPy (http://www.cherrypy.org) is required.
    Futures (https://pypi.python.org/pypi/futures) is required.
    """
    args = "[--option=value, use `runproductionserver help` for help]"

    option_list = BaseCommand.option_list + (
        make_option('--host',
                    action='store',
                    type='string',
                    dest='host',
                    default='0.0.0.0',
                    help='Adapter to listen on. Default is 0.0.0.0'),
        make_option('--port',
                    action='store',
                    type='int',
                    dest='port',
                    default=8080,
                    help='Port to listen on. Default is 8080. Note, port 80 requires root access'),
    )

    def handle(self, *args, **options):
        pass