
KEYWORDS: svndump minimize compress clean
ABSTRACT: 
  remove all junk (or confidential ) files from the svndump file, according to the HEAD version of the depository;
  All files which is has already been "svn del" from repository but still in the history, will be removed from the svndump file, to make the repository size minimized. 
  从 SVN DUMP 文件中删除"垃圾或敏感文件"(已经svn del但还留在历史里), 使其体积最小化的工具


以最终状态为准, 凡是与最终保留文件相关的历史文件都被保留, 否则被删除;
EXAMPLE:
文件 /a/b.txt, 被改名为 /a/b1.txt, 则历史中应保留 /a/b.txt /a/b1.txt
文件 /a/b.txt, 被改名为 /a/b1.txt, 随后被删除; 则历史中应删除 /a/b.txt /a/b1.txt
如果 /a 被删除后 又提交了新的无关的 /a, 则历史中的第一个 /a 仍然被保留;

使用svn过程中,经常可能有人提交一些 .obj .pch 之类垃圾文件,
(或者可能是敏感文件,需要从历史中彻底删除)
已有的 svndumpfilter.exe 需要自行提供路径列表来过滤, 比较麻烦,
而且 svndumpfilter 不考虑依赖关系, 导致得到的 dumpfile 可能无法 load ;

可以先将垃圾文件删除, 然后提交svn.
然后 svnadmin dump 得到 dump 文件,
执行本程序进行过滤, 得到的 dump 文件较小,
然后 svnadmin create; svnadmin load; 得到新的干净的库;

