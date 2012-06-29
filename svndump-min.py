# -*- coding:gb18030
"""
�� SVN DUMP �ļ���ɾ�������������ļ�, ʹ�������С���Ĺ���

KEYWORDS: svndump minimize compress clean
ABSTRACT: 
  remove all junk (or confidential ) files from the svndump file,
    according to the latest status of the depository;

������״̬Ϊ׼, ���������ձ����ļ���ص���ʷ�ļ���������, ����ɾ��;
EXAMPLE:
�ļ� /a/b.txt, ������Ϊ /a/b1.txt, ����ʷ��Ӧ���� /a/b.txt /a/b1.txt
�ļ� /a/b.txt, ������Ϊ /a/b1.txt, ���ɾ��; ����ʷ��Ӧɾ�� /a/b.txt /a/b1.txt
��� /a ��ɾ���� ���ύ���µ��޹ص� /a, ����ʷ�еĵ�һ�� /a ��Ȼ������;

ʹ��svn������,�������������ύһЩ .obj .pch ֮�������ļ�,
(���߿����������ļ�,��Ҫ����ʷ�г���ɾ��)
���е� svndumpfilter.exe ��Ҫ�����ṩ·���б�������, �Ƚ��鷳;

�����Ƚ������ļ�ɾ��, Ȼ���ύsvn.
Ȼ�� svnadmin dump �õ� dump �ļ�,
ִ�б�������й���, �õ��� dump �ļ���С,
Ȼ�� svnadmin create; svnadmin load; �õ��µĸɾ��Ŀ�;




"""

import io
import re
import sys
import json
import string

##################

def print_info(header, header_str, prop, bytes):
    if('Revision-number' in header):
        print >>sys.stderr, 'rev', header['Revision-number'] # show progress
    print header_str

def dump(f, header, header_str, prop, bytes):
    # ���������dump�ļ����в��(���з�), �� load �� co ����,������ͬ
    f.write(header_str);
    f.write(prop);
    f.write(bytes());
    f.write('\n');

def parent_path(j):
    ret = [];
    dirs = j.split('/');
    for k in range(0, len(dirs)):
        ret.append(str.join('/', dirs[0:k+1]));
    return ret;

def read_file(f, pos, len):
    f.seek(pos);
    return f.read(len);



#############


class read_dumpfile():
    def __init__(self, file):
        self.f = io.open(file, 'rb') if isinstance(file,str) else file;
    def read_header(self):
        header = {};
        header_str = '';
        while 1:
            s = self.f.readline();
            if(s==''):
                return header,header_str;
            if(s!='\n'):
                break;
        while 1:
            header_str += s;
            r = re.match('^(\S+):\s+(.*)$', s);
            if r==None:
                assert s=='\n';
                return header, header_str;
            header[r.group(1)] = r.group(2);
            s = self.f.readline();
    def parse(self, callback):
        while 1:
            header,header_str = self.read_header();
            if header=={}:
                assert self.f.readline()=='' ;
                break;
            len1 = 0;
            len2 = 0;
            if('Prop-content-length' in header):
                len1 = int(header['Prop-content-length']);
                len2 = len1
            if('Content-length' in header):
                len2 = int(header['Content-length']);
            assert(len1 <= len2);
            prop = self.f.read(len1);
            tell = self.f.tell();
            # to speed up, ignore big data reading if possible
            bytes = lambda: read_file(self.f, tell, len2 - len1);
            callback(header, header_str, prop, bytes);
            self.f.seek(tell + len2 - len1);

class svn_item:
    def __init__(self, init):
        # ���дȱʡֵ���� init={'files':{}}, ���� {} �ᱻʵ���临��,
        self.__dict__ = init;

#ģ��svn�ֿ�
class svn_db():
    def __init__(self):
        self.items = {};
        self.current_rev = 0;
    def do_add_change_replace(self, path):
        if(path not in self.items):
            # �����ж��copy����ָ��һ���ط�,ȫ������
            self.items[path] = svn_item({'files':{}, 'copy_from':{}, 'del_at':None, 'keep':False});
        self.items[path].del_at = None;
        parent_dir = string.join(path.split('/')[:-1], '/')
        assert path.startswith(parent_dir);
        if(parent_dir != ''):
            assert parent_dir in self.items, parent_dir+" not exists";
            self.items[parent_dir].files[path] = 1;
    def do_copy_from(self, path, path_from, from_rev):
        assert path_from in self.items;
        self.do_add_change_replace(path);
        self.items[path].copy_from[path_from] = 1;
        for i in self.items[path_from].files.copy():
            assert i.startswith(path_from);
            if(self.items[i].del_at != None and self.items[i].del_at < from_rev):
                continue;
            f = path + i[len(path_from):];
            self.do_copy_from(f, i, from_rev); # ����ݹ�
    def do_del(self, path):
        assert path in self.items, path+" not exists";
        assert self.items[path].del_at == None or self.items[path].del_at == self.current_rev;
        self.items[path].del_at = self.current_rev;
        for i in self.items[path].files:
            if(self.items[i].del_at != None):
                continue;
            self.do_del(i);
    def exists(self, path):
        if(path not in self.items):
            return False;
        if(self.items[path].del_at != None):
            return False;
        return True;
    def keep(self, path):
        if(self.items[path].keep):
            return;
        self.items[path].keep = True;
        parent_dir = string.join(path.split('/')[:-1], '/')
        if(parent_dir != ''):
            self.keep(parent_dir);
        for i in self.items[path].copy_from:
            self.keep(i);
    def calc_keep(self):
        for i in self.items:
            if(self.items[i].del_at == None):
                self.keep(i);
    def handle(self, header, header_str, prop, bytes):
        if('Revision-number' in header):
            self.current_rev = int(header['Revision-number'])
            print >>sys.stderr, 'rev', self.current_rev # show progress
        if('Node-action' in header and header['Node-action']=='delete'):
            self.do_del(header['Node-path']);            
            return;
        if('Node-path' in header):
            if('Node-copyfrom-path' in header):
                # �п��ܴ�һ����ɾ����rev�и���, ָ����С�� copyfrom-rev
                self.do_copy_from(header['Node-path'], header['Node-copyfrom-path'], \
                    int(header['Node-copyfrom-rev']));
            else:
                self.do_add_change_replace(header['Node-path']);


class calc():
    def __init__(self, filename):
        self.svn = svn_db();
        self.f = io.open(filename, "wb");
    def record(self, header, header_str, prop, bytes):
        self.svn.handle(header, header_str, prop, bytes);
    def __del__(self):
        self.svn.calc_keep();
        self.f.write(json.dumps(self.svn.items, indent=1, default=lambda x:x.__dict__));

class filter():
    def __init__(self, filename, output):
        self.items = json.loads(io.open(filename, "rb").read(-1));
        self.svn2 = svn_db();
        self.output = io.open(output,"wb") if isinstance(output, str) else output
    def write(self, header, header_str, prop, bytes):
        if('Node-path' in header and not self.items[header['Node-path'].decode('utf-8')]['keep']):
            # ��Ŀ¼copy������, û�е����� Node-action: add  ��Ӧ����
            # ���п����临����Դ�Ѿ�������, ���� svnadmin load ����;
            # ��˹���֮���Ե��� recrod ģ��, �ж��ļ��Ƿ���
            if(self.svn2.exists(header['Node-path'])):
                print >> sys.stderr, "del-ignore", header['Node-path'].decode('utf-8');
                self.svn2.handle(header, header_str, prop, bytes);
                dump(self.output, header, header_str, prop, bytes);
                return;
            print >> sys.stderr, "ignore", header['Node-path'].decode('utf-8');
            return;
        self.svn2.handle(header, header_str, prop, bytes);
        dump(self.output, header, header_str, prop, bytes);


def main():
    if(len(sys.argv) in [2,3] and sys.argv[1]=='list'):
        read_dumpfile(sys.stdin if len(sys.argv)==2 else sys.argv[2]).parse(print_info);
    elif(len(sys.argv)==4 and sys.argv[1]=='calc'):
        read_dumpfile(sys.argv[2]).parse(calc(sys.argv[3]).record);
    elif(len(sys.argv) in [4,5] and sys.argv[1]=='filter'):
        read_dumpfile(sys.argv[2]).parse(\
            filter(sys.argv[3], sys.stdout if len(sys.argv)==4 else sys.argv[4]).write);
    else:
        print >> sys.stderr, "USAGE: python -u svndump-min.py list < from.dump"
        print >> sys.stderr, "USAGE: svndump-min.py list from.dump"
        print >> sys.stderr, "USAGE: svndump-min.py calc from.dump inc.txt"
        print >> sys.stderr, "USAGE: python -u svndump-min.py filter from.dump inc.txt > to.dump"

if __name__ == "__main__" :
    main();


