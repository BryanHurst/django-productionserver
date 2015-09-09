#!/bin/bash
# Download the nginx source you want to compile, put this script into that folder and run it.

sudo apt-get update
sudo apt-get install build-essential gcc g++ openssl libssl-dev libperl-dev

wget ftp://ftp.csx.cam.ac.uk/pub/software/programming/pcre/pcre-8.37.tar.gz
wget http://zlib.net/zlib-1.2.8.tar.gz
gzip -d pcre-8.37.tar.gz
gzip -d zlib-1.2.8.tar.gz
tar -xvf pcre-8.37.tar
tar -xvf zlib-1.2.8.tar

cd pcre-8.37
./configure --prefix=/usr --enable-unicode-properties
make
sudo make install
cd ..

cd zlib-1.2.8
./configure
make
sudo make install
cd ..

./configure --prefix=. --sbin-path=nginx --conf-path=conf/nginx.conf --error-log-path=logs/error.log --pid-path=nginx.pid --http-client-body-temp-path=tmp/client_body_temp/ --http-proxy-temp-path=tmp/proxy_temp/ --http-fastcgi-temp-path=tmp/fastcgi_temp/ --http-uwsgi-temp-path=tmp/uwsgi_temp/ --http-scgi-temp-path=tmp/scgi_temp/ --with-ipv6 --with-http_ssl_module --with-http_gzip_static_module --with-http_stub_status_module --without-mail_pop3_module --without-mail_imap_module --without-mail_smtp_module --without-http_fastcgi_module --with-pcre=pcre-8.37 --with-zlib=zlib-1.2.8

make build && make install

echo "There should be errors about conf files being the same."

make clean

rm pcre-8.37.tar
rm -r pcre-8.37/
rm zlib-1.2.8.tar
rm -r zlib-1.2.8/

rm -r auto objs src CHANGES CHANGES.ru configure LICENSE README
