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

--

可能目录A复制为B, svndump只记录B, 而 B/* 没有记录, 而后来又某文件依赖B/x 
从而造成错误; 需要在复制目录时,产生所有文件的引用记录;
删除目录时, svndump也没有记载其下每个文件都应该删除;
在有大量分支和标签时,计算量很大;

可能某些文件是因目录copy而产生, 然后单独 delete
这样就没有单独的 node-action: add 可过滤, 
而只过滤掉 delete 动作, 造成保留不应保留的文件

// svnadmin dump 没有根据 sha1 重复排除重复文件

改用 sha1 计算应该排除的文件,
但仍然不能解决目录复制和删除的计算量问题;

TODO: 需要设计一个虚拟的 svn 仓库对象, 才能实现 0 成本目录复制删除;

TODO: 过滤过程会产生一些空提交, 考虑删除;



"""

import io
import re
import sys
import collections

class read_dumpfile():
    def __init__(self, filename):
        self.f = io.open(filename, 'rb');
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
            prop = '';
            bytes = '';
            if('Prop-content-length' in header):
                assert 'Content-length' in header;
                len1 = int(header['Prop-content-length']);
                len2 = int(header['Content-length']);
                assert(len1 <= len2);
                prop = self.f.read(len1);
                #print prop
                bytes = self.f.read(len2 - len1);
                #print len(bytes);
            callback(header, header_str, prop, bytes);

def print_info(header, header_str, prop, bytes):
    print header
    print header_str

def dump(f, header, header_str, prop, bytes):
    # 试验产生的dump文件略有差别(换行符), 但 load 后 co 正常,内容相同
    f.write(header_str);
    f.write(prop);
    f.write(bytes);
    f.write('\n');

def parent_path(j):
    ret = [];
    dirs = j.split('/');
    for k in range(0, len(dirs)):
        ret.append(str.join('/', dirs[0:k+1]));
    return ret;

def is_in_dir(i, dir):
    return i[0:len(dir)+1]==dir+'/'

class write_dumpfile():
    def __init__(self, filename):
        self.f = io.open(filename, 'wb');
        self.depends = collections.defaultdict(lambda:{});
    def write_test_filter(self, header, header_str, prop, bytes):
        # 简单的 filter, 正确;
        if('Node-path' in header and header['Node-path']=='1/tmp1.bmp'):
            return;
        dump(self.f, header, header_str, prop, bytes);
    def minimize_record(self, header, header_str, prop, bytes):        
        if('Node-action' in header and header['Node-action']=='delete'):
            path = header['Node-path'];
            assert path in self.depends;
            del self.depends[path];
            for i in self.depends.copy():
                if(is_in_dir(i, path)):
                    del self.depends[i];
            return;
        if('Node-path' in header):
            path = header['Node-path'];
            self.depends[path][path] = 1;
            if('Node-copyfrom-path' in header):
                path_from = header['Node-copyfrom-path'];
                self.depends[path][path_from]=1;
                assert path_from in self.depends;
                for i in self.depends[path_from]:
                    self.depends[path][i]=1;
                if(header['Node-kind']=='dir'):
                    for i in self.depends.copy():
                        if(is_in_dir(i, path_from)):
                            for j in self.depends[i]:
                                self.depends[path+i[len(path_from):]][j] = 1;
    def minimize_calc_filter(self):
        self.keep = {};
        for i in self.depends:
            for j in self.depends[i]:
                # 保留文件的父目录也需要保留
                for k in parent_path(j):
                    self.keep[k] = 1;
        for i in self.keep:
            print "keep", i;
        self.status = collections.defaultdict(lambda:"");
    def minimize_write(self, header, header_str, prop, bytes):
        if('Node-path' in header and not(header['Node-path'] in self.keep)):
            if(self.status[header['Node-path']]=='' and header['Node-action']=='delete'):
                # 随目录copy而产生, 没有单独的 Node-action: add
                #  不应过滤
                dump(self.f, header, header_str, prop, bytes);
                return;
            self.status[header['Node-path']] = header['Node-action'];
            print "ignore", header['Node-path'];
            return;
        dump(self.f, header, header_str, prop, bytes);

#根据 sha1 过滤
#class write_dumpfile():
#    def __init__(self, filename):
#        self.f = io.open(filename, 'wb');
#        self.sha1 = collections.defaultdict(lambda:{});
#    def minimize_record(self, header, header_str, prop, bytes):
#        if('Text-content-sha1' in header):
#            sha1 = header['Text-content-sha1'];
#            self.sha1[header['Node-path']][sha1] = 1;
#            return;
#        if('Text-copy-source-sha1' in header):
#            sha1 = header['Text-copy-source-sha1'];
#            self.sha1[header['Node-path']][sha1] = 1;
#            return;
#        if('Node-action' in header and header['Node-action']=='delete'):
#            path = header['Node-path'];
#            # 遍历子目录文件
#            for i in self.sha1.copy():
#                if(is_in_dir(i, path)):
#                    del self.sha1[i];
#            return;
#        # 目录复制
#        assert 0, 'not implemented yet'
#        pass
#    def minimize_calc_filter(self):
#        assert 0, 'not implemented yet'
#    def minimize_write(self, header, header_str, prop, bytes):
#        assert 0, 'not implemented yet'

#模拟svn仓库
#class write_dumpfile():
#    def __init__(self, filename):
#        self.f = io.open(filename, 'wb');
#    def minimize_record(self, header, header_str, prop, bytes):
#        pass
#    def minimize_calc_filter(self):
#        pass
#    def minimize_write(self, header, header_str, prop, bytes):
#        pass

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


