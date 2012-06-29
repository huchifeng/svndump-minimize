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

需要设计一个虚拟的 svn 仓库对象, 才能实现 0 成本目录复制删除;
最终必须有一个产生白名单的过程, 复杂度至少和最终状态文件数成正比, 
能提高的地方在于复制和删除子树时,不必遍历全部节点(可以遍历子树节点);
使用树结构tree代替平铺的map即可实现.
没有实现0成本复制删除,但复杂度应该已可接受.

从直接过滤 dump 文件,改为产生一个大的 include 列表,
然后 svnadmin dump | svndumpfilter include --drop-empty-revs --targets inc.txt 来执行;

TODO: 过滤过程会产生一些空提交, 考虑删除;



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
    # 试验产生的dump文件略有差别(换行符), 但 load 后 co 正常,内容相同
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

#模拟svn仓库
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
            # 可能同个 rev 里, 先delete A, 然后 B copy from A
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
            # 随目录copy而产生, 没有单独的 Node-action: add  不应过滤
            # 但有可能其复制来源已经被忽略, 则导致 svnadmin load 出错;
            # 因此过滤之后仍调用 recrod 模拟, 判断文件是否还在
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


