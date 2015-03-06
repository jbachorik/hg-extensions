from mercurial import util, commands
from subprocess import call, check_output
from string import Template

import urllib2
import urllib
import shutil
import os
import tempfile
import json
import cookielib
import stat

webrev_origin = "http://hg.openjdk.java.net/code-tools/webrev/raw-file/tip/webrev.ksh"
issue_api = "https://bugs.openjdk.java.net/rest/api/latest/issue"
issue_browse = "https://bugs.openjdk.java.net/browse"
authURL = "https://id.openjdk.java.net/console/login"

opener = None

def webrev(ui, repo, **opts):
    wrev = findWebrev(ui)
    if not wrev:
        ui.warning("'webrev' tool not available. Exitting.\n")
        return

    update = opts['update']
    rev = opts['revision']
    category = opts['category']
    
    ctx = repo[None if rev == '' else rev]
    user = ctx.user()
    server = opts['server']

    issue = opts['issue']
    if issue == '':
        issue = inferIssue(ui, ctx)

    if not issue:
        issue = ui.prompt("Enter the issue number: ")

    if not issue:
        ui.warning("No issue number provided. Exitting.\n")
        return

    augmentChange(ui, ctx, issue)

    parent = findChangeRoot(ui, ctx)

    patches = check_output(['hg', 'qseries']).splitlines()
    if patches:
        qtop = check_output(['hg', 'qtop']).strip()

        check_output(['hg', 'qpop', '-a'])
        check_output(['hg', 'qpush', '--move', qtop])

    if parent:
        call(["webrev", "-N", "-c", issue, "-r", str(parent.rev()), "-o", issue])
    else:
        call(["webrev"])
    
    if patches:
        check_output(['hg', 'qpop', '-a'])
        for patch in patches:
            patch = patch.strip()
            check_output(['hg', 'qpush', '--move', patch])
            if patch == qtop:
                break

    augmentWebrev(ui, issue)

    uploadWebrev(ui, server, issue, category, user, update)

def augmentChange(ui, ctx, issue):
    if "qtip" in ctx.tags():
        issueJs = loadIssue(ui, issue)
        title = issueTitle(ui, issue, issueJs)
        revdby = '\nReviewed-by: duke' if 'Reviewed-by:' in title else ''
        call(['hg', 'qrefresh', '-m', '%s%s' % (title, revdby)])

def findChangeRoot(ui, ctx):
    if "qtip" in ctx.tags():
        return findMqRoot(ui, ctx)
    else:
        return findBranchRoot(ui, ctx)

def findMqRoot(ui, ctx):
    first = findMqFirst(ui, ctx)

    return first.parents()[0] if first else None

def findBranchRoot(ui, ctx):
    branch = ctx.branch()
    if branch == "default":
        return ctx

    for c in ctx.parents():
        return findBranchRoot(ui, c)


    return None

def findChangeFirst(ui, ctx):
    if "qtip" in ctx.tags():
        return findMqFirst(ui, ctx)
    else:
        return findBranchFirst(ui, ctx)

def findMqFirst(ui, ctx):
    if "qbase" in ctx.tags() and not str(ctx).endswith('+'):
        return ctx

    for c in ctx.parents():
        return findMqFirst(ui, c)

def findBranchFirst(ui, ctx):
    for c in ctx.parents():
        ui.write('checking parent: %s [%s]\n' % (c.rev(), c.branch()))
        if c.branch() == "default":
            return ctx

        return findBranchFirst(ui, c)

    return None

def findLatestDefault(ui, ctx):
    for c in ctx.children():
        if c.branch() == 'default':
            return findLatestDefault(ui, c)

    return ctx if ctx.branch() == 'default' else None

def inferIssue(ui, ctx):
    for tag in ctx.tags():
        if tag.startswith("JDK-"):
            issue = validateIssue(ui, tag)
            if (issue):
                return issue[4:]

    for bkmk in ctx.bookmarks():
        issue = validateIssue(ui, bkmk)
        if issue:
            return issue[4:]

    return None

def validateIssue(ui, issue):
    url = "%s/%s" % (issue_api, issue)

    ui.note("Validating issue number " + issue + "\n")
    try:
        ui.note("Opening URL: %s\n" % url)
        loadData(ui, url)
        return issue
    except urllib2.HTTPError, e:
        ui.note("%s\n" % e)
    except urllib2.URLError, e:
        ui.note("%s\n" % e)

    return None

def augmentWebrev(ui, issue):
    issueJs = loadIssue(ui, issue)
    title = issueTitle(ui, issue, issueJs)
    if title:
        fTitle = "%s/webrev/.title" % issue
        with open(fTitle, "wb") as local_file:
            local_file.write(title)

def issueTitle(ui, issue, issueJs):
    if issueJs:
        title = "%s: %s" % (issue, issueJs['fields']['summary'])
        return title

    return None

def issueTitleEx(ui, issue):
    issueJs = loadIssue(ui, issue)
    return issueTitle(ui, issue, issueJs)

def loadIssue(ui, issue):
    try:
        response = loadData(ui, "%s/JDK-%s" % (issue_api, issue))
        issueJs = json.load(response)

        return issueJs
    except urllib2.HTTPError, e:
        ui.note("%s\n" % e)
    except urllib2.URLError, e:
        ui.note("%s\n" % e)

    return None

def loadData(ui, url):
    authenticate(ui)

    req = urllib2.Request(url)
    req.add_header("Content-type", "application/json")
    req.add_header("Accept", "application/json")
    return opener.open(req)

def authenticate(ui):
    global opener

    if opener:
        return opener

    uname = ui.config("jbs", "username", default = None, untrusted = False)
    upwd = ui.config("jbs", "password", default = None, untrusted = False)

    ui.note("Authenticating\n")

    cj = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

    login_data = urllib.urlencode({
        'email' : uname,
        'password' : upwd,
    })

    req = urllib2.Request(authURL)
    fp = opener.open(req, login_data)

    fp.close()
    ui.note("done\n")

    return opener

def uploadWebrev(ui, server, issue, category, user, update):
    unused = False

    url = "http://%s/~%s/%s/webrev" % (server, user, issue)
    ver = 0
    postfix = ".%02d" % ver
    while not unused:
        try:
            urllib2.urlopen(url + postfix)
            ver += 1
            postfix = ".%02d" % ver
        except urllib2.HTTPError, e:
            ui.note("%s\n" % e)
            unused = True
        except urllib2.URLError, e:
            ui.note("%s\n" % e)
            unused = True


    if update and ver > 0:
        ver -= 1
        postfix = ".%02d" % ver
        ui.write("Updating an existing revision of webrev for %s: %2d\n" % (issue, ver))
    else:
        ui.write("Creating a new revision of webrev for %s: %2d\n" % (issue, ver))
        
    if category:
        category = "/%s" % category
        
    destDir = "%s/webrev%s%s" % (issue, postfix, category)
    destZip = "%s/webrev%s%s.zip" % (issue, postfix, category)
    if os.path.exists(destDir):
        shutil.rmtree(destDir)

    if os.path.exists(destZip):
       os.remove(destZip)

    shutil.move(issue + "/webrev", destDir)
    shutil.move(issue + "/webrev.zip", destZip)
    resp = ui.promptchoice("Review created in '%s'\nDo you want to preview it(Yn)? $$ &Yes $$ &No" % os.path.abspath(destDir), 0)

    upload = True

    if resp == 0:
        reviewUrl = "file://%s/index.html" % os.path.abspath(destDir)
        call(["google-chrome", reviewUrl])
        resp = ui.promptchoice("Upload review(yN)? $$ &Yes $$ &No", 1)
        upload = (resp == 0)

    if upload:
        call(["rsync", "-i", "-z", "-a", "%s" % os.path.abspath(issue), "%s@cr.openjdk.java.net:" % user])
        mailer = ui.config("webrev", "mailer", default = None, untrusted = None)
        mail_args = mailer.split(' ')
        
        if mailer:
            s = Template(mail_args[2])
            subj = 'RFR %s: %s' % (issue, issueTitleEx(ui, issue))
            bdy = 'Please, review the following change\n\n' \
                   'Issue : %s/JDK-%s\n' \
                   'Webrev: %s%s\n\n' \
                   '<message goes here>' % (issue_browse, issue, url, postfix)
                   
            args = '%s' % s.substitute(subject = urllib.quote(subj), body = urllib.quote(bdy))
            ui.write("args =  %s\n" % args)
            call([mail_args[0], mail_args[1], args])
        else:
            ui.write("Issue : %s/JDK-%s\n" % (issue_api, issue))
            ui.write("Webrev: %s%s\n" % (url, postfix))       
    else:
        ui.write("Review upload cancelled!\n")

def findWebrev(ui):
    wr = which("webrev")

    if not wr:
        tmpdir = tempfile.gettempdir()
        wr = "%s/webrev" % tmpdir

        if not os.path.exists(wr):
            ui.write("'webrev' not found in PATH. Attempting to download from OpenJDK...\n")
            try:
                f = urllib2.urlopen(webrev_origin)
                with open(wr, "wb") as local_file:
                    local_file.write(f.read())

                return wr
            except HTTPError, e:
                ui.warning("%s\n" % e)
            except URLError, e:
                ui.warning("%s\n" % e)

            return None

    return wr

def which(pgm):
    path=os.getenv('PATH')
    for p in path.split(os.path.pathsep):
        p=os.path.join(p,pgm)
        if os.path.exists(p) and os.access(p,os.X_OK):
            return p

def integrate(ui, repo, **opts):
    rev = opts['revision']

    ctx = repo[None if rev == '' else rev]

    issue = opts['issue']
    if issue == '':
        issue = inferIssue(ui, ctx)

    if not issue:
        issue = ui.prompt("Enter the issue number: ")

    if not issue or issue == '':
        ui.warning("No issue number provided. Exitting.\n")
        return

    revs = opts['reviewedby']
    if revs == '':
        revs = ui.prompt("Enter reviewers (comma separated): ")

    if not revs or revs == '':
        ui.warning('No reviewers provided. Exitting.\n')

    dest = None
    root = findBranchRoot(ui, ctx)
    if root:
        dest = findLatestDefault(ui, root)

    src = findBranchFirst(ui, ctx)
    ui.write('src: %s\n' % src)
    ui.write('dst: %s\n' % dest)

    issueJs = loadIssue(ui, issue)
    commit_message = '%s\nReviewed-by: %s' % (issueTitle(ui, issue, issueJs), revs)

    ui.write("msg: %s\n" % commit_message)
    if src:
        call(['hg', 'rebase', '--dest', str(dest), '--source', str(src)])
        call(['hg', 'commit', '--amend', '-m', commit_message])
    else:
        call(['hg', 'rebase', '--dest', str(dest)])
        call(['hg', 'commit', '--amend', '-m', commit_message])
        
def jbsrefresh(ui, repo, **opts):
    rev = opts['revision']

    ctx = repo[None if rev == '' else rev]

    issue = opts['issue']
    if issue == '':
        issue = inferIssue(ui, ctx)

    if not issue:
        issue = ui.prompt("Enter the issue number: ")

    if not issue or issue == '':
        ui.warning("No issue number provided. Exitting.\n")
        return

    revs = opts['reviewedby']
    if revs == '':
        revs = 'duke'

    augmentChange(ui, ctx, issue)

def qexport(ui, repo, patch, **opts):
    export_cmd = ['hg', 'export']
    if opts['git']:
        export_cmd.append('-g')

    export_cmd.append(patch)

    active = check_output(['hg', 'qtop']).strip()

    # ok, let's go and apply the patch to export
    check_output(['hg', 'qgoto', patch])
    ui.write(check_output(export_cmd))

    check_output(['hg', 'qgoto', active])
    call(['hg', 'purge'])
    call(['hg', 'update', '-C'])


cmdtable = {
    # "command-name": (function-call, options-list, help-string)
    "webrev": (webrev,
                     [('r', 'revision', '', 'revision number'),
                      ('u', 'update', None, 'update the latest webrev in-place'),
                      ('i', 'issue', '', 'the associated issue number'),
                      ('c', 'category', '', 'webrev qualifier - eg. hotspot, jdk etc.'),
                      ('', 'server', 'cr.openjdk.java.net', 'server to publish the webrev')],
                     "hg webrev [options]"),
                     
    "jbsrefresh": (jbsrefresh,
                    [('r', 'revision', '', 'revision number'),
                     ('i', 'issue', '', 'the issue number'),
                     ('w', 'reviewedby', '', 'comma separated list of reviewers')],
                   "hg jbsrefresh [options]"),

    "integrate": (integrate,
                     [('r', 'revision', '', 'revision number'),
                      ('w', 'reviewedby', '', 'comma separated list of reviewers'),
                      ('i', 'issue', '', 'the associated issue number')],
                    "hg integrate [options]"),

    "qexport": (qexport,
                    [('g', 'git', False, 'git format')],
                    "hg qexport [options] patch-name")
}