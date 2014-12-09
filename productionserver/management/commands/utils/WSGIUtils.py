import os
import stat
import mimetypes
from django.utils.http import http_date
from django.http import HttpResponseNotModified, HttpResponseNotFound, HttpResponseNotAllowed, HttpResponse


class HttpResponseUnAuthorized(HttpResponse):
    status_code = 401


class BlockIteratorResponse(object):
    """
    I looked into the proper way to send static files, and it is agreed that it is more efficient to split files up
    before sending.
    Chunks, just like in Skittle, are created from each file and formed into the end "response".
    This is good for network efficiency.
    Unlike Skittle though, we are doing this on the fly. We have to read the file from the disk to transmit any ways,
    so chunk it up with in iter and there is no performance loss during reading.
    """
    def __init__(self, fp):
        self.fp = fp

    def __iter__(self):
        return self

    def __next__(self):
        chunk = self.fp.read(20*1024)
        if chunk:
            return chunk
        self.fp.close()
        raise StopIteration

    def next(self):
        return self.__next__()

class StaticFileWSGIApplication(object):
    """
    CherryPy does serving based off of apps, kind of like Django.
    Our problem is that we are just using the HTTP server part of CherryPy and not serving CherryPy applications.

    We serve the Django python code by sending Django's WSGIApplication to CherryPy as an app.

    BUT we want to serve static files too, which Django's WSGIApplication doesn't handle.
    So we need to setup an "app" for static files.
    When serving collected static, this will just be one app for the root /static/ folder.
    When serving static files from each application, there will be a different StaticFilesApp for each Django App.
    """
    logger = None

    def __init__(self, static_file_root, logger):
        self.static_file_root = os.path.normpath(static_file_root)
        self.logger = logger

    def __call__(self, environ, start_response):
        """
        I was confused about this magic method at first. It makes instances of your class callable.

        class MyClass()
        foo = MyClass()

        Then the __call__ method in MyClass allows you to do
        foo() in your code and have it execute the class.

        I needed to use this, because CherryPy's dispatcher takes classes (apps)
        that it then calls when a request comes in.
        When CherryPy calls the app, it sends in the app's context (or environ)
        and what is essentially a callback method for us to start sending our final response to the client that requested it.
        """
        def done(response, output=None):
            # self.logger.debug('Done from self.static_file_root: %s' % self.static_file_root, response.status_code, response.items())
            start_response(str(response.status_code), response.items())
            return output or response

        path_info = environ['PATH_INFO']
        if path_info[0] == '/':
            path_info = path_info[1:]
        file_path = os.path.normpath(os.path.join(self.static_file_root, path_info))

        # prevent escaping out of paths above our static root (e.g. via "..")
        if not file_path.startswith(self.static_file_root):
            self.logger("%s: Attempted to access UnAuthorized Area! %s" % (environ['REMOTE_ADDR'], file_path))
            return done(HttpResponseUnAuthorized())

        # only allow GET or HEAD requests e.g. not PUT, DELETE, POST, etc.
        if not (environ['REQUEST_METHOD'] == 'GET' or environ['REQUEST_METHOD'] == 'HEAD'):
            self.logger("%s: Attempted to use HTTP Method that is Not Allowed! %s %s" % (environ['REMOTE_ADDR'], environ['REQUEST_METHOD'], environ['REQUEST_URI']))
            return done(HttpResponseNotAllowed(['GET', 'HEAD']))

        if not os.path.exists(file_path):
            self.logger.debug('%s: %s 404' % (environ['REMOTE_ADDR'], environ['REQUEST_URI']))
            return done(HttpResponseNotFound())

        try:
            fp = open(file_path, 'rb')
        except IOError:
            self.logger("%s: Attempted to access UnAuthorized File! %s" % (environ['REMOTE_ADDR'], file_path))
            return done(HttpResponseUnAuthorized())
       
        # Static files are marked with last modified times so the client does some caching.
        # the time needs to be in ascii for the client, but django does everything in unicode
        # but django has made a nice function to help with this!
        modified_time = http_date(os.stat(file_path)[stat.ST_MTIME]).encode('ascii', 'ignore')
        if environ.get('HTTP_IF_MODIFIED_SINCE', None) == modified_time:
            self.logger.debug('%s: %s 304' % (environ['REMOTE_ADDR'], environ['REQUEST_URI']))
            return done(HttpResponseNotModified())
        else:
            response = HttpResponse(content_type=mimetypes.guess_type(file_path)[0], status=200)
            response['Last-Modified'] = modified_time
            output = BlockIteratorResponse(fp)
            return done(response, output)


class WSGIRequestLoggerMiddleware(object):
    """
    A WSGI middle ware to printout/log the requests and response codes
    """
    wsgiapp = None
    logger = None

    def __init__(self, app, logger):
        self.wsgiapp = app
        self.logger = logger

    def __call__(self, environ, start_response):
        output = self.wsgiapp(environ, start_response)
        if hasattr(output, 'status_code'):
            self.logger.info("%s: [%s] %s %s" % (environ['REMOTE_ADDR'], environ['REQUEST_METHOD'], environ['REQUEST_URI'], output.status_code))
        else:
            self.logger.info("%s: [%s] %s" % (environ['REMOTE_ADDR'], environ['REQUEST_METHOD'], environ['REQUEST_URI']))
        return output