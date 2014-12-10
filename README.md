django-productionserver
=======================

Runs a Django project using CherryPy as the App Server and NGINX for the Static File Server. Taking place of the 'manage.py runserver', which is for development purposes only, this is suitable for small to medium server deployments.

v1.0.0:

Very limited release. 

This version only works on Windows as NGINX for different platforms isn't configured yet. There are very limited options currently as we just have host, port, and app port. More will come like thread and worker counts, ssl, process names, ability to run in the background, and more.

Currently you will get a warning when starting up about not having a log file, this is fine. You also cannot see streaming log info from NGINX yet; this will be in a future version.
