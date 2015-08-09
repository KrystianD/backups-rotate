template = """\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
    <body>
{content}
    </body>
</html>
"""

output = None

def init():
    global output
    # f = open("report.html", "wb")
    output = ""
    
def log(cmd):
    global output
    output += '<div style="">{0}</div>'.format(cmd)

def log_command(cmd):
    global output
    output += '<div style="">{0}</div>'.format(cmd)

def get_html():
    global output
    return template.format(content=output)

print(template)
