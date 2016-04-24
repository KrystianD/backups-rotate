import os, sys, argparse, time, subprocess, configparser, shutil, select, traceback
from datetime import datetime, timedelta
import utils, report
import ago, yaml

report.init()

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--force", action='store_true')
parser.add_argument("--basedate")
args = parser.parse_args()

config = yaml.load(open(args.config))

report.log_name(config['name'])

base_date = datetime.now()
if args.basedate:
    base_date = datetime.strptime(args.basedate, "%Y-%m-%d")

def ago_format(x):
    if x < timedelta(minutes=1):
        return "now"
    else:
        return ago.human(x)

class BackupException(Exception):
    output = None
    base_exc = None

    def __init__(self, msg, output = None, base_exc=None):
        super(BackupException, self).__init__(msg)
        self.output = output
        self.base_exc = base_exc
    
    def log(self):
        if self.output:
            report.log(self.output)
        if self.base_exc is not None:
            exc = traceback.format_exc() + "\nBase exception:\n" + str(self.base_exc)
        else:
            exc = traceback.format_exc()
        report.log_text(exc)
        if self.output:
            report.log_html("<span style='color: red''><pre>" + self.output + "\n" + exc + "</pre></span>")
        else:
            report.log_html("<span style='color: red''><pre>" + exc + "</pre></span>")

class Task:
    name = None

    dest_dir = None

    def __init__(self, config):
        self.dest_dir = config['dest']
        self.name = config['name']

        self.dest_dir = self.dest_dir.rstrip("/") + "/"

        if not os.path.isabs(self.dest_dir):
            raise BackupException("Destination directory - path must be absolute: {0}".format(self.dest_dir))
        if not os.path.exists(self.dest_dir):
            raise BackupException("Destination directory doesn't exist: {0}".format(self.dest_dir))

        # if self.name is None:
            # raise BackupException("name must be specified".format(self.src_dir))

    def cc(self, txt):
        for v in self.rpl:
            txt = txt.replace(v[1].rstrip('/'), "<{0}>".format(v[0]))
        return txt

    def process_vars(self, rpl):
        self.rpl = sorted(rpl, key=lambda x: -len(x[1]))
        report.log_msg("Variables:")
        for var in self.rpl:
            report.log_state("{0:>16s} = {1}".format("<{0}>".format(var[0]), var[1]))

class BackupTask(Task):
    interval = None

    src_dir = None
    do_compress = None
    cpu_limit = None
    check = None

    def __init__(self, config):
        super().__init__(config)

        self.interval = utils.get_interval_from_str(config['interval'])
        self.do_compress = config['compress']
        self.cpu_limit = config.get('cpu_limit')
        self.check = config['check']
        self.src_dir = config['src']

        if not os.path.isabs(self.src_dir):
            raise BackupException("Source directory - path must be absolute: {0}".format(self.src_dir))
        if not os.path.exists(self.src_dir):
            raise BackupException("Source directory doesn't exist: {0}".format(self.src_dir))

    def check_if_needed(self):
        last_date = utils.get_last_date_in_dir(self.dest_dir)
        report.log_msg("Last backup date: {0}".format(last_date))

        if last_date is None or args.force:
            return True

        if self.check == 'exact':
            diff = base_date - last_date
            report.log_msg("Checking exact: {0}".format(ago_format(diff)))
        elif self.check == 'daily':
            diff = base_date.date() - last_date.date()
            report.log_msg("Checking daily: {0}".format(ago_format(diff)))

        interval = timedelta(seconds=self.interval)
        return diff >= interval

    def perform(self):
        if not self.check_if_needed():
            return

        dest_file_name = base_date.strftime("%Y-%m-%d_%H%M%S_") + utils.get_valid_filename(self.name)

        self.process_vars([
            ['DEST_FILENAME', dest_file_name],
            ['SRC_DIR', self.src_dir],
            ['DEST_DIR', self.dest_dir],
        ])

        dest_path = self.dest_dir + dest_file_name

        if self.do_compress in ['gzip', 'store']:
            ext = {'gzip': 'tgz', 'store': 'tar'}[self.do_compress]

            dest_path_compressed = self.dest_dir + dest_file_name + "." + ext
            if os.path.exists(dest_path_compressed):
                report.log_warn("Destination file exists {0}".format(self.cc(dest_path_compressed)))
                return

            dest_path_compressed_tmp = dest_path_compressed + ".tmp"

            report.log_state("Changing directory to {0}".format(self.cc(self.src_dir)))
            os.chdir(self.src_dir)

            report.log_state("Creating archive {0} to {1}...".format(self.cc(self.src_dir), self.cc(dest_path_compressed_tmp)))
            args = ['tar']
            # args.append('--verbose')
            args.append('--create')
            if self.do_compress == 'gzip':
                args.append('--gzip')
            args.append('--file')
            args.append(dest_path_compressed_tmp)
            args.append('.')

            report.log_command(self.cc(" ".join(args)))
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            processLimit = None
            if self.cpu_limit:
                limit_cmd = "cpulimit --lazy --include-children --pid={0} --limit={1}".format(process.pid, self.cpu_limit)
                report.log_command(limit_cmd)
                processLimit = subprocess.Popen(limit_cmd, shell=True)
            else:
                pass

            r = process.wait()
            if processLimit is not None:
                processLimit.wait()

            tar_output = process.stdout.read()

            if r == 0:
                report.log_state("Moving {0} to {1}".format(self.cc(dest_path_compressed_tmp), self.cc(dest_path_compressed)))
                os.rename(dest_path_compressed_tmp, dest_path_compressed)
            else:
                raise BackupException("tar failed", tar_output)
        else:
            if os.path.exists(dest_path):
                report.log_warn("Destination folder exists {0}".format(self.cc(dest_path)))
                return

            dest_path_tmp = dest_path + "_tmp"
            report.log_state("Copying {0} to {1}...".format(self.cc(self.src_dir), self.cc(dest_path_tmp)))
            try:
                if os.path.exists(dest_path_tmp):
                    shutil.rmtree(dest_path_tmp)
                shutil.copytree(self.src_dir, dest_path_tmp)
                os.rename(dest_path_tmp, dest_path)
            except Exception as err:
                report.log_warn(err)

class RotateTask(Task):
    delete_older_than = None 
    clean_day_parts = None
    delete_prefix = None

    def __init__(self, config):
        super().__init__(config)

        self.delete_older_than = config.get('delete_older_than')
        self.clean_day_parts = config.get('clean_day_parts')
        self.delete_prefix = config.get('delete_prefix')

        if self.delete_older_than is not None and self.clean_day_parts is not None:
            raise BackupException.log_error("specify one of delete_older_than or clean_day_parts")

    def perform(self):
        self.rpl = [
            ['DEST_DIR', self.dest_dir],
        ]
        self.rpl = sorted(self.rpl, key=lambda x: -len(x[1]))

        if self.delete_older_than is not None:
            interval = utils.get_interval_from_str(self.delete_older_than)

            for filename in os.listdir(self.dest_dir):
                if filename.endswith(".tmp"):
                    continue
                date = utils.get_date_from_filename(filename)
                if date is None:
                    continue

                if utils.get_date_diff_in_seconds(date, base_date) >= interval:
                    self.delete_backup_file(filename)

        elif self.clean_day_parts:
            parts = []
            # extract parts from string
            cur_date = base_date.date()
            for p in self.clean_day_parts.split(","):
                days = int(p.strip())
                start_date = cur_date - timedelta(days - 1)
                end_date = cur_date
                cur_date = start_date - timedelta(1)
                parts.append({"from": start_date, "to": end_date, "file_to_keep": None})

            # assign files to parts
            for filename in os.listdir(self.dest_dir):
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
            report.log_msg("Current backups state")
            files_to_keep = []
            for p in parts:
                if p["file_to_keep"] is not None:
                    files_to_keep.append(p["file_to_keep"])

                    file_date = utils.get_date_from_filename(p["file_to_keep"])
                    file_str = "{0[file_to_keep]} ({1})".format(p, ago_format(base_date - file_date))
                else:
                    file_str = 'no file'

                report.log_state("[{0[from]}, {0[to]}] file: {1}".format(p, file_str))

            for filename in os.listdir(self.dest_dir):
                if filename.endswith(".tmp"):
                    continue
                date = utils.get_date_from_filename(filename)
                if date is None:
                    continue
                date = date.date()

                if not filename in files_to_keep:
                    self.delete_backup_file(filename)

    def delete_backup_file(self, filename):
        if self.delete_prefix:
            new_filename = self.delete_prefix + filename
            report.log_state("Renaming {0} to {1}...".format(self.cc(filename), self.cc(new_filename)))
            dest_path = self.dest_dir + filename
            new_dest_path = self.dest_dir + new_filename
            os.rename(dest_path, new_dest_path)
        else:
            report.log_state("Deleting {0}...".format(self.cc(filename)))
            dest_path = self.dest_dir + filename
            if os.path.isfile(dest_path):
                os.remove(dest_path)
            elif os.path.isdir(dest_path):
                shutil.rmtree(dest_path)

if __name__ == "__main__":
    for task in config['tasks']:
        try:
            type = task['task']
            if type == "backup":
                t = BackupTask(task)
                report.log_task("Backup {0}".format(t.name))
            elif type == "rotate":
                t = RotateTask(task)
                report.log_task("Rotate {0}".format(t.name))
            t.perform()
            code = 0
        except BackupException as e:
            e.log()
            code = 1
        except Exception as e:
            e = BackupException("task failed", base_exc=e)
            e.log()
            code = 1

    mail_config = config.get('mail')
    if mail_config:
        report.send(config, code)
    exit(code)

