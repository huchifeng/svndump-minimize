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

TODO: ���˹��̻����һЩ���ύ, ����ɾ��;



"""

import io
import re
import sys
import collections

class read_dumpfile():
    def __init__(self, filename):
        self.f = io.open(filename, 'rb');
    def read_para(self):
        ret = {};
        str = '';
        while 1:
            s = self.f.readline();
            if(s==''):
                return ret,str;
            if(s!='\n'):
                break;
        while 1:
            str += s;
            r = re.match('^(\S+):\s+(.*)$', s);
            if r==None:
                assert s=='\n';
                return ret, str;
            ret[r.group(1)] = r.group(2);
            s = self.f.readline();
    def parse(self, callback):
        while 1:
            p,str = self.read_para();
            if p=={}:
                assert self.f.readline()=='' ;
                break;
            prop = '';
            bytes = '';
            if('Prop-content-length' in p):
                assert 'Content-length' in p;
                len1 = int(p['Prop-content-length']);
                len2 = int(p['Content-length']);
                assert(len1 <= len2);
                prop = self.f.read(len1);
                #print prop
                bytes = self.f.read(len2 - len1);
                #print len(bytes);
            callback(p, str, prop, bytes);

def print_info(p, str, prop, bytes):
    print p
    print str

class write_dumpfile():
    def __init__(self, filename):
        self.f = io.open(filename, 'wb');
        self.depends = collections.defaultdict(lambda:{});
    def write(self, p, str, prop, bytes):
        # ���������dump�ļ����в��(���з�), �� load �� co ����,������ͬ
        self.f.write(str);
        self.f.write(prop);
        self.f.write(bytes);
        self.f.write('\n');
    def write_test_filter(self, p, str, prop, bytes):
        # �򵥵� filter, ��ȷ;
        if('Node-path' in p and p['Node-path']=='1/tmp1.bmp'):
            return;
        self.write(p, str, prop, bytes);
    def minimize_record(self, p, str, prop, bytes):
        if('Node-action' in p and p['Node-action']=='delete'):
            path = p['Node-path'];
            assert path in self.depends;
            del self.depends[path];
            return;
        if('Node-path' in p):
            path = p['Node-path'];
            self.depends[path][path] = 1;
            if('Node-copyfrom-path' in p):
                p1 = p['Node-copyfrom-path'];
                for i in self.depends[p1]:
                    self.depends[path][i]=1;
    def minimize_calc_filter(self):
        self.keep = {};
        for i in self.depends:
            for j in self.depends[i]:
                self.keep[j] = 1;
        for i in self.keep:
            print "keep", i;
    def minimize_write(self, p, str, prop, bytes):
        if('Node-path' in p and not(p['Node-path'] in self.keep)):
            print "ignore", p['Node-path'];
            return;
        self.write(p, str, prop, bytes)

def main():
    if(len(sys.argv)!=3):
        print "USAGE: svndump-min.py from.dump to.dump"
        return;
    #read_dumpfile(sys.argv[1]).parse(print_info);
    #read_dumpfile(sys.argv[1]).parse(write_dumpfile(sys.argv[2]).write_test_filter);
    dst = write_dumpfile(sys.argv[2]);
    read_dumpfile(sys.argv[1]).parse(dst.minimize_record);
    dst.minimize_calc_filter();
    read_dumpfile(sys.argv[1]).parse(dst.minimize_write);
    #raw_input();

if __name__ == "__main__" :
    main();


