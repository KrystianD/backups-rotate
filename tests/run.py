import os, time, datetime, sys

os.system ("mkdir -p test_backups test_dir")
os.system ("touch test_dir/file_to_backup")
os.system ("rm -f test_backups/*")

i = 0
while True:
    bd =  "--basedate \""+(datetime.datetime (2015, 8, 2) + datetime.timedelta (days=i)).strftime ("%Y-%m-%d")+"\""
    os.system ("python ../backups_rotate.py --force --config test.cfg {0} > /dev/null".format(bd))
    os.system ("python show_cal.py --config test.cfg {0}".format(bd))
    i += 1
    sys.stdin.read(1)
