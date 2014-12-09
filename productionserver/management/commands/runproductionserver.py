import sys
import os

from django.core.management.base import BaseCommand
from django.core.servers.basehttp import get_internal_wsgi_application
from optparse import make_option

import cherrypy


class Command(BaseCommand):
    help = r"""Run the Django project using CherryPy as the server.
    Taking place of the 'manage.py runserver', which is for development purposes only, this is suitable for small to medium server deployments.

    CherryPy (http://www.cherrypy.org) is required.
    Futures (https://pypi.python.org/pypi/futures) is required.
    """
    args = "[--option=value, use `runproductionserver help` for help]"

    options = None

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
        self.options = options

        # Get this Django Project's WSGI Application and mount it
        application = get_internal_wsgi_application()
        cherrypy.tree.graft(application, "/")

        # Unsubscribe the default server
        cherrypy.server.unsubscribe()

        # Instantiate a new server
        server = cherrypy._cpserver.Server()

        # Configure the server
        server.socket_host = self.options['host']
        server.socket_port = self.options['port']
        server.thread_pool = 30

        # For SSL Support
        # server.ssl_module = 'pyopenssl'
        # server.ssl_certificate = 'ssl/certificate.crt'
        # server.ssl_private_key = 'ssl/private.key'
        # server.ssl_certificate_chain = 'ssl/bundle.crt

        # Subscribe the new server
        server.subscribe()

        cherrypy.engine.start()
        cherrypy.engine.block()