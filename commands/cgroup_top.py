#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Monitor local cgroups as used by Docker, LXC, SystemD, ...

Usage:
  ctop [--tree] [--refresh=<seconds>] [--columns=<columns>] [--sort-col=<sort-col>] [--follow=<name>] [--fold=<cgroup>, ...]
  ctop (-h | --help)

Options:
  --tree                 Show tree view by default.
  --fold=<name>          Start with <name> cgroup path folded
  --follow=<name>        Follow/highlight cgroup at path.
  --refresh=<seconds>    Refresh display every <seconds> [default: 1].
  --columns=<columns>    List of optional columns to display. Always includes 'name'. [default: owner,processes,memory,cpu-sys,cpu-user,blkio,cpu-time].
  --sort-col=<sort-col>  Select column to sort by initially. Can be changed dynamically. [default: cpu-user]
  --type=[types]         Only keep containers of this types
  -h --help              Show this screen.

'''

from __future__ import print_function
import os
import re
import sys
import stat
import pwd
import time
import pty
import errno
import subprocess
import multiprocessing
import json

from collections import defaultdict
from collections import namedtuple

from optparse import OptionParser


try:
    import curses, _curses
except ImportError:
    print("Curse is not available on this system. Exiting.", file=sys.stderr)
    sys.exit(0)

def cmd_exists(cmd):
    try:
        return subprocess.call(["which",  cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
    except OSError:
        return False

HAS_LXC = cmd_exists('lxc-start')
HAS_DOCKER = cmd_exists('docker')
HAS_OPENVZ = cmd_exists('vzctl')
regexp_ovz_container = re.compile('^/\d+$')
HAS_LIBVIRT = cmd_exists('virsh')


HIDE_EMPTY_CGROUP = True
CGROUP_MOUNTPOINTS={}
CONFIGURATION = {
        'sort_by': 'cpu_total',
        'sort_asc': False,
        'tree': False,
        'follow': False,
        'pause_refresh': False,
        'refresh_interval': 1.0,
        'columns': [],
        'selected_line': None,
        'offset': 0,
        'selected_line_num': 0,
        'selected_line_name': '/',
        'cgroups': [],
        'fold': [],
        'type': [],
}

Column = namedtuple('Column', ['title', 'width', 'align', 'col_fmt', 'col_data', 'col_sort'])

COLUMNS = []
COLUMNS_MANDATORY = ['name']
COLUMNS_AVAILABLE = {
    'owner':     Column("OWNER",   10, '<', '{0:%ss}',      'owner',           'owner'),
    'type':      Column("TYPE",    10, '<', '{0:%ss}',      'type',            'type'),
    'processes': Column("PROC",    11, '>', '{0:%ss}',      'tasks',           'tasks'),
    'memory':    Column("MEMORY",  17, '^', '{0:%ss}',      'memory_cur_str',  'memory_cur_bytes'),
    'cpu-sys':   Column("SYST",     5, '^', '{0: >%s.1%%}', 'cpu_syst',        'cpu_total'),
    'cpu-user':  Column("USER",     5, '^', '{0: >%s.1%%}', 'cpu_user',        'cpu_total'),
    'blkio':     Column("BLKIO",   10, '^', '{0: >%s}',     'blkio_bw',        'blkio_bw_bytes'),
    'cpu-time':  Column("TIME+",   14, '^', '{0: >%ss}',    'cpu_total_str',   'cpu_total_seconds'),
    'name':      Column("CGROUP",  '', '<', '{0:%ss}',      'cgroup',          'cgroup'),
}

DOCKER_PREFIXES = ["/docker/", "/system.slice/docker-", "/system.slice/docker/"]

# TODO:
# - visual CPU/memory usage
# - auto-color
# - persist preferences
# - dynamic column width
# - handle small screens
# - massive refactoring. This code U-G-L-Y

## Utils


def strip_prefix(prefix, text):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


def docker_container_name(container_id, default, cache=dict()):
    # Python's default arguments are evaluated when the function is
    # defined, not when the function is called.
    # We potentially cache and return a default value so we don't spend time
    # pointlessly retrying to get the container name if something goes wrong.
    cached_name = cache.get(container_id)
    if cached_name:
        return cached_name

    try:
        sp = subprocess.Popen(['docker', 'inspect', container_id],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
    except OSError:
        # `docker` is not on PATH
        cache[container_id] = default
        return default

    for _ in range(10):
        sp.poll()
        if sp.returncode is not None:
            break
        time.sleep(0.1)

    if sp.returncode is None:
        try:
            sp.kill()
        except OSError:
            # OSError: [Errno 3] No such process
            pass
    elif sp.returncode == 0:
        stdout, _stderr = sp.communicate()
        try:
            containers = json.loads(stdout)
            if len(containers) == 1:
                container = containers[0]
                container_name = container['Name'].lstrip('/')
                name = '/docker/' + container_name
                cache[container_id] = name
                return name
        except Exception:
            pass

    cache[container_id] = default
    return default

def libvirt_vm_name(cgroup_line):
    # Get VM name from cgroup line like
    # /machine.slice/machine-qemu\x2d305\x2d121487.scope/emulator
    cgroup_line = cgroup_line.replace('/machine.slice/machine-qemu','')
    splited_line = cgroup_line.split('.scope')
    if len(splited_line) < 1: 
        return ''
    splited_line = splited_line[0].split("\\x2d")
    return splited_line[len(splited_line)-1]

def to_human(num, suffix='B'):
    num = int(num)
    for unit in [' ','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "{0:.1f}{1}{2}".format(num, unit, suffix)
        num /= 1024.0
    return "{0:5.1d}{1}{2}" % (num, 'Y', suffix)

def div(num, by):
    res = num / by
    mod = num % by
    return res, mod

def to_human_time(seconds):
    minutes, seconds = div(seconds, 60)
    hours, minutes = div(minutes, 60)
    days, hours = div(hours, 24)
    if days:
        return '%3dd %02d:%02d.%02d' % (days, hours, minutes, seconds)
    else:
        return '%02d:%02d.%02d' % (hours, minutes, seconds)

def get_total_memory():
    '''
    Get total memory from /proc if available.
    '''
    try:
        with open('/proc/meminfo') as f:
            content = f.read()
    except OSError:
        content = ''

    for line in content.split('\n'):
        fields = re.split(' +', line)
        if fields[0].strip() == "MemTotal:":
            return int(fields[1])*1024

    return -1

def run(user, cmd, interactive=False):
    '''
    Run ``cmd`` as ``user``. If ``interactive`` is True, save any curses status
    and synchronously run the command in foreground. Otherwise, run the command
    in background, discarding any output.

    special user -2 means: current user
    '''
    prefix = []
    cur_uid = os.getuid()
    try:
        cur_user = pwd.getpwuid(cur_uid).pw_name
    except:
        cur_user = cur_uid

    if user != cur_user and user != -2:
        if cur_uid == 0:
            prefix = ['su', user]
        if user == 'root':
            prefix = ['sudo']
        else:
            prefix = ['sudo', '-u', user]

    if interactive:
        # Prepare screen for interactive command
        curses.savetty()
        curses.nocbreak()
        curses.echo()
        curses.endwin()

        # Run command
        pty.spawn(prefix+cmd)

        # Restore screen
        init_screen()
        curses.resetty()
    else:
        with open('/dev/null', 'w') as dev_null:
            subprocess.Popen(
                prefix+cmd,
                stdout=dev_null,
                stderr=dev_null,
                close_fds=True,
            )

class Cgroup(object):
    def __init__(self, path, base_path):
        self.path = path
        self.base_path = base_path

    @property
    def short_path(self):
        return self.path[len(self.base_path):] or '/'

    @property
    def name(self):
        if HAS_DOCKER and self.type == 'docker':
            container_id = self.short_path
            for prefix in DOCKER_PREFIXES:
                container_id = strip_prefix(prefix, container_id)
            return docker_container_name(container_id, default=self.short_path)

        return self.short_path

    @property
    def owner(self):
        path = os.path.join(self.base_path, self.path, 'tasks')
        uid = os.stat(path).st_uid
        try:
            return pwd.getpwuid(uid).pw_name
        except:
            return uid

    @property
    def type(self):
        path = self.short_path

        # Guess cgroup owner
        if any(path.startswith(prefix) for prefix in DOCKER_PREFIXES):
            return 'docker'
        elif path.startswith('/lxc/'):
            return 'lxc'
        elif path.startswith('/user.slice/'):
            _, parent, name = path.rsplit('/', 2)
            if parent.endswith('.scope'):
                if os.path.isdir('/home/%s/.local/share/lxc/%s' % (self.owner, name)):
                    return 'lxc-user'
            return 'systemd'
        elif path == '/user.slice' or path == '/system.slice' or path.startswith('/system.slice/'):
            return 'systemd'
        elif path.startswith('/machine.slice/machine-qemu'):
            return 'qemu-kvm'
        elif regexp_ovz_container.match(path) and path != '/0' and HAS_OPENVZ:
            return 'openvz'
        else:
            return '-'

    def _coerce(self, value):
        try:
            return int(value)
        except:
            pass

        try:
            return float(value)
        except:
            pass

        return value

    def __getitem__(self, name):
        path = os.path.join(self.base_path, self.path, name)

        with open(path) as f:
            content = f.read().strip()

        if name == 'tasks' or '\n' in content or ' ' in content:
            content = content.split('\n')

            if ' ' in content[0]:
                content = dict((re.split(' +', l, 1) for l in content if content))
                for k, v in content.items():
                    content[k] = self._coerce(v)
            else:
                content = [self._coerce(v) for v in content if v]

        else:
            content = self._coerce(content)

        return content

def cgroups(base_path):
    '''
    Generator of cgroups under path ``name``
    '''
    for cgroup_path, dirs, files in os.walk(base_path):
        yield Cgroup(cgroup_path, base_path)

## Grab cgroup data

def init():
    # Get all cgroup subsystems avalaible on this system
    with open("/proc/cgroups") as f:
        cgroups = f.read().strip()

    subsystems = []
    for cgroup in cgroups.split('\n'):
        if cgroup[0] == '#': continue
        subsystems.append(cgroup.split()[0])

    # Match cgroup mountpoints to susbsytems. Always take the first matching
    with open("/proc/mounts") as f:
        mounts = f.read().strip()

    for mount in mounts.split('\n'):
        mount = mount.split(' ')

        if mount[2] != "cgroup":
            continue

        for arg in mount[3].split(','):
            if arg in subsystems and arg not in CGROUP_MOUNTPOINTS:
                CGROUP_MOUNTPOINTS[arg] = mount[1]

def collect_ensure_common(data, cgroup):
    '''
    Some cgroup exists in only one controller. Attempt to collect common metrics
    (tasks clount, owner, ...) from the first controller we find the task in.
    '''
    if 'tasks' in data:
        return

    # Collect
    data['tasks'] = cgroup['tasks']
    data['owner'] = cgroup.owner
    data['type'] = cgroup.type

def get_user_beacounts():
    '''
    get memory stats(via privvmpages) from vzlist output to openvz containers
    '''
    prefix = []
    if os.getuid() != 0:
       prefix = ['sudo']

    command = prefix + ['vzlist', '-o', 'ctid,privvmpages,privvmpages.l', '-H']
    output, err = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE).communicate()
    return output


def collect(measures):
    cur = defaultdict(dict)
    prev = measures['data']


    # Collect CPU statistics
    if 'cpuacct' in CGROUP_MOUNTPOINTS:
        # list all "folders" under mountpoint
        for cgroup in cgroups(CGROUP_MOUNTPOINTS['cpuacct']):
            collect_ensure_common(cur[cgroup.name], cgroup)

            # Collect CPU stats
            cur[cgroup.name]['cpuacct.stat'] = cgroup['cpuacct.stat']
            cur[cgroup.name]['cpuacct.stat.diff'] = {'user':0, 'system':0}

            # Collect CPU increase on run > 1
            if cgroup.name in prev:
                for key, value in cur[cgroup.name]['cpuacct.stat'].items():
                    cur[cgroup.name]['cpuacct.stat.diff'][key] = value - prev[cgroup.name]['cpuacct.stat'][key]

    # Collect BlockIO statistics
    if 'blkio' in CGROUP_MOUNTPOINTS:
        # list all "folders" under mountpoint
        for cgroup in cgroups(CGROUP_MOUNTPOINTS['blkio']):
            collect_ensure_common(cur[cgroup.name], cgroup)

            # Collect BlockIO stats
            try:
                cur[cgroup.name]['blkio.throttle.io_service_bytes'] = cgroup['blkio.throttle.io_service_bytes']
                cur[cgroup.name]['blkio.throttle.io_service_bytes.diff'] = {'total':0}
            except IOError as e:
                # Workaround broken systems (see #15)
                if e.errno == errno.ENOENT:
                    continue
                raise

            # Collect BlockIO increase on run > 1
            if cgroup.name in prev:
                cur_val = cur[cgroup.name]['blkio.throttle.io_service_bytes']['Total']
                prev_val = prev[cgroup.name]['blkio.throttle.io_service_bytes']['Total']
                cur[cgroup.name]['blkio.throttle.io_service_bytes.diff']['total'] = cur_val - prev_val

    # Collect memory statistics
    if 'memory' in CGROUP_MOUNTPOINTS:
        # list all "folders" under mountpoint
        for cgroup in cgroups(CGROUP_MOUNTPOINTS['memory']):
            collect_ensure_common(cur[cgroup.name], cgroup)
            cache = cgroup['memory.stat']['cache']
            cur[cgroup.name]['memory.usage_in_bytes'] = cgroup['memory.usage_in_bytes'] - cache
            cur[cgroup.name]['memory.limit_in_bytes'] = min(int(cgroup['memory.limit_in_bytes']), measures['global']['total_memory'])

    # Collect PIDs constraints. Root cgroup does *not* have the controller files
    if 'pids' in CGROUP_MOUNTPOINTS:
        # list all "folders" under mountpoint
        for cgroup in cgroups(CGROUP_MOUNTPOINTS['pids']):
            if cgroup.name == "/":
                continue
            collect_ensure_common(cur[cgroup.name], cgroup)
            cur[cgroup.name]['pids.max'] = cgroup['pids.max']

    #Collect memory statistics for openvz
    if HAS_OPENVZ:
        user_beancounters = get_user_beacounts()
        # We have lines like -
        #      1202     202419    2457600
        #      1203     299835    2457600
        #      1207      54684    2457600
        #      1210     304939    2457600
        #1000001212      13493    2457600
        for line in user_beancounters.split('\n'):
            if line == '':
                continue
            line = re.sub(r'^\s+', '', line)
            splited_line = re.split('\s+', line)
            if len(splited_line) != 3:
                continue
            ctid, privvmpages, limit = splited_line
            ctid = '/' + ctid
            if 'tasks' not in cur[ctid]:
                continue
            privvmpages = int(privvmpages)
            privvmpages = privvmpages * 4096
            limit = int(limit)
            limit = limit * 4096
            cur[ctid]['memory.usage_in_bytes'] = privvmpages
            cur[ctid]['memory.limit_in_bytes'] = min(limit, measures['global']['total_memory'])

    # Sanity check: any data at all ?
    if not len(cur):
        raise KeyboardInterrupt()

    # Apply
    measures['data'] = cur

def built_statistics(measures, conf):
    # Time
    prev_time = measures['global'].get('time', -1)
    cur_time = time.time()
    time_delta = cur_time - prev_time
    measures['global']['time'] = cur_time
    cpu_to_percent = measures['global']['scheduler_frequency'] * measures['global']['total_cpu'] * time_delta

    # Build data lines
    results = []
    for cgroup, data in measures['data'].items():
        cpu_usage = data.get('cpuacct.stat.diff', {})
        line = {
            'owner': str(data.get('owner', 'nobody')),
            'type': str(data.get('type', 'cgroup')),
            'cur_tasks': len(data['tasks']),
            'max_tasks': data.get('pids.max', 'max'),
            'memory_cur_bytes': data.get('memory.usage_in_bytes', 0),
            'memory_limit_bytes': data.get('memory.limit_in_bytes', measures['global']['total_memory']),
            'cpu_total_seconds': data.get('cpuacct.stat', {}).get('system', 0) + data.get('cpuacct.stat', {}).get('user', 0),
            'cpu_syst': cpu_usage.get('system', 0) / cpu_to_percent,
            'cpu_user': cpu_usage.get('user', 0) / cpu_to_percent,
            'blkio_bw_bytes': data.get('blkio.throttle.io_service_bytes.diff', {}).get('total', 0),
            'cgroup': cgroup,
        }
        line['cpu_total'] = line['cpu_syst'] + line['cpu_user'],
        line['cpu_total_str'] = to_human_time(line['cpu_total_seconds'])
        line['memory_cur_percent'] = line['memory_cur_bytes'] / line['memory_limit_bytes']
        line['memory_cur_str'] = "{0: >7}/{1: <7}".format(to_human(line['memory_cur_bytes']), to_human(line['memory_limit_bytes']))
        line['tasks'] = "{0: >5}/{1: <5}".format(line['cur_tasks'], line['max_tasks'])
        line['blkio_bw'] = to_human(line['blkio_bw_bytes'], 'B/s')
        results.append(line)

    return results

def render_tree(results, tree, level=0, prefix=[], node='/'):
    # Exit condition
    if node not in tree:
        return

    # Iteration
    for i, line in enumerate(tree[node]):
        cgroup = line['cgroup']

        # Build name
        if i == len(tree[node]) - 1:
            line['_tree'] = prefix + [curses.ACS_LLCORNER, curses.ACS_HLINE, ' ']
            _child_prefix = prefix + [' ', ' ', ' ']
        else:
            line['_tree'] = prefix + [curses.ACS_LTEE, curses.ACS_HLINE, ' ']
            _child_prefix = prefix + [curses.ACS_VLINE, ' ', ' ']

        # Commit, fold or recurse
        results.append(line)
        if cgroup not in CONFIGURATION['fold']:
            render_tree(results, tree, level+1, _child_prefix, cgroup)
        else:
            line['_tree'] [-2] = '+'

def filter_tree(tree, keep, node='/'):
    '''
    Keep a branch if and only if it is of of a 'keep' type or has a child of
    the 'keep' type
    '''
    filtered = []

    # Filter
    for cgroup in tree.get(node, []):
        if filter_tree(tree, keep, cgroup['cgroup']):
            filtered.append(cgroup)
        elif cgroup['type'] in keep:
            filtered.append(cgroup)

    # Commit
    if filtered:
        tree[node] = filtered
    else:
        tree.pop(node, None)

    return bool(filtered)

def prepare_tree(results):
    '''
    Filter results for matching types and render tree
    '''
    ## List view
    if not CONFIGURATION['tree']:
        # Fast track: if there is no filter, do not filter
        if not CONFIGURATION['type']:
            return results

        # Slow track: do filter
        return [l for l in results if l['type'] in CONFIGURATION['type']]

    ## Tree view
    tree = {}
    rendered = []

    # Build tree
    for line in results:
        cgroup = line['cgroup']
        parent = os.path.dirname(cgroup)

        # Root cgroup ?
        if parent == cgroup:
            rendered.append(line)
            continue

        # Insert in hierarchie as needed
        if parent not in tree:
            tree[parent] = []
        tree[parent].append(line)

    # If there are filters, filter
    if CONFIGURATION['type']:
         filter_tree(tree, CONFIGURATION['type'])

    # Render tree, starting from root
    render_tree(rendered, tree)
    return rendered

def display(scr, results, conf):
    # Sort and render
    results = sorted(results, key=lambda line: line.get(conf['sort_by'], 0), reverse=not conf['sort_asc'])
    results = prepare_tree(results)

    CONFIGURATION['cgroups'] = [cgroup['cgroup'] for cgroup in results]

    # Ensure selected line name synced with num
    if results:
        if CONFIGURATION['follow']:
            while True:
                try:
                    i = CONFIGURATION['cgroups'].index(CONFIGURATION['selected_line_name'])
                    CONFIGURATION['selected_line_num'] = i
                    break
                except:
                    CONFIGURATION['selected_line_name'] = os.path.dirname(CONFIGURATION['selected_line_name'])
        else:
            CONFIGURATION['selected_line_num'] = min(len(results)-1, CONFIGURATION['selected_line_num'])
            CONFIGURATION['selected_line_name'] = CONFIGURATION['cgroups'][CONFIGURATION['selected_line_num']]
        CONFIGURATION['selected_line'] = results[CONFIGURATION['selected_line_num']]
    else:
        CONFIGURATION['selected_line_num'] = 0
        CONFIGURATION['selected_line_name'] = ''
        CONFIGURATION['selected_line'] = None

    # Get display informations
    height, width = scr.getmaxyx()
    list_height = height - 2 # title + status lines

    # Update offset
    max_offset = max(0, len(results) - list_height)
    # selected line above screen limit
    if CONFIGURATION['selected_line_num'] < CONFIGURATION['offset']:
        CONFIGURATION['offset'] = CONFIGURATION['selected_line_num']
    # selected line below screen limit
    elif CONFIGURATION['selected_line_num'] - CONFIGURATION['offset'] > list_height - 1:
        CONFIGURATION['offset'] = CONFIGURATION['selected_line_num'] - list_height + 1
    # offset non consistent
    elif CONFIGURATION['offset'] > max_offset:
        CONFIGURATION['offset'] = max_offset

    # Display statistics
    scr.clear()

    # Title line && templates
    x = 0
    line_tpl = []
    scr.addstr(0, 0, ' '*width, curses.color_pair(1))

    for col in COLUMNS:
        # Build templates
        title_fmt = '{0:%s%ss}' % (col.align, col.width)
        line_tpl.append(col.col_fmt % (col.width))

        # Build title line
        color = 2 if col.col_sort == conf['sort_by'] else 1
        try:
            scr.addstr(0, x, title_fmt.format(col.title)+' ', curses.color_pair(color))
        except:
            # Handle narrow screens
            break
        if col.width:
            x += col.width + 1

    # Content
    lineno = 1
    for line in results[CONFIGURATION['offset']:]:
        y = 0
        if lineno-1 == CONFIGURATION['selected_line_num']-CONFIGURATION['offset']:
            col_reg, col_tree = curses.color_pair(2), curses.color_pair(2)
        else:
            col_reg, col_tree = colors = curses.color_pair(0), curses.color_pair(4)

        # Draw line background
        try:
            scr.addstr(lineno, 0, ' '*width, col_reg)
        except _curses.error:
            # Handle small screens
            break

        # Draw line content
        try:
            for col in COLUMNS:
                cell_tpl = col.col_fmt % (col.width if col.width else 1)
                data_point = line.get(col.col_data, '')

                if col.title == 'CGROUP' and CONFIGURATION['tree']:
                    data_point = os.path.basename(data_point) or '[root]'

                    for c in line.get('_tree', []):
                        scr.addch(c, col_tree)
                        y+=1

                scr.addstr(lineno, y, cell_tpl.format(data_point)+' ', col_reg)
                if col.width:
                    y += col.width + 1
        except _curses.error:
            # Handle narrow screens
            pass
        lineno += 1
    else:
        # Make sure last line did not wrap, clear it if needed
        try: scr.addstr(lineno, 0, ' '*width)
        except _curses.error: pass

    # status line
    try:
        color = curses.color_pair(2)
        try:
            scr.addstr(height-1, 0, ' '*(width), color)
        except:
            # Last char wraps, on purpose: draw full line
            pass

        selected = results[CONFIGURATION['selected_line_num']] if results else {}

        scr.addstr(height-1, 0, " CTOP ", color)
        scr.addch(curses.ACS_VLINE, color)
        scr.addstr(" [P]ause: "+('On ' if CONFIGURATION['pause_refresh'] else 'Off '), color)
        scr.addch(curses.ACS_VLINE, color)
        scr.addstr(" [F]ollow: "+('On ' if CONFIGURATION['follow']  else 'Off ') , color)
        scr.addch(curses.ACS_VLINE, color)
        scr.addstr(" [F5] Toggle %s view "%('list' if CONFIGURATION['tree'] else 'tree'), color)
        scr.addch(curses.ACS_VLINE, color)

        # Fold control
        if CONFIGURATION['tree']:
            scr.addstr(" [+/-] %s "%('unfold' if selected.get('cgroup', '') in CONFIGURATION['fold'] else 'fold'), color)
            scr.addch(curses.ACS_VLINE, color)

        # Do we have any actions available for *selected* line ?
        selected_type = selected.get('type', '')
        if selected_type == 'docker' and HAS_DOCKER or \
           selected_type in ['lxc', 'lxc-user'] and HAS_LXC or \
           selected_type == 'qemu-kvm' and HAS_LIBVIRT or \
           selected_type == 'openvz' and HAS_OPENVZ:
             if selected_type == 'openvz':
                scr.addstr(" [A]ttach, [E]nter, [S]top, [C]hkpnt, [K]ill ", color)
             elif selected_type == 'qemu-kvm':
                scr.addstr(" [A]ttach, [S]top, [K]ill ", color)
             else:
                scr.addstr(" [A]ttach, [E]nter, [S]top, [K]ill ", color)
             scr.addch(curses.ACS_VLINE, color)

        scr.addstr(" [Q]uit", color)
    except _curses.error:
        # Handle narrow screens
        pass

    scr.refresh()

def set_sort_col(sort_by):
    if CONFIGURATION['sort_by'] == sort_by:
        CONFIGURATION['sort_asc'] = not CONFIGURATION['sort_asc']
    else:
        CONFIGURATION['sort_by'] = sort_by

def on_keyboard(c):
    '''Handle keyborad shortcuts'''
    if c == ord('q'):
        raise KeyboardInterrupt()
    elif c == ord('p'):
        CONFIGURATION['pause_refresh'] = not CONFIGURATION['pause_refresh']
    elif c == ord('f'):
        CONFIGURATION['follow'] = not CONFIGURATION['follow']
        return 2
    elif c == 269: # F5
        CONFIGURATION['tree'] = not CONFIGURATION['tree']
        return 2
    elif c == curses.KEY_DOWN:
        if CONFIGURATION['follow']:
            i = CONFIGURATION['cgroups'].index(CONFIGURATION['selected_line_name'])
        else:
            i = CONFIGURATION['selected_line_num']
        i = min(i+1, len(CONFIGURATION['cgroups'])-1)
        CONFIGURATION['selected_line_num'] = i
        CONFIGURATION['selected_line_name'] = CONFIGURATION['cgroups'][i]
        return 2
    elif c == curses.KEY_UP:
        if CONFIGURATION['follow']:
            i = CONFIGURATION['cgroups'].index(CONFIGURATION['selected_line_name'])
        else:
            i = CONFIGURATION['selected_line_num']
        i = max(i-1, 0)
        CONFIGURATION['selected_line_num'] = i
        CONFIGURATION['selected_line_name'] = CONFIGURATION['cgroups'][i]
        return 2
    elif CONFIGURATION['selected_line'] is None:
        # All following lines expect a valid selected line
        return 2
    elif c == ord('+') or c == ord('-'):
        cgroup = CONFIGURATION['selected_line']['cgroup']
        if cgroup in CONFIGURATION['fold']:
            CONFIGURATION['fold'].remove(cgroup)
        else:
            CONFIGURATION['fold'].append(cgroup)
        return 2
    elif c == ord('a'):
        selected = CONFIGURATION['selected_line']
        selected_name = os.path.basename(selected['cgroup'])

        if selected['type'] == 'docker' and HAS_DOCKER:
            if selected_name.startswith('docker-'):
                selected_name = selected_name[7:-6]
            run(-2, ['docker', 'attach', selected_name], interactive=True)
        elif selected['type'] in ['lxc', 'lxc-user'] and HAS_LXC:
            run(selected['owner'], ['lxc-console', '--name', selected_name, '--', '/bin/bash'], interactive=True)
        elif selected['type'] == 'openvz' and HAS_OPENVZ:
            run(selected['owner'], ['vzctl', 'console', selected_name], interactive=True)
        elif selected['type'] == 'qemu-kvm' and HAS_LIBVIRT:
            run(selected['owner'], ['virsh', 'console', libvirt_vm_name(selected['cgroup']) ], interactive=True)

        return 2
    elif c == ord('e'):
        selected = CONFIGURATION['selected_line']
        selected_name = os.path.basename(selected['cgroup'])

        if selected['type'] == 'docker' and HAS_DOCKER:
            if selected_name.startswith('docker-'):
                selected_name = selected_name[7:-6]
            run(-2, ['docker', 'exec', '-it', selected_name, '/bin/bash'], interactive=True)
        elif selected['type'] in ['lxc', 'lxc-user'] and HAS_LXC:
            run(selected['owner'], ['lxc-attach', '--name', selected_name, '--', '/bin/bash'], interactive=True)
        elif selected['type'] == 'openvz' and HAS_OPENVZ:
            run(selected['owner'], ['vzctl', 'enter', selected_name], interactive=True)

        return 2
    elif c == ord('s'):
        selected = CONFIGURATION['selected_line']
        selected_name = os.path.basename(selected['cgroup'])

        if selected['type'] == 'docker' and HAS_DOCKER:
            if selected_name.startswith('docker-'):
                selected_name = selected_name[7:-6]
            run(-2, ['docker', 'stop', selected_name])
        elif selected['type'] in ['lxc', 'lxc-user'] and HAS_LXC:
            run(selected['owner'], ['lxc-stop', '--name', selected_name, '--nokill', '--nowait'])
        elif selected['type'] == 'openvz' and HAS_OPENVZ:
            run(selected['owner'], ['vzctl', 'stop', selected_name])
        elif selected['type'] == 'qemu-kvm' and HAS_LIBVIRT:
            run(selected['owner'], ['virsh', 'shutdown', libvirt_vm_name(selected['cgroup']) ])

        return 1
    elif c == ord('c'):
        selected = CONFIGURATION['selected_line']
        selected_name = os.path.basename(selected['cgroup'])

        if selected['type'] == 'openvz' and HAS_OPENVZ:
            run(selected['owner'], ['vzctl', 'chkpnt', selected_name])

        return 1
    elif c == ord('k'):
        selected = CONFIGURATION['selected_line']
        selected_name = os.path.basename(selected['cgroup'])

        if selected['type'] == 'docker' and HAS_DOCKER:
            if selected_name.startswith('docker-'):
                selected_name = selected_name[7:-6]
            run(-2, ['docker', 'stop', '-t', '0', selected_name])
        elif selected['type'] in ['lxc', 'lxc-user'] and HAS_LXC:
            run(selected['owner'], ['lxc-stop', '-k', '--name', selected_name, '--nowait'])
        elif selected['type'] == 'openvz' and HAS_OPENVZ:
            run(selected['owner'], ['vzctl', 'stop', selected_name, '--fast'])
        elif selected['type'] == 'qemu-kvm' and HAS_LIBVIRT:
            run(selected['owner'], ['virsh', 'destroy', libvirt_vm_name(selected['cgroup']) ])

        return 2
    return 1

def on_mouse():
    '''Update selected line / sort'''
    _, x, y, z, bstate =  curses.getmouse()

    # Left button click ?
    if bstate & curses.BUTTON1_CLICKED:
        # Is it title line ?
        if y == 0:
            # Determine sort column based on offset / col width
            x_max = 0
            for col in COLUMNS:
                if not col.width:
                    set_sort_col(col.col_sort)
                elif x < x_max+col.width:
                    set_sort_col(col.col_sort)
                else:
                    x_max += col.width + 1
                    continue
                return 2
        # Is it a cgroup line ?
        elif y <= len(CONFIGURATION['cgroups']):
            if CONFIGURATION['follow']:
                CONFIGURATION['selected_line_name'] = CONFIGURATION['cgroups'][y-1]
            else:
                CONFIGURATION['selected_line_num'] = y-1
            return 2
    return 1

def on_resize():
    '''Redraw screen, do not refresh'''
    return 2

def event_listener(scr, timeout):
    '''
    Wait for curses events on screen ``scr`` at mot ``timeout`` ms

    return
     - 1 OK
     - 2 redraw
     - 0 error
    '''
    try:
        scr.timeout(timeout)
        c = scr.getch()
        if c == -1:
            return 1
        elif c == curses.KEY_MOUSE:
            return on_mouse()
        elif c == curses.KEY_RESIZE:
            return on_resize()
        else:
            return on_keyboard(c)
    except _curses.error:
        return 0

def rebuild_columns():
    del COLUMNS[:]
    for col in CONFIGURATION['columns']+COLUMNS_MANDATORY:
        COLUMNS.append(COLUMNS_AVAILABLE[col])

def diagnose():
    devnull = open(os.devnull, 'w')
    if os.path.isfile('/.dockerenv'):
        print("""
Hint: It seems you are running inside a Docker container.
      Please make sure to expose host's cgroups with
      '--volume=/sys/fs/cgroup:/sys/fs/cgroup:ro'""", file=sys.stderr)

    if cmd_exists('boot2docker'):
        print("""
Hint: It seems you have 'boot2docker' installed.
      To monitor Docker containers in 'boot2docker'
      run CTOP inside the VM itself with:
      $ docker run --volume=/sys/fs/cgroup:/sys/fs/cgroup:ro -it --rm yadutaf/ctop""", file=sys.stderr)
    devnull.close()

def init_screen():
    curses.start_color() # load colors
    curses.use_default_colors()
    curses.noecho()      # do not echo text
    curses.cbreak()      # do not wait for "enter"
    curses.mousemask(curses.ALL_MOUSE_EVENTS)

    # Hide cursor, if terminal AND curse supports it
    if hasattr(curses, 'curs_set'):
        try:
            curses.curs_set(0)
        except:
            pass

def main():
    # Parse arguments
    parser = OptionParser()
    parser.add_option("--tree",     action="store_true",                default=False, help="show tree view by default")
    parser.add_option("--refresh",  action="store",      type="int",    default=1,     help="Refresh display every <seconds>")
    parser.add_option("--follow",   action="store",      type="string", default="",    help="Follow cgroup path")
    parser.add_option("--fold",     action="append",                                   help="Fold cgroup sub tree")
    parser.add_option("--type",     action="append",                                   help="Only show containers of this type")
    parser.add_option("--columns",  action="store",      type="string", default="owner,type,processes,memory,cpu-sys,cpu-user,blkio,cpu-time", help="List of optional columns to display. Always includes 'name'")
    parser.add_option("--sort-col", action="store",      type="string", default="cpu-user", help="Select column to sort by initially. Can be changed dynamically.")

    options, args = parser.parse_args()

    CONFIGURATION['tree'] = options.tree
    CONFIGURATION['refresh_interval'] = float(options.refresh)
    CONFIGURATION['columns'] = []
    CONFIGURATION['fold'] = options.fold or list()
    CONFIGURATION['type'] = options.type or list()

    if options.follow:
        CONFIGURATION['selected_line_name'] = options.follow
        CONFIGURATION['follow'] = True

    for col in options.columns.split(','):
        col = col.strip()
        if col in COLUMNS_MANDATORY:
            continue
        if not col in COLUMNS_AVAILABLE:
            print("Invalid column name", col, file=sys.stderr)
            print(__doc__)
            sys.exit(1)
        CONFIGURATION['columns'].append(col)
    rebuild_columns()

    if options.sort_col not in COLUMNS_AVAILABLE:
        print("Invalid sort column name", options.sort_col, file=sys.stderr)
        print(__doc__)
        sys.exit(1)
    CONFIGURATION['sort_by'] = COLUMNS_AVAILABLE[options.sort_col].col_sort

    # Initialization, global system data
    measures = {
        'data': defaultdict(dict),
        'global': {
            'total_cpu': multiprocessing.cpu_count(),
            'total_memory': get_total_memory(),
            'scheduler_frequency': os.sysconf('SC_CLK_TCK'),
        }
    }

    init()

    if not CGROUP_MOUNTPOINTS:
        print("[ERROR] Failed to locate cgroup mountpoints.", file=sys.stderr)
        diagnose()
        sys.exit(1)

    results = None

    try:
        # Curse initialization
        stdscr = curses.initscr()
        init_screen()
        stdscr.keypad(1)     # parse keypad control sequences

        # Curses colors
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_GREEN) # header
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)  # focused header / line
        curses.init_pair(3, curses.COLOR_WHITE, -1)  # regular
        curses.init_pair(4, curses.COLOR_CYAN,  -1)  # tree

        # Main loop
        while True:
            collect(measures)
            results = built_statistics(measures, CONFIGURATION)
            display(stdscr, results, CONFIGURATION)
            sleep_start = time.time()
            while CONFIGURATION['pause_refresh'] or time.time() < sleep_start + CONFIGURATION['refresh_interval']:
                if CONFIGURATION['pause_refresh']:
                    to_sleep = -1
                else:
                    to_sleep = int((sleep_start + CONFIGURATION['refresh_interval'] - time.time())*1000)
                ret = event_listener(stdscr, to_sleep)
                if ret == 2:
                    display(stdscr, results, CONFIGURATION)
    except KeyboardInterrupt:
        pass
    finally:
        curses.nocbreak()
        stdscr.keypad(0)
        curses.echo()
        curses.endwin()

    # If we found only root cgroup, me may be expecting to run in a boot2docker instance
    if results is not None and len(results) < 2:
        print("[WARN] Failed to find any relevant cgroup/container.", file=sys.stderr)
        diagnose()

if __name__ == "__main__":
    main()