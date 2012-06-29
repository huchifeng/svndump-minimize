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

--

����Ŀ¼A����ΪB, svndumpֻ��¼B, �� B/* û�м�¼, ��������ĳ�ļ�����B/x 
�Ӷ���ɴ���; ��Ҫ�ڸ���Ŀ¼ʱ,���������ļ������ü�¼;
ɾ��Ŀ¼ʱ, svndumpҲû�м�������ÿ���ļ���Ӧ��ɾ��;
���д�����֧�ͱ�ǩʱ,�������ܴ�;

����ĳЩ�ļ�����Ŀ¼copy������, Ȼ�󵥶� delete
������û�е����� node-action: add �ɹ���, 
��ֻ���˵� delete ����, ��ɱ�����Ӧ�������ļ�

// svnadmin dump û�и��� sha1 �ظ��ų��ظ��ļ�

���� sha1 ����Ӧ���ų����ļ�,
����Ȼ���ܽ��Ŀ¼���ƺ�ɾ���ļ���������;

��Ҫ���һ������� svn �ֿ����, ����ʵ�� 0 �ɱ�Ŀ¼����ɾ��;
���ձ�����һ�������������Ĺ���, ���Ӷ����ٺ�����״̬�ļ���������, 
����ߵĵط����ڸ��ƺ�ɾ������ʱ,���ر���ȫ���ڵ�(���Ա��������ڵ�);
ʹ�����ṹtree����ƽ�̵�map����ʵ��.
û��ʵ��0�ɱ�����ɾ��,�����Ӷ�Ӧ���ѿɽ���.

��ֱ�ӹ��� dump �ļ�,��Ϊ����һ����� include �б�,
Ȼ�� svnadmin dump | svndumpfilter include --drop-empty-revs --targets inc.txt ��ִ��;

TODO: ���˹��̻����һЩ���ύ, ����ɾ��;



"""

import io
import re
import sys

def read_file(f, pos, len):
    f.seek(pos);
    return f.read(len);
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

def is_in_dir(i, dir):
    return i[0:len(dir)+1]==dir+'/'

#ģ��svn�ֿ�
class svn_item():
    def __init__(self):
        self.items = {};
        self.depends = {};
        self.mark_del = False;
        self.path = "";
    def get_item(self, name):
        if(name not in self.items):
            item = svn_item();
            item.path = self.path + ("/" if self.path!="" else "") + name;
            item.depends[item.path] = 1;
            self.items[name] = item;
        return self.items[name];
    def get_recursive(self, path):
        path = path.split('/', 1);
        if(len(path)==1):
            return self.get_item(path[0]);
        return self.get_item(path[0]).get_recursive(path[1]);
    def remove_recursive(self, path):
        path = path.split('/', 1);
        if(path[0] not in self.items):
            return;
        if(len(path)==1):
            self.items[path[0]].mark_del = True;
            return;
        self.items[path[0]].remove_recursive(path[1]);
    def exists(self, path):
        path = path.split('/', 1);
        if(path[0] not in self.items):
            return False;
        if(self.items[path[0]].mark_del):
            return False;
        if(len(path)==1):
            return True;
        return self.items[path[0]].exists(path[1]);
    def copy_depends(self, src):
        for i in src.depends:
            self.depends[i]=1;
        for i in src.items:
            if(src.items[i].mark_del):
                continue;
            self.get_item(i).copy_depends(src.items[i]);        
    def make_filter(self, keep):
        for i in self.depends:
            for j in parent_path(i):
                keep[j] = 1;
        for i in self.items:
            if(self.items[i].mark_del):
                #print "ignore", self.items[i].path;
                continue;
            self.items[i].make_filter(keep);

class calc():
    def __init__(self, filename):
        self.root = svn_item();
        self.f = io.open(filename, "wb");        
    def record(self, header, header_str, prop, bytes):
        if('Revision-number' in header):
            print >>sys.stderr, 'rev', header['Revision-number'] # show progress
        if('Node-action' in header and header['Node-action']=='delete'):
            path = header['Node-path'];
            self.root.remove_recursive(path);            
            return;
        if('Node-path' in header):
            path = header['Node-path'];
            # ����ͬ�� rev ��, ��delete A, Ȼ�� B copy from A
            dst = self.root.get_recursive(path)
            dst.mark_del = False;
            if('Node-copyfrom-path' in header):
                path_from = header['Node-copyfrom-path'];
                src = self.root.get_recursive(path_from)
                dst.depends[path_from]=1;
                dst.copy_depends(src);
    def __del__(self):
        self.keep = {};
        self.root.make_filter(self.keep);
        for i in sorted(self.keep.keys()):
            print >> sys.stderr, "keep", i.decode('utf-8');
            self.f.write(i+"\n");
class filter():
    def __init__(self, filename):
        self.keep = {};
        for i in io.open(filename, "rb"):
            self.keep[re.sub('^\s+|^/|\s+$', '', i)] = 1
    def write(self, header, header_str, prop, bytes):
        if('Node-path' in header and not(header['Node-path'] in self.keep)):
            # ��Ŀ¼copy������, û�е����� Node-action: add  ��Ӧ����
            # ���п����临����Դ�Ѿ�������, ���� svnadmin load ����;
            # ��˹���֮���Ե��� recrod ģ��, �ж��ļ��Ƿ���
            #if(self.calc.root.exists(header['Node-path'])):
            #    #print >> sys.stderr, "should-del", header['Node-path'].decode('utf-8');
            #    dump(sys.stdout, header, header_str, prop, bytes);
            #    #return;
            print >> sys.stderr, "ignore", header['Node-path'].decode('utf-8');
            return;
        dump(sys.stdout, header, header_str, prop, bytes);

def main():
    if(len(sys.argv) in [2,3] and sys.argv[1]=='list'):
        read_dumpfile(sys.stdin if len(sys.argv)==2 else sys.argv[2]).parse(print_info);
    elif(len(sys.argv)==4 and sys.argv[1]=='calc'):
        read_dumpfile(sys.argv[2]).parse(calc(sys.argv[3]).record);
    elif(len(sys.argv)==4 and sys.argv[1]=='filter'):
        read_dumpfile(sys.argv[2]).parse(filter(sys.argv[3]).write);
    else:
        print >> sys.stderr, "USAGE: python -u svndump-min.py list < from.dump"
        print >> sys.stderr, "USAGE: svndump-min.py list from.dump"
        print >> sys.stderr, "USAGE: svndump-min.py calc from.dump inc.txt"
        print >> sys.stderr, "USAGE: python -u svndump-min.py filter from.dump inc.txt > to.dump"

if __name__ == "__main__" :
    main();


