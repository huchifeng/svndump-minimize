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

TODO: ��Ҫ���һ������� svn �ֿ����, ����ʵ�� 0 �ɱ�Ŀ¼����ɾ��;

TODO: ���˹��̻����һЩ���ύ, ����ɾ��;



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
    # ���������dump�ļ����в��(���з�), �� load �� co ����,������ͬ
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
        # �򵥵� filter, ��ȷ;
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
                # �����ļ��ĸ�Ŀ¼Ҳ��Ҫ����
                for k in parent_path(j):
                    self.keep[k] = 1;
        for i in self.keep:
            print "keep", i;
        self.status = collections.defaultdict(lambda:"");
    def minimize_write(self, header, header_str, prop, bytes):
        if('Node-path' in header and not(header['Node-path'] in self.keep)):
            if(self.status[header['Node-path']]=='' and header['Node-action']=='delete'):
                # ��Ŀ¼copy������, û�е����� Node-action: add
                #  ��Ӧ����
                dump(self.f, header, header_str, prop, bytes);
                return;
            self.status[header['Node-path']] = header['Node-action'];
            print "ignore", header['Node-path'];
            return;
        dump(self.f, header, header_str, prop, bytes);

#���� sha1 ����
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
#            # ������Ŀ¼�ļ�
#            for i in self.sha1.copy():
#                if(is_in_dir(i, path)):
#                    del self.sha1[i];
#            return;
#        # Ŀ¼����
#        assert 0, 'not implemented yet'
#        pass
#    def minimize_calc_filter(self):
#        assert 0, 'not implemented yet'
#    def minimize_write(self, header, header_str, prop, bytes):
#        assert 0, 'not implemented yet'

#ģ��svn�ֿ�
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


