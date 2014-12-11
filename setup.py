from distutils.core import setup

setup(
    name='django-productionserver',
    version='1.0.0',
    packages=['productionserver', 'productionserver.management', 'productionserver.management.commands'],
    url='https://github.com/BryanHurst/django-productionserver',
    license='',
    author='Bryan Hurst',
    author_email='bryan@newline.us',
    description='Runs a Django Project using CherryPy as the App Server and nginx as the Static Asset Server.',
    requires=['futures', 'cherrypy', 'django']
)
