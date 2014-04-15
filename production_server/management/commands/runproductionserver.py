import os
if os.name == 'posix':
    import pwd
    import grp
import signal
import time
import errno

from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler

from cherrypy.wsgiserver import CherryPyWSGIServer as Server


class Command(BaseCommand):
    help = "Run the Django project using CherryPy as the server.\nTaking place of the 'manage.py runserver', " \
           "which is for development purposes only, this is suitable for small to medium server deployments.\n\n" \
           "CherryPy (http://www.cherrypy.org) is required."
    args = "[--option=value, use `runproductionserver help` for help]"

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
        make_option('--stop',
                    action='store_true',
                    dest='stop',
                    default=False,
                    help="Stop a currently running server either in a screen or daemon. "
                         "Must define pid_file or want to kill the server running from the default pid_file location."),
    )

    def handle(self, *args, **options):
        if options['stop']:
            try:
                return stop_server(options['pid_file'])
            except Exception as e:
                print e
                return False
        else:
            if '8080.pid' in options['pid_file'] and options['port'] != 8080:
                options['pid_file'].replace('8080', options['port'])
            return runproductionserver(options)


def get_uid_gid(uid, gid=None):
    if os.name == 'posix':
        uid, default_grp = pwd.getpwnam(uid)[2:4]
        if gid is None:
            gid = default_grp
        else:
            try:
                gid = grp.getgrname(gid)[2]
            except KeyError:
                gid = default_grp
        return (uid, gid)
    else:
        return False


def change_uid_gid(uid, gid=None):
    if os.name == 'posix':
        if not os.geteuid() == 0:
            return False
        (uid, gid) = get_uid_gid(uid, gid)
        os.setgid(gid)
        os.setuid(uid)
        return True
    else:
        return True


def poll_process(pid):
    for n in range(10):
        time.sleep(0.25)
        try:
            os.kill(pid, 0)
        except OSError, e:
            if e[0] == errno.ESRCH:
                return False
            else:
                raise
    return True


def stop_server(pid_file):
    if os.path.exists(pid_file):
        pid = int(open(pid_file).read())
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            os.remove(pid_file)
            return False
        if poll_process(pid):
            if os.name != 'posix':
                raise OSError("Process %s did not stop." % pid)
            os.kill(pid, signal.SIGKILL)
            if poll_process(pid):
                raise OSError("Process %s did not stop." % pid)
        os.remove(pid_file)
        return True
    else:
        print "Could not find a running server!"
        return False


def start_server(options):
    if options['screen']:
        if not change_uid_gid(options['server_user'], options['server_group']):
            raise RuntimeError('Error changing user and group!')

    server = Server(
        (options['host'], int(options['port'])),
        WSGIHandler(),
        int(options['threads']),
        options['server_name']
    )
    if options['ssl_certificate'] and options['ssl_private_key']:
        server.ssl_certificate = options['ssl_certificate']
        server.ssl_private_key = options['ssl_private_key']
    try:
        server.start()
        return True
    except KeyboardInterrupt:
        server.stop()
        return True
    except:
        return False


def runproductionserver(options):
    if options['screen']:
        if os.path.exists(options['pid_file']):
            raise RuntimeError("It appears there is already a server running in the background, "
                               "or there is a rogue PID file. Please run `productionserver --stop` to clean up.")

        if os.name != 'posix':
            from django.utils.daemonize import become_daemon
            become_daemon(our_home_dir=options['working_directory'])
            f = open(options['pid_file'], 'w')
            f.write("%d\n" % os.getpid())
            f.close()
            print "Starting server with options %s" % options
            return start_server(options)
        else:
            script_path = os.path.dirname(os.path.realpath(__file__)) + '/utils/run_screen.sh'
            import subprocess
            subprocess.call("screen -dmS %s %s %s %s %s %s %s %s %s %s" % (options['server_name'],
                                                                           script_path,
                                                                           settings.BASE_DIR,
                                                                           options['working_directory'],
                                                                           options['host'],
                                                                           options['port'],
                                                                           options['server_name'],
                                                                           options['threads'],
                                                                           options['ssl_certificate'],
                                                                           options['ssl_private_key']), shell=True)
            pid = subprocess.check_output("screen -ls | awk '/\\.%s\\t/ {print strtonum($1)}" % options['server_name'], shell=True)
            f = open(options['pid_file'], 'w')
            f.write("%d\n" % pid)
            f.close()
            print "Starting server in screen %s with options %s" % (options['server_name'], options)
            return True
    else:
        print "Starting server with options host=%s, port=%s, threads=%s, server_name=%s, " \
              "ssl_certificate=%s, ssl_private_key=%s" \
              % (options['host'], options['port'], options['threads'], options['server_name'],
                 options['ssl_certificate'], options['ssl_private_key'])

        return start_server(options)