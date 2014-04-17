import sys
import os
import signal
import time
import errno
import logging
if os.name == 'posix':
    import pwd
    import grp

from datetime import datetime

from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.core.management.base import BaseCommand

from optparse import make_option

from cherrypy.wsgiserver import CherryPyWSGIServer, WSGIPathInfoDispatcher
from utils.WSGIUtils import StaticFileWSGIApplication


class Command(BaseCommand):
    help = r"""Run the Django project using CherryPy as the server.
    Taking place of the 'manage.py runserver', which is for development purposes only, this is suitable for small to medium server deployments.

    CherryPy (http://www.cherrypy.org) is required.

    Examples:
        Run a simple server suitable for testing
            $ manage.py runproductionserver

        TODO: Probably need some more examples
    """
    args = "[--option=value, use `runproductionserver help` for help]"

    logger = None
    options = None

    option_list = BaseCommand.option_list + (
        make_option('--host',
                    action='store_true',
                    dest='host',
                    default='0.0.0.0',
                    help='Adapter to listen on. Default is 0.0.0.0'),
        make_option('--port',
                    action='store_true',
                    dest='port',
                    default=8080,
                    help='Port to listen on. Default is 8080. Note, port 80 requires root access'),
        make_option('--server_name',
                    action='store_true',
                    dest='server_name',
                    default='Django Server',
                    help="CherryPy's server_name. Defaults to 'Django Server'"),
        make_option('--threads',
                    action='store_true',
                    dest='threads',
                    default=20,
                    help='Number of threads for server to use'),
        make_option('--screen',
                    action='store_true',
                    dest='screen',
                    default=False,
                    help='Whether to run the server in a screen. Defaults to False. Runs as daemon in Windows'),
        make_option('--working_directory',
                    action='store_true',
                    dest='working_directory',
                    default=settings.BASE_DIR,
                    help='Directory to set as working directory when in screen. Defaults to BASE_DIR'),
        make_option('--pid_file',
                    action='store_true',
                    dest='pid_file',
                    default=settings.BASE_DIR + '/server_8080.pid',
                    help="Write the spawned screen's id to this file. Defaults to BASE_DIR/server_PORT.pid"),
        make_option('--server_user',
                    action='store_true',
                    dest='server_user',
                    default='www-data',
                    help="System user to run the server under. Defaults to www-data. Not available in Windows"),
        make_option('--server_group',
                    action='store_true',
                    dest='server_group',
                    default='www-data',
                    help="System Group to run server under. Defaults to www-data. Not available in Windows"),
        make_option('--ssl_certificate',
                    action='store_true',
                    dest='ssl_certificate',
                    default=None,
                    help="SSL Certificate file"),
        make_option('--ssl_private_key',
                    action='store_true',
                    dest='ssl_private_key',
                    default=None,
                    help="SSL Private Key file"),
        make_option('--auto_reload',
                    action='store_true',
                    dest='auto_reload',
                    default=False,
                    help="Automatically reload the server upon code changes"),
        make_option('--serve_static',
                    action='store_true',
                    dest='serve_static',
                    default='app',
                    help="--server_static=app|collect|none\n "
                         "Serve static files directly from each app's static file folders (good for development [default]),\n"
                         "from the collected static directory at STATIC_ROOT (good for production),\n"
                         "or don't serve static files at all (not good)"),
        make_option('--stop',
                    action='store_true',
                    dest='stop',
                    default=False,
                    help="Stop a currently running server either in a screen or daemon. "
                         "Must define pid_file or want to kill the server running from the default pid_file location"),
    )

    def handle(self, *args, **options):
        self.options = options

        if self.options['stop']:
            try:
                return self.stop_server(self.options['pid_file'])
            except Exception as e:
                print e
                return False
        else:
            self.logger = logging.getLogger(self.options['server_name'])
            self.logger.setLevel(logging.WARNING)
            self.logger.addHandler(logging.StreamHandler())

            if '8080.pid' in options['pid_file'] and options['port'] != 8080:
                options['pid_file'].replace('8080', options['port'])
            return self.runproductionserver()

    def runproductionserver(self):
        if self.options['screen']:
            if os.path.exists(self.options['pid_file']):
                raise RuntimeError("There is already a server running with this pid_file configuration! "
                                   "Run 'manage.py stop' to clean it up.")

            # I haven't figured out how to detect a screen crash to auto reload yet
            self.options['auto_reload'] = False

            if os.name != 'posix':
                # Windows doesn't have screen, so we will use Django's daemonize function
                from django.utils.daemonize import become_daemon
                become_daemon(our_home_dir=self.options['working_directory'])

                fp = open(self.options['pid_file'], 'w')
                fp.write("%d\n" % os.getpid())
                fp.close()

                logging.info('Starting server in background process with options:\n%s' % self.options)

                try:
                    self.start_server()
                except Exception as e:
                    logging.info(e)
            else:
                # Launch a screen
                script_path = os.path.dirname(os.path.realpath(__file__)) + '/utils/run_screen.sh'

                import subprocess
                subprocess.call("screen -dmS %s %s %s %s %s %s %s %s %s %s %s %s %s" % (self.options['server_name'],
                                                                                     script_path,
                                                                                     settings.BASE_DIR,
                                                                                     self.options['working_directory'],
                                                                                     self.options['host'],
                                                                                     self.options['port'],
                                                                                     self.options['server_name'],
                                                                                     self.options['threads'],
                                                                                     self.options['ssl_certificate'],
                                                                                     self.options['ssl_private_key'],
                                                                                     self.options['auto_reload'],
                                                                                     self.options['collectstatic'],
                                                                                     self.options['serve_static']),
                                shell=True)
                pid = subprocess.check_output("screen -ls | aqk '/\\.%s\\t/ {print strtonum($1)}"
                                              % self.options['server_name'],
                                              shell=True)
                f = open(self.options['pid_file'], 'w')
                f.write("%d\n" % pid)
                f.close()
                logging.info("Starting server in screen %s with options:\n%s" % (self.options['server_name'], self.options))
                return True
        elif self.options['auto_reload']:
            # Running auto reloading server in the current console
            import django.utils.autoreload
            logging.info('Starting auto reloading server with options:\n%s' % self.options)
            try:
                django.utils.autoreload.main(self.start_server)
                return True
            except Exception as e:
                logging.info(e)
                return False
        else:
            # Running normal server in the current console
            logging.info('Starting server with options:\n%s' % self.options)
            try:
                return self.start_server()
            except Exception as e:
                logging.info(e)
                return False

    def start_server(self):
        """
        Note on SSL:
        The new way in CherryPy is to just set server.ssl_adapter to an SSLAdapter instance.
        The old, deprecated way is to set server.ssl_certificate and server.ssl_private_key:

        The new way is complicated, especially through this command line thingy.
        So for now, I'm using the deprecated way.
        """
        self.stdout.write("Validating models...")
        self.validate(display_num_errors=True)
        self.stdout.write("%s\nDjango version: %s, using Settings: %r\n"
                          "CherryPy Production Server is running at http://%s:%s/\n"
                          "Quit the server with Ctrl-C\n"
                          % (datetime.now().strftime('%B %d, %Y - %X'),
                             self.get_version(),
                             settings.SETTINGS_MODULE,
                             self.options['host'],
                             self.options['port']))

        self.logger.info("Launching CherryPy with the following options:\n%s" % self.options)
        if int(self.options['verbosity']) >= 2:
            self.stdout.write("Launching with the following options:\n%s" % self.options)

        if self.options['screen']:
            #When not in windows, change the running user and group
            if os.name == 'posix':
                self.change_uid_gid(self.options['server_user'], self.options['server_group'])

        # This will serve django code
        app = WSGIHandler()

        # There are two ways for static files to be served
        # 1. When in development, you may want to serve static files directly from each app's static file folder.
        #       This is what the normal 'manage.py runserver' does, and why you don't need to collectstatic while testing
        # 2. In production, you collect all the installed apps static files into one location (single folder, or CDN)
        #       using 'manage.py collectstatic'. You run this every time you change any app's static files and deploy.
        path = {'/': app}
        static_type = self.options['serve_static'].lower()
        if static_type != "none":
            if static_type != "app" and static_type != "collect":
                raise ValueError("Type of static serving must be app|collect|none!")
            try:
                if not settings.STATIC_URL:
                    # could use misconfigured exception (what is this in django?) instead of AttributeError
                    raise AttributeError("settings.STATIC_URL = %s" % repr(settings.STATIC_URL))
            except AttributeError as e:
                self.logger.error(e)
                self.logger.error("****")
                self.logger.error("STATIC_URL must be set in settings file when using static files!")
                self.logger.error("****")
                raise

            # Used to route static file requests through the WSGI Server.
            if static_type == 'app':
                # find all install apps static files and add them to the path
                if settings.STATICFILES_FINDERS:
                    self.logger.debug("Settings.STATICFILES_FINDERS:\n%s" % settings.STATICFILES_FINDERS)

                    from django.contrib.staticfiles.finders import AppDirectoriesFinder

                    app_static_finder = AppDirectoriesFinder(settings.INSTALLED_APPS)
                    self.logger.debug("app_static_finder.storages:\n%s" % app_static_finder.storages)
                    for key, val in app_static_finder.storages.items():
                        self.logger.debug(key, " static location:", val.location)
                        app_url = key.split('.')[-1] + r'/'
                        full_static_url = os.path.join(settings.STATIC_URL, app_url)
                        full_dir_location = os.path.join(val.location, app_url)
                        self.logger.debug(full_static_url, full_dir_location)
                        path[full_static_url] = StaticFileWSGIApplication(full_dir_location, self.logger)

                # Don't forget to also log other user defined static file locations
                if hasattr(settings, 'STATICFILES_DIRS'):
                    staticlocations = self.process_staticfiles_dirs(settings.STATICFILES_DIRS)
                    self.logger.debug("staticlocations:\n%s" % staticlocations)
                    for urlprefix, root in staticlocations:
                        path[os.path.join(settings.STATIC_URL, urlprefix)] = StaticFileWSGIApplication(root, self.logger)

            if static_type == 'collect':
                # only serve the top level static root folder
                path[settings.STATIC_URL] = StaticFileWSGIApplication(settings.STATIC_ROOT, self.logger)
                self.logger.warning("Serving all static files from %s.\n"
                                    "*** Make sure you have done a fresh 'manage.py collectstatic' operation! ***"
                                    % settings.STATIC_ROOT)

        # Setup router to intercept URLs and send to correct StaticFileWSGIApplication
        self.logger.debug("path: %s" % path)
        dispatcher = WSGIPathInfoDispatcher(path)
        self.logger.debug("apps: %s" % dispatcher.apps)

        if self.options['verbosity'] >= 1:
            from utils.WSGIUtils import WSGIRequestLoggerMiddleware
            dispatcher = WSGIRequestLoggerMiddleware(dispatcher, self.logger)

            if self.options['verbosity'] >= 2:
                self.logger.setLevel(logging.INFO)
            else:
                self.logger.setLevel(10)

        server = CherryPyWSGIServer(
            (self.options['host'], int(self.options['port'])),
            dispatcher,
            int(self.options['threads']),
            self.options['server_name']
        )
        if self.options['ssl_certificate'] and self.options['ssl_private_key']:
            if sys.version_info < (3, 0):
                import cherrypy.wsgiserver.wsgiserver2 as wsgiserver
            else:
                import cherrypy.wsgiserver.wsgiserver3 as wsgiserver
            Adapter = wsgiserver.get_ssl_adapter_class()
            try:
                server.ssl_adapter = Adapter(certificate=self.options['ssl_certificate'],
                                            private_key=self.options['ssl_private_key'])
            except ImportError:
                pass
            try:
                Adapter = wsgiserver.get_ssl_adapter_class('builtin')
                server.ssl_adapter = Adapter(certificate=self.options['ssl_certificate'],
                                             private_key=self.options['ssl_private_key'])
            except ImportError:
                Adapter = None
                raise
        try:
            server.start()
        except KeyboardInterrupt:
            server.stop()

    @staticmethod
    def stop_server(pidfile):
        """
        Stop process whose pid was written to supplied pidfile.
        First try SIGTERM and if it fails, SIGKILL. If process is still running, an exception is raised.
        """
        def poll_process(pid):
            """
            Poll for process with given pid up to 10 times waiting .25 seconds in between each poll.
            Returns False if the process no longer exists otherwise, True.
            """
            for n in range(10):
                time.sleep(0.25)
                try:
                    # poll the process state
                    os.kill(pid, 0)
                except OSError, e:
                    if e[0] == errno.ESRCH:
                        # process has died
                        return False
                    else:
                        raise Exception
            return True

        if os.path.exists(pidfile):
            pid = int(open(pidfile).read())
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:  # process does not exist
                os.remove(pidfile)
                return
            if poll_process(pid):
                if os.name != "posix":
                    raise OSError("Process %s did not stop!" % pid)
                # process didn't exit cleanly, make one last effort to kill it
                os.kill(pid, signal.SIGKILL)
                #if still_alive(pid):
                if poll_process(pid):
                    raise OSError("Process %s did not stop!" % pid)
            os.remove(pidfile)

    def change_uid_gid(self, uid, gid=None):
        """Try to change UID and GID to the provided values.
        UID and GID are given as names like 'nobody' not integer.

        Src: http://mail.mems-exchange.org/durusmail/quixote-users/4940/1/
        """
        if not os.geteuid() == 0:
            # Do not try to change the gid/uid if not root.
            return
        (uid, gid) = self.get_uid_gid(uid, gid)
        os.setgid(gid)
        os.setuid(uid)

    @staticmethod
    def get_uid_gid(uid, gid=None):
        """Try to change UID and GID to the provided values.
        UID and GID are given as names like 'nobody' not integer.

        Src: http://mail.mems-exchange.org/durusmail/quixote-users/4940/1/
        """
        uid, default_grp = pwd.getpwnam(uid)[2:4]
        if gid is None:
            gid = default_grp
        else:
            try:
                gid = grp.getgrnam(gid)[2]
            except KeyError:
                gid = default_grp
        return (uid, gid)

    @staticmethod
    def process_staticfiles_dirs(staticfiles_dirs, default_prefix='/'): # settings.STATIC_URL
        """
        normalizes all elements of STATICFILES_DIRS to be of ('prefix','/root/path/to/files') form
        the prefix gets added after STATIC_URL
        """
        staticlocations=[]
        for staticdir in staticfiles_dirs:
            # elements of staticfiles_dirs are ether simple path strings like "/var/www/polls/static"
            # or are tuples/
            if isinstance(staticdir, (list, tuple)):
                prefix, root = staticdir
                root = os.path.abspath(root)
            else:
                # default url prefix used for single path elements
                root = os.path.abspath(staticdir)
                prefix = os.path.join(default_prefix, os.path.basename(root))+r'/' # end with /

            staticlocations.append((prefix, root))
        return staticlocations