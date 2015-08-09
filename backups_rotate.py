import os, sys, argparse, time, subprocess, configparser, shutil
from datetime import datetime, timedelta
import utils, report

report.init()

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--force", action='store_true')
parser.add_argument("--basedate")
args = parser.parse_args()

config = configparser.ConfigParser()
config.read(args.config)

name = utils.get_option('backup', config, 'name')
src_dir = utils.get_option('backup', config, 'src')
do_compress = utils.get_option('backup', config, 'compress')
cpu_limit = utils.get_option('backup', config, 'cpu_limit')
interval = utils.get_interval_from_str(utils.get_option('backup', config, 'interval'))
check = utils.get_option('backup', config, 'check')

dest_dir = utils.get_option('rotate', config, 'dest')
delete_older_than = utils.get_option('rotate', config, 'delete_older_than')
clean_day_parts = utils.get_option('rotate', config, 'clean_day_parts')
delete_prefix = utils.get_option('rotate', config, 'delete_prefix')

task_backup = src_dir is not None

base_date = datetime.now()
if args.basedate:
    base_date = datetime.strptime(args.basedate, "%Y-%m-%d")

def main():
    global src_dir, dest_dir, interval

    if delete_older_than is not None and clean_day_parts is not None:
        utils.log(utils.LOG_ERROR, "backup", "specify one of delete_older_than or clean_day_parts".format(src_dir))
        sys.exit(1)

    dest_dir = dest_dir.rstrip("/") + "/"

    if task_backup:
        src_dir = src_dir.rstrip("/") + "/"

        if name is None:
            utils.log(utils.LOG_ERROR, "backup", "name must be specified".format(src_dir))
            sys.exit(1)
        if interval is None:
            utils.log(utils.LOG_ERROR, "backup", "interval must be specified".format(src_dir))
            sys.exit(1)

        if not os.path.isabs(src_dir):
            utils.log(utils.LOG_ERROR, "backup", "Source directory - path must be absolute: {0}".format(src_dir))
            sys.exit(1)
        if not os.path.exists(src_dir):
            utils.log(utils.LOG_ERROR, "backup", "Source directory doesn't exist: {0}".format(src_dir))
            sys.exit(1)

        interval = timedelta(seconds=interval)

    if not os.path.isabs(dest_dir):
        utils.log(utils.LOG_ERROR, "backup", "Destination directory - path must be absolute: {0}".format(src_dir))
        sys.exit(1)
    if not os.path.exists(dest_dir):
        utils.log(utils.LOG_ERROR, "backup", "Destination directory doesn't exist: {0}".format(dest_dir))
        sys.exit(1)

    last_date = utils.get_last_date_in_dir(dest_dir)
    report.log("Last backup date: {0}".format(last_date))

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
            report.log("Rotate needed")
            do_backup()

    do_rotate()

def do_backup():
    dest_file_name = base_date.strftime("%Y-%m-%d_%H%M")
    dest_file_name += "_" + name

    dest_path = dest_dir + dest_file_name

    if do_compress in ['gzip', 'store']:
        ext = {'gzip': 'tgz', 'store': 'tar'}[do_compress]

        dest_path_compressed = dest_dir + dest_file_name + "." + ext
        if os.path.exists(dest_path_compressed):
            utils.log(utils.LOG_WARN, "backup", "Destination file exists {0}".format(dest_path_compressed))
            return

        dest_path_compressed_tmp = dest_path_compressed + ".tmp"

        utils.log(utils.LOG_INFO, "backup", "Changing directory to {0}".format(src_dir))
        os.chdir(src_dir)

        utils.log(utils.LOG_INFO, "backup", "Creating archive {0} to {1}...".format(src_dir, dest_path_compressed_tmp))
        args = ['tar']
        args.append('--create')
        if do_compress == 'gzip':
            args.append('--gzip')
        args.append('--file')
        args.append(dest_path_compressed_tmp)
        args.append('.')

        report.log_command(" ".join(args))
        process = subprocess.Popen(args)
        if cpu_limit:
            limit_cmd = "cpulimit --lazy --include-children --pid={0} --limit={1}".format(process.pid, cpu_limit)
            report.log_command(limit_cmd)
            processLimit = subprocess.Popen(limit_cmd, shell=True)
            r = process.wait()
            processLimit.wait()
        else:
            r = process.wait()

        if r == 0:
            utils.log(utils.LOG_INFO, "backup", "Copying {0} to {1}".format(dest_path_compressed_tmp, dest_path_compressed))
            os.rename(dest_path_compressed_tmp, dest_path_compressed)
    else:
        if os.path.exists(dest_path):
            utils.log(utils.LOG_WARN, "backup", "Destination folder exists {0}".format(dest_path))
            return

        dest_path_tmp = dest_path + "_tmp"
        utils.log(utils.LOG_INFO, "backup", "Copying {0} to {1}...".format(src_dir, dest_path_tmp))
        try:
            if os.path.exists(dest_path_tmp):
                shutil.rmtree(dest_path_tmp)
            shutil.copytree(src_dir, dest_path_tmp)
            os.rename(dest_path_tmp, dest_path)
        except Exception as err:
            utils.log(utils.LOG_WARN, "backup", err)

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
        files_to_keep = []
        for p in parts:
            if p["file_to_keep"] is not None:
                files_to_keep.append(p["file_to_keep"])
            print("[" + str(p["from"]) + ", " + str(p["to"]) + "] file: " + str(p["file_to_keep"]))

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
    print('del', filename)

    if delete_prefix:
        new_filename = delete_prefix + filename
        utils.log(utils.LOG_INFO, "backup", "Renaming {0} to {1}...".format(filename, new_filename))
        dest_path = dest_dir + filename
        new_dest_path = dest_dir + new_filename
        os.rename(dest_path, new_dest_path)
    else:
        utils.log(utils.LOG_INFO, "backup", "Deleting {0}...".format(filename))
        dest_path = dest_dir + filename
        if os.path.isfile(dest_path):
            os.remove(dest_path)
        elif os.path.isdir(dest_path):
            shutil.rmtree(dest_path)

main()

# print(config.get("rotate", "src_dir"))
# print(config.getboolean("rotate", "zip"))
# print(config.options("rotate"))
