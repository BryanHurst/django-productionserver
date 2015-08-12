import sys
import os
import signal
import shutil
import subprocess

from django.core.management.base import BaseCommand
from django.core.servers.basehttp import get_internal_wsgi_application
from django.conf import settings
from django.utils.timezone import now
from optparse import make_option
from tempfile import mkstemp
from time import sleep

import cherrypy


class Command(BaseCommand):
    help = r"""Run the Django project using CherryPy as the App Server and NGINX as the Static Server.
    Taking place of the 'manage.py runserver', which is for development purposes only, this is suitable for small to medium server deployments.

    CherryPy (http://www.cherrypy.org) is required.
    Futures (https://pypi.python.org/pypi/futures) is required (for CherryPy).
    NGINX is included.

    Examples:
        Run a server on external port 80 with Django running on internal port 25566
            $ manage.py runproductionserver --host=0.0.0.0 --port=80 --app_port=25566
    """
    args = "[--option=value, use `runproductionserver help` for help]"

    options = None
    if getattr(sys, 'frozen', False):
        PRODUCTIONSERVER_DIR = os.path.join(settings.BASE_DIR)
    else:
        PRODUCTIONSERVER_DIR = os.path.dirname(os.path.abspath(__file__))

    option_list = BaseCommand.option_list + (
        make_option('--host',
                    action='store',
                    type='string',
                    dest='host',
                    default='127.0.0.1',
                    help='Adapter to listen on. Default is 127.0.0.1'),
        make_option('--port',
                    action='store',
                    type='int',
                    dest='port',
                    default=8080,
                    help='External Port to listen on (what you navigate to). Default is 8080. Note, port 80 requires root access'),
        make_option('--app_port',
                    action='store',
                    type='int',
                    dest='app_port',
                    default=8081,
                    help='Port for the CherryPy App Server (what hosts the Django App) to listen on. Default is 8181. Note, this must be different from the normal Server Port.'),
        make_option('--silent',
                    action='store_true',
                    dest='silent',
                    default=False,
                    help='Hide all console output.')
    )

    def handle(self, *args, **options):
        self.options = options

        if hasattr(settings, 'WORKSPACE_PATH') and settings.WORKSPACE_PATH:
            WORKSPACE_PATH = settings.WORKSPACE_PATH
        else:
            WORKSPACE_PATH = settings.BASE_DIR
        WORKSPACE_PATH = os.path.join(WORKSPACE_PATH, 'settings')

        if self.options['silent']:
            sys.stdout = open(os.devnull, 'w')
            sys.sterr = open(os.devnull, 'w')

        # Get this Django Project's WSGI Application and mount it
        application = get_internal_wsgi_application()
        cherrypy.tree.graft(application, "/")

        # Unsubscribe the default server
        cherrypy.server.unsubscribe()

        # Instantiate a new server
        server = cherrypy._cpserver.Server()

        # Configure the server
        server.socket_host = self.options['host']
        server.socket_port = self.options['app_port']
        server.thread_pool = 30

        server.max_request_body_size = 10737412742

        # For SSL Support
        # server.ssl_module = 'pyopenssl'
        # server.ssl_certificate = 'ssl/certificate.crt'
        # server.ssl_private_key = 'ssl/private.key'
        # server.ssl_certificate_chain = 'ssl/bundle.crt

        # Subscribe the new server
        server.subscribe()

        # Get the DJANGO_BASE nginx conf file and copy it to the running project's base dir as nginx.conf.
        # Startup nginx with a passed in conf file of the one in the project's base dir.
        # nginx -c settings.BASE_DIR/nginx.conf
        if not os.path.exists(os.path.join(WORKSPACE_PATH, 'nginx', 'conf')):
            os.makedirs(os.path.join(WORKSPACE_PATH, 'nginx', 'conf'))
        if not os.path.exists(os.path.join(WORKSPACE_PATH, 'nginx', 'logs')):
            os.makedirs(os.path.join(WORKSPACE_PATH, 'nginx', 'logs'))
        if not os.path.exists(os.path.join(WORKSPACE_PATH, 'nginx', 'temp')):
            os.makedirs(os.path.join(WORKSPACE_PATH, 'nginx', 'temp'))

        if os.path.isfile(os.path.join(WORKSPACE_PATH, 'nginx', 'conf', 'nginx.conf')):
            os.remove(os.path.join(WORKSPACE_PATH, 'nginx', 'conf', 'nginx.conf'))

        shutil.copyfile(os.path.join(self.PRODUCTIONSERVER_DIR, 'nginx', 'conf', 'nginx.conf.DJANGO_BASE'), os.path.join(WORKSPACE_PATH, 'nginx', 'conf', 'nginx.conf'))
        self.replace_text_in_file(os.path.join(WORKSPACE_PATH, 'nginx', 'conf', 'nginx.conf'),
                                  [('%%APP_PORT%%', str(self.options['app_port'])),
                                   ('%%SERVER_PORT%%', str(self.options['port'])),
                                   ('%%STATIC_FILE_DIR%%', settings.STATIC_ROOT),
                                   ('%%BASE_DIR%%', settings.BASE_DIR),
                                   ('%%WORKSPACE_PATH%%', WORKSPACE_PATH),
                                   ('%%PRODUCTIONSERVER_DIR%%', self.PRODUCTIONSERVER_DIR),
                                   ('%%HOST%%', self.options['host'])])

        launch_args = {}
        if self.options['silent']:
            launch_args['stdout'] = subprocess.DEVNULL
            launch_args['stderr'] = subprocess.DEVNULL

            if not os.path.exists(os.path.join(WORKSPACE_PATH, 'logs')):
                os.makedirs(os.path.join(WORKSPACE_PATH, 'logs'))

            output_log = os.path.join(WORKSPACE_PATH, 'logs', 'server_output.log')
            error_log = os.path.join(WORKSPACE_PATH, 'logs', 'server_error.log')

            if os.path.isfile(output_log) and os.stat(output_log).st_size > 10000000:
                os.remove(output_log)
            if os.path.isfile(error_log) and os.stat(error_log).st_size > 10000000:
                os.remove(error_log)

            with open(output_log, 'a') as log:
                log.write("STARTING AT: %s" % now())
                log.close()
            with open(error_log, 'a') as log:
                log.write("STARTING AT: %s" % now())
                log.close()

            cherrypy.log.screen = False
            cherrypy.log.access_file = output_log
            cherrypy.log.error_file = error_log

        nginx = subprocess.Popen([os.path.join(self.PRODUCTIONSERVER_DIR, 'nginx', 'nginx.exe'), "-c", os.path.join(WORKSPACE_PATH, 'nginx', 'conf', 'nginx.conf'), "-p",  os.path.join(WORKSPACE_PATH, 'nginx')], **launch_args)

        cherrypy.engine.start()
        #cherrypy.engine.block()  # I would like to use this as it listens to other CherryPy bad states. However, it causes the application to not catch the system close call correctly

        try:
            while(True):
                sleep(.1)
        except (KeyboardInterrupt, IOError, SystemExit) as e:
            try:
                print("Attempting to shutdown the server...")
                cherrypy.engine.exit()  # Need to call this first since we aren't blocking above
                nginx.kill()
                print("Server shutdown.")
            except:
                print("Failed to shutdown server! Please press 'Ctrl+c.'")

    @staticmethod
    def replace_text_in_file(file_path, replacements=None):
        if not replacements:
            replacements = [(), ]

        fh, abs_path = mkstemp()

        new_file = open(abs_path, 'w')
        old_file = open(file_path, 'r')

        for line in old_file:
            new_line = line
            for replacement in replacements:
                new_line = new_line.replace(replacement[0], replacement[1])
            new_file.write(new_line.replace('\\', '/'))

        new_file.close()
        os.close(fh)
        old_file.close()

        os.remove(file_path)
        shutil.move(abs_path, file_path)