import datetime, sys, os, random, argparse, configparser
sys.path.append("..")
import utils

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--basedate")
args = parser.parse_args()

config = configparser.ConfigParser()
config.read(args.config)

clean_day_parts = utils.get_option(config, 'clean_day_parts')

base_date = datetime.datetime.now()
if args.basedate:
    base_date = datetime.datetime.strptime(args.basedate, "%Y-%m-%d")

# Get files info
destDir = "test_backups"
haveBackups = []
maxDate = None
minDate = None
for filename in os.listdir (destDir):
	fdate = utils.get_date_from_filename (filename)
	if fdate is None:
		continue
	fdate = fdate.date ()
	haveBackups.append (fdate)
	if maxDate is None or maxDate < fdate:
		maxDate = fdate
	if minDate is None or minDate > fdate:
		minDate = fdate

colors = [1,2,3,4,5,6,7]

# Extract parts from string
random.seed (4)
parts = []
curDate = maxDate
curDate = base_date.date()
if clean_day_parts:
    for p in clean_day_parts.split (","):
            days = int(p.strip ())
            _startDate = curDate - datetime.timedelta (days - 1)
            _endDate = curDate
            curDate = _startDate - datetime.timedelta (1)
            c = random.randint (1,7)
            while len(parts) > 0 and c == parts[len(parts)-1]["color"]:
                    c = random.randint (1,7)
            parts.append ({ "from": _startDate, "to": _endDate, "color": c })

endDate = maxDate
endDate = base_date.date()

while (endDate + datetime.timedelta (days=1)).month == endDate.month:
	endDate = endDate + datetime.timedelta (days=1)

startDate = endDate - datetime.timedelta (days=40)
startDate = minDate

while startDate.day != 1:
	startDate = startDate - datetime.timedelta (days=1)
startMonth = startDate.month


date = startDate
month = startMonth
year = minDate.year

weekNames = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

sys.stdout.write ("\033[2J")
sys.stdout.write ("\033[0;0H")

print (startDate, endDate)

# Header
sys.stdout.write ("{0:^21}\n".format ("{0:4}-{1:02}".format (date.year, date.month)))
for i in range (0, 7): sys.stdout.write (weekNames[i] + " ")
sys.stdout.write ("\n")

for i in range (0, date.weekday ()):
	sys.stdout.write ("   ")

while date <= endDate:
	weekday = date.weekday ()
	
	for p in parts:
		if date >= p["from"] and date <= p["to"]:
			sys.stdout.write ("\033[4"+str(p["color"])+";1m")
	
	if date in haveBackups:
		sys.stdout.write ("\033[31;1m")
	else:
		pass
	sys.stdout.write ("{0:2} ".format (date.day))
	sys.stdout.write ("\033[0m")
	
	if weekday == 6:
		sys.stdout.write ("\n")
		date = date + datetime.timedelta (days=1)
	
	else:
		date = date + datetime.timedelta (days=1)

sys.stdout.write ("\n")
