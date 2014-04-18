#!/bin/bash
{
cd $2
python $1/manage.py runproductionserver --host=$3 --port=$4 --server_name=$5 --threads=$6 --screen=False --ssl_certificate=$7 --ssl_private_key=$8 --auto_reload=$9 --collectstatic=${10} --serve_static${11}
}