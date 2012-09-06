import sublime
import sublime_plugin

s_archive_separator = '-' * 30 + ' archive ' + '-' * 30


# ------------------------------------------------------------------------
# Helper Functions for dealing with dicts of lists
# ------------------------------------------------------------------------
def AddItemToPile(item, pile, data):
    '''Add item to a pile (a list in a dict)'''
    if pile in data:
        data[pile].append(item)
    else:
        data[pile] = [item]
    return data


def RemoveItemFromPile(item, pile, data):
    '''Removes an item from a pile (a list in a dict)'''
    data[pile].remove(item)
    if not data[pile]:
        del data[pile]
    return data


def AllPilesContainingItem(item, data):
    '''Return list of all piles containing the item'''
    piles = []
    for pname, pcont in data.items():
        if item in pcont:
            piles.append(pname)
    piles.sort()
    return piles


# ------------------------------------------------------------------------
# Actual Todo-list Stuff
# ------------------------------------------------------------------------
def RemoveTags(s):
    '''Remove all tags from a string'''
    new_words = []
    for word in s.split(' '):
        if not word.startswith(('@', '.')):
            new_words.append(word)
    return ' '.join(new_words)


def FormatTag(tag, kind, target='header'):
    '''Format tag for use as header or inline tag'''

    # remove the prefix for now, if there is one
    if tag.startswith(('@', '.')):
        tag = tag[1:]

    # determine format
    if tag.find('_') > -1:
        format = 'tag'
    elif tag[0].islower():
        format = 'tag'
    else:
        format = 'header'

    # reformat
    if target == 'header':
        if target == format:
            new_tag = tag
        else:
            new_words = []
            for word in tag.split('_'):
                new_words.append(word.capitalize())
            new_tag = " ".join(new_words)

        prefix = {'project': '', 'context': '@'}

    elif target == 'tag':
        if target == format:
            new_tag = tag
        else:
            new_words = []
            for word in tag.split(' '):
                new_words.append(word.lower())
            new_tag = "_".join(new_words)

        prefix = {'project': '.', 'context': '@'}

    return prefix[kind] + new_tag


def DetermineSortMode(s):
    mode = None
    count = -1
    lines = s.split('\n')
    while mode is None:
        count += 1
        if lines[count].startswith('# @'):
            mode = 'context'
        elif lines[count].startswith('# '):
            mode = 'project'
        else:
            pass
    return mode


def ParseTodoLine(line, mode, current_head):
    '''Parse a single line from a todo file into a list'''

    if line == '':
        item = None

    elif line.startswith('# @'):
        item = None
        mode = 1
        current_head = line[2:]

    elif line.startswith('# '):
        item = None
        mode = 0
        current_head = line[2:]

    else:
        proj = []
        cont = []
        done = False

        # save header info
        if current_head != '':
            if mode == 0:
                proj.append(FormatTag(current_head, 'project', 'tag'))
            else:
                cont.append(FormatTag(current_head, 'context', 'tag'))

        # save done status info
        if line.startswith('x '):
            done = True

        # save tag info
        for word in line.split(' '):
            if word.startswith('.'):
                # saving _formatted_ tag to allow for dup check
                proj.append(FormatTag(word[1:], 'project', 'tag'))
            elif word.startswith('@'):
                # saving _formatted_ tag to allow for dup check
                cont.append(FormatTag(word[1:], 'context', 'tag'))

        # sort and remove duplicaes
        proj = list(set(proj))
        cont = list(set(cont))
        proj.sort()
        cont.sort()

        item = RemoveTags(line), proj, cont, done

    return item, mode, current_head


def ParseTodoBlock(b):
    '''Parse a todo block into a dict of dicts of strings and lists'''

    # parse lines into touples
    items = []
    current_head = ''
    mode = 0  # 0 if headings are projects, 1 if headings are contexts
    for line in b.split('\n'):
        item, mode, current_head = ParseTodoLine(line, mode, current_head)
        if item is not None:
            items.append(item)

    # throw items into containers and get rid of duplicates
    fulltexts = {}
    contexts = {}
    projects = {}
    donemarks = {}
    count = 0
    seen = []
    for full, proj, cont, done in items:
        toup = full, proj, cont, done
        if toup not in seen:
            fulltexts[count] = full
            donemarks[count] = done
            if proj == []:
                AddItemToPile(count, 0, projects)
            else:
                for pro in proj:
                    AddItemToPile(count, pro, projects)
            if cont == []:
                AddItemToPile(count, 0, contexts)
            else:
                for con in cont:
                    AddItemToPile(count, con, contexts)

            seen.append(toup)
        count += 1

    return {'fulltexts': fulltexts, 'projects': projects, 'contexts': contexts, 'donemarks': donemarks}


def ParseTodoList(d):
    '''Parse a todolist into a list of dicts of dicts of strings and lists'''

    blocks = []
    for block in d.split(s_archive_separator):
        blocks.append(ParseTodoBlock(block))

    return blocks


def ArchiveItems(d):
    '''Move done items to archive block'''

    # determine highest archive id in archive block
    archive_keys = d[1]['fulltexts'].keys()
    archive_id = 0
    if archive_keys:
        archive_id = max(archive_keys)

    # remove done items from main block and attach to archive block
    for main_id, done in d[0]['donemarks'].items():
        if done == True:
            archive_id += 1
            for key in ['donemarks', 'fulltexts']:
                d[1][key][archive_id] = d[0][key].pop(main_id)
            for key in ['projects', 'contexts']:
                for tag in AllPilesContainingItem(main_id, d[0][key]):
                    RemoveItemFromPile(main_id, tag, d[0][key])
                    AddItemToPile(archive_id, tag, d[1][key])

    return d


def FormatTodoList(d, mode='project'):
    '''Print todolist from parsed data'''

    s = ''

    for i, block in enumerate(d):
        if mode == 'project':
            head = block['projects']
        elif mode == 'context':
            head = block['contexts']

        if i == 1:
            s += s_archive_separator + '\n' * 2

        for current_head, todos in sorted(head.items()):
            if current_head != 0:
                s += "# {0}\n".format(FormatTag(current_head, mode, 'header'))
            for todo in sorted(todos):
                tags = AllPilesContainingItem(todo, block['projects'])
                tags += AllPilesContainingItem(todo, block['contexts'])
                tags.remove(current_head)
                if 0 in tags:
                    tags.remove(0)
                s += block['fulltexts'][todo].strip() + ' ' + ' '.join(tags) + '\n'
            s += "\n"

    return s.strip("\n")


# ------------------------------------------------------------------------
# Sublime Commands
# ------------------------------------------------------------------------
class ReorderTodosByProjectCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        total = sublime.Region(0, self.view.size())
        body = self.view.substr(total)
        parsed = ParseTodoList(body)
        formatted = FormatTodoList(parsed, 'project')
        self.view.replace(edit, total, formatted)


class ReorderTodosByContextCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        total = sublime.Region(0, self.view.size())
        body = self.view.substr(total)
        parsed = ParseTodoList(body)
        formatted = FormatTodoList(parsed, 'context')
        self.view.replace(edit, total, formatted)


class ArchiveCompletedTodosCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        total = sublime.Region(0, self.view.size())
        body = self.view.substr(total)
        parsed = ParseTodoList(body)
        mode = DetermineSortMode(body)
        parsed = ArchiveItems(parsed)
        formatted = FormatTodoList(parsed, mode)
        self.view.replace(edit, total, formatted)
