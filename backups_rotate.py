import os, sys, argparse, time, subprocess, configparser, shutil, select
from datetime import datetime, timedelta
import utils, mylog
import ago

mylog.init()

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--force", action='store_true')
parser.add_argument("--basedate")
args = parser.parse_args()

config = configparser.ConfigParser()
config.read(args.config)
mylog.set_config(config)

name = utils.get_option('backup', config, 'name')

src_dir = utils.get_option('backup', config, 'src')
do_compress = utils.get_option('backup', config, 'compress')
cpu_limit = utils.get_option('backup', config, 'cpu_limit')
interval = utils.get_interval_from_str(utils.get_option('backup', config, 'interval'))
check = utils.get_option('backup', config, 'check')

delete_older_than = utils.get_option('rotate', config, 'delete_older_than')
clean_day_parts = utils.get_option('rotate', config, 'clean_day_parts')
delete_prefix = utils.get_option('rotate', config, 'delete_prefix')

title = utils.get_option('global', config, 'title')
dest_dir = utils.get_option('global', config, 'dest')

if title is None:
    title = name
mylog.log_name(title)

task_backup = src_dir is not None

base_date = datetime.now()
if args.basedate:
    base_date = datetime.strptime(args.basedate, "%Y-%m-%d")

dest_file_name = base_date.strftime("%Y-%m-%d_%H%M%S_") + name

rpl = [
    ['DEST_FILENAME', dest_file_name],
    ['SRC_DIR', src_dir],
    ['DEST_DIR', dest_dir],
]
rpl = sorted(rpl, key=lambda x: -len(x[1]))

mylog.log_msg("Variables:")
mylog.log_state("<DEST_FILENAME> = {0}".format(dest_file_name))
mylog.log_state("      <SRC_DIR> = {0}".format(src_dir))
mylog.log_state("     <DEST_DIR> = {0}".format(dest_dir))

def cc(txt):
    for v in rpl:
        txt = txt.replace(v[1].rstrip('/'), "<{0}>".format(v[0]))
    return txt

class BackupException(Exception):
    output = None
    base_exc = None

    def __init__(self, msg, output = None, base_exc=None):
        super(BackupException, self).__init__(msg)
        self.output = output
        self.base_exc = base_exc
    
    def log(self):
        if self.output:
            log(self.output)
        if self.base_exc is not None:
            exc = traceback.format_exc() + "\nBase exception:\n" + str(self.base_exc)
        else:
            exc = traceback.format_exc()
        mylog.log(exc)
        if self.output:
            log_html("<span style='color: red''><pre>" + self.output + "\n" + exc + "</pre></span>")
        else:
            log_html("<span style='color: red''><pre>" + exc + "</pre></span>")

def main():
    global src_dir, dest_dir, interval

    if delete_older_than is not None and clean_day_parts is not None:
        raise BackupException.log_error("specify one of delete_older_than or clean_day_parts".format(src_dir))

    dest_dir = dest_dir.rstrip("/") + "/"

    if task_backup:
        src_dir = src_dir.rstrip("/") + "/"

        if name is None:
            raise BackupException("name must be specified".format(src_dir))
        if interval is None:
            raise BackupException("interval must be specified".format(src_dir))

        if not os.path.isabs(src_dir):
            raise BackupException("Source directory - path must be absolute: {0}".format(src_dir))
        if not os.path.exists(src_dir):
            raise BackupException("Source directory doesn't exist: {0}".format(src_dir))

        interval = timedelta(seconds=interval)

    if not os.path.isabs(dest_dir):
        raise BackupException("Destination directory - path must be absolute: {0}".format(src_dir))
    if not os.path.exists(dest_dir):
        raise BackupException("Destination directory doesn't exist: {0}".format(dest_dir))

    last_date = utils.get_last_date_in_dir(dest_dir)
    mylog.log_msg("Last backup date: {0}".format(last_date))

    if task_backup:
        rotate_needed = False

        if last_date is not None:
            if check == 'exact':
                diff = base_date - last_date
            elif check == 'daily':
                diff = base_date.date() - last_date.date()

            if diff >= interval:
                rotate_needed = True
        else:
            rotate_needed = True

        if rotate_needed or args.force:
            mylog.log_msg("Rotate needed")
            do_backup()

    do_rotate()

def do_backup():
    dest_path = dest_dir + dest_file_name

    if do_compress in ['gzip', 'store']:
        ext = {'gzip': 'tgz', 'store': 'tar'}[do_compress]

        dest_path_compressed = dest_dir + dest_file_name + "." + ext
        if os.path.exists(dest_path_compressed):
            mylog.log_warn("Destination file exists {0}".format(cc(dest_path_compressed)))
            return

        dest_path_compressed_tmp = dest_path_compressed + ".tmp"

        mylog.log_state("Changing directory to {0}".format(cc(src_dir)))
        os.chdir(src_dir)

        mylog.log_state("Creating archive {0} to {1}...".format(cc(src_dir), cc(dest_path_compressed_tmp)))
        args = ['tar']
        # args.append('--verbose')
        args.append('--create')
        if do_compress == 'gzip':
            args.append('--gzip')
        args.append('--file')
        args.append(dest_path_compressed_tmp)
        args.append('.')

        mylog.log_command(cc(" ".join(args)))
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if cpu_limit:
            limit_cmd = "cpulimit --lazy --include-children --pid={0} --limit={1}".format(process.pid, cpu_limit)
            mylog.log_command(limit_cmd)
            processLimit = subprocess.Popen(limit_cmd, shell=True)
            processLimit.wait()
        else:
            pass

        r = process.wait()
        tar_output = process.stdout.read()

        if r == 0:
            mylog.log_state("Copying {0} to {1}".format(cc(dest_path_compressed_tmp), cc(dest_path_compressed)))
            os.rename(dest_path_compressed_tmp, dest_path_compressed)
        else:
            raise BackupException("tar failed", tar_output)
    else:
        if os.path.exists(dest_path):
            mylog.log_warn("Destination folder exists {0}".format(cc(dest_path)))
            return

        dest_path_tmp = dest_path + "_tmp"
        mylog.log_state("Copying {0} to {1}...".format(cc(src_dir), cc(dest_path_tmp)))
        try:
            if os.path.exists(dest_path_tmp):
                shutil.rmtree(dest_path_tmp)
            shutil.copytree(src_dir, dest_path_tmp)
            os.rename(dest_path_tmp, dest_path)
        except Exception as err:
            mylog.log_warn(err)

def do_rotate():
    # rotating
    if delete_older_than is not None:
        interval = utils.get_interval_from_str(delete_older_than)

        for filename in os.listdir(dest_dir):
            if filename.endswith(".tmp"):
                continue
            date = utils.get_date_from_filename(filename)
            if date is None:
                continue

            if utils.get_date_diff_in_seconds(date, base_date) >= interval:
                delete_backup_file(filename)

    elif clean_day_parts:
        parts = []
        # extract parts from string
        cur_date = base_date.date()
        for p in clean_day_parts.split(","):
            days = int(p.strip())
            start_date = cur_date - timedelta(days - 1)
            end_date = cur_date
            cur_date = start_date - timedelta(1)
            parts.append({"from": start_date, "to": end_date, "file_to_keep": None})

        # assign files to parts
        for filename in os.listdir(dest_dir):
            if filename.endswith(".tmp"):
                continue
            date = utils.get_date_from_filename(filename)
            if date is None:
                continue
            date = date.date()

            for p in parts:
                if date >= p["from"] and date <= p["to"]:
                    if p["file_to_keep"] is None or utils.get_date_from_filename(p["file_to_keep"]).date() > date:
                        p["file_to_keep"] = filename

        # gather all files to keep
        mylog.log_msg("Current backups state")
        files_to_keep = []
        for p in parts:
            if p["file_to_keep"] is not None:
                files_to_keep.append(p["file_to_keep"])

                file_date = utils.get_date_from_filename(p["file_to_keep"])
                file_str = "{0[file_to_keep]} ({1})".format(p, ago.human(base_date - file_date))
            else:
                file_str = 'no file'

            mylog.log_state("[{0[from]}, {0[to]}] file: {1}".format(p, file_str))

        for filename in os.listdir(dest_dir):
            if filename.endswith(".tmp"):
                continue
            date = utils.get_date_from_filename(filename)
            if date is None:
                continue
            date = date.date()

            if not filename in files_to_keep:
                delete_backup_file(filename)

def delete_backup_file(filename):
    if delete_prefix:
        new_filename = delete_prefix + filename
        mylog.log_state("Renaming {0} to {1}...".format(cc(filename), cc(new_filename)))
        dest_path = dest_dir + filename
        new_dest_path = dest_dir + new_filename
        os.rename(dest_path, new_dest_path)
    else:
        mylog.log_state("Deleting {0}...".format(cc(filename)))
        dest_path = dest_dir + filename
        if os.path.isfile(dest_path):
            os.remove(dest_path)
        elif os.path.isdir(dest_path):
            shutil.rmtree(dest_path)

if __name__ == "__main__":
    try:
        main()
        code = 0
    except BackupException as e:
        e.log()
        code = 1

    mylog.send(code)
    exit(code)
