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
        # 如果写缺省值对象 init={'files':{}}, 导致 {} 会被实例间复用,
        self.__dict__ = init;

#模拟svn仓库
class svn_db():
    def __init__(self):
        self.items = {};
        self.current_rev = 0;
    def do_add_change_replace(self, path):
        if(path not in self.items):
            # 可能有多次copy动作指向一个地方,全部保留
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
            self.do_copy_from(f, i, from_rev); # 必须递归
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
                # 有可能从一个已删除的rev中复制, 指定较小的 copyfrom-rev
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
            # 随目录copy而产生, 没有单独的 Node-action: add  不应过滤
            # 但有可能其复制来源已经被忽略, 则导致 svnadmin load 出错;
            # 因此过滤之后仍调用 recrod 模拟, 判断文件是否还在
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


