# -*- coding:gb18030
"""
从 SVN DUMP 文件中删除垃圾或敏感文件, 使其体积最小化的工具

KEYWORDS: svndump minimize compress clean
ABSTRACT: 
  remove all junk (or confidential ) files from the svndump file,
    according to the latest status of the depository;

以最终状态为准, 凡是与最终保留文件相关的历史文件都被保留, 否则被删除;
EXAMPLE:
文件 /a/b.txt, 被改名为 /a/b1.txt, 则历史中应保留 /a/b.txt /a/b1.txt
文件 /a/b.txt, 被改名为 /a/b1.txt, 随后被删除; 则历史中应删除 /a/b.txt /a/b1.txt
如果 /a 被删除后 又提交了新的无关的 /a, 则历史中的第一个 /a 仍然被保留;

使用svn过程中,经常可能有人提交一些 .obj .pch 之类垃圾文件,
(或者可能是敏感文件,需要从历史中彻底删除)
已有的 svndumpfilter.exe 需要自行提供路径列表来过滤, 比较麻烦;

可以先将垃圾文件删除, 然后提交svn.
然后 svnadmin dump 得到 dump 文件,
执行本程序进行过滤, 得到的 dump 文件较小,
然后 svnadmin create; svnadmin load; 得到新的干净的库;

TODO: 过滤过程会产生一些空提交, 考虑删除;



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
        # 试验产生的dump文件略有差别(换行符), 但 load 后 co 正常,内容相同
        self.f.write(str);
        self.f.write(prop);
        self.f.write(bytes);
        self.f.write('\n');
    def write_test_filter(self, p, str, prop, bytes):
        # 简单的 filter, 正确;
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


