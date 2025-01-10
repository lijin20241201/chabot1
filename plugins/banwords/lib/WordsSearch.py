#!/usr/bin/env python
# -*- coding:utf-8 -*-
# ToolGood.Words.WordsSearch.py
__all__ = ['WordsSearch']

# TrieNode 类用于创建一个字典树的节点。每个节点代表一个字符，并且指向其子节点，帮助我们高效地存储和匹配敏感词。
class TrieNode():
    def __init__(self):
        self.Index = 0
        self.Layer = 0 # 节点所在的层级。
        self.End = False # 标记节点是否是敏感词的结尾
        self.Char = '' # 该节点对应的字符。
        # 假设我们有敏感词列表：["ab", "abc", "abcd"]。a 节点是所有三个敏感词的开始（即 "ab", "abc", "abcd"）。
        # 但是，a 不是任何一个敏感词的结尾节点。 因此，a 节点的 Results 列表应该是空的，即 Results = []
        # d 节点是 "abcd" 的结尾节点。同时，d 也是 "ab", "abc", "abcd" 这三个敏感词的结尾节点。
        # d 节点的 Results 列表应该包含所有三个敏感词的索引：[0, 1, 2]，分别表示 "ab"（索引 0）、
        # "abc"（索引 1）、和 "abcd"（索引 2）。
        self.Results = [] # 如果当前节点不是任何敏感词的结尾,results是空列表,如果是,results存储敏感词对应的索引
        self.m_values = {} # m_values 存储当前节点的子节点的字典，键是字符的 ASCII 值，值是子节点。
        self.Failure = None # Failure 指向失配的下一个节点，用于 Aho-Corasick 算法的优化。
        self.Parent = None  # 父节点
    # Add 方法用来添加新的字符节点到当前节点的子节点字典 m_values 中。
    def Add(self,c):
        # 如果该字符节点已经存在，直接返回现有节点
        if c in self.m_values :
            return self.m_values[c] 
        node = TrieNode()  # 创建一个新的子节点
        node.Parent = self  # 设置父节点
        node.Char = c # 设置节点字符
        self.m_values[c] = node # 将子节点添加到 m_values 字典
        return node # 返回新节点
    
    def SetResults(self,index): # index是节点是敏感词结尾，对应的敏感词的索引
        if (self.End == False): # 如果当前节点不是敏感词结尾
            self.End = True  # 将当前节点标记为敏感词结尾
        self.Results.append(index) # 将当前敏感词的索引添加到结果列表
# TrieNode2 是优化版的节点类，通过记录 minflag 和 maxflag 来加速查找，避免逐个遍历节点字符。
class TrieNode2():
    def __init__(self):
        self.End = False # 标记是否为敏感词结尾
        self.Results = [] # 存储匹配的敏感词索引
        self.m_values = {} # 子节点字典，存储字符与对应节点的映射。
        self.minflag = 0xffff # 记录节点字符的最小值，用于加速查找
        self.maxflag = 0 # 记录节点字符的最大值，用于加速查找

    def Add(self,c,node3):
        if (self.minflag > c):
            self.minflag = c  # 更新最小字符
        if (self.maxflag < c):
             self.maxflag = c # 更新最大字符
        self.m_values[c] = node3  # 将子节点添加到 m_values 字典
    # SetResults 方法将当前节点标记为敏感词结尾，并将其关联的敏感词索引添加到 Results 列表中。
    def SetResults(self,index):
        if (self.End == False) :
            self.End = True # 将节点标记为敏感词的结尾
        if (index in self.Results )==False : 
            self.Results.append(index) # 将敏感词索引添加到结果列表
    # HasKey 方法检查当前节点是否有某个字符的子节点。
    def HasKey(self,c):
        return c in self.m_values   # 检查当前节点是否包含字符 c 的子节点
        
     # TryGetValue 方法用于在字符范围内查找子节点。
    def TryGetValue(self,c):
        if (self.minflag <= c and self.maxflag >= c):  # 判断字符是否在当前节点的字符范围内
            if c in self.m_values:
                return self.m_values[c] # 返回对应的子节点
        return None # 如果不在范围内，返回 None

# WordsSearch 类是核心类，负责敏感词的加载、查找和替换。
class WordsSearch():
    def __init__(self):
        self._first = {} # 存储 Aho-Corasick 算法的优化根节点。
        self._keywords = [] # 存储敏感词列表
        self._indexs=[]  # 存储敏感词索引
    def SetKeywords(self,keywords):
        self._keywords = keywords 
        self._indexs=[i for i in range(len(keywords))]   # 为每个敏感词生成一个索引
        root = TrieNode() # 初始化树根
        allNodeLayer={} # 用于存储所有节点按层级分组
        for i in range(len(self._keywords)): # 遍历所有敏感词
            p = self._keywords[i] # 获取索引对应的敏感词
            nd = root # 从根节点开始
            for j in range(len(p)):  # 遍历每个敏感词的字符
                nd = nd.Add(ord(p[j])) # 添加字符节点,这时nd从上个父节点指向了新节点(刚刚创建的子节点,这时它的Layer还是0)
                if (nd.Layer == 0):
                    nd.Layer = j + 1 # 因为j在逐渐改变,所以在一个敏感词内,从左到右,层级变大
                    if nd.Layer in allNodeLayer: # 存在当前层级
                        allNodeLayer[nd.Layer].append(nd) # 追加
                    else: # 否则新建
                        allNodeLayer[nd.Layer] = [nd] 
            nd.SetResults(i)  # 这时nd对应的刚好是敏感词的结尾,这时把节点对应的敏感词的索引加入
        allNode = [root]  # 包含根节点
        for key in allNodeLayer.keys():  # 遍历所有层级的节点
            allNode.extend(allNodeLayer[key])
        allNodeLayer=None
        for i in range(len(allNode)):  # 遍历所有节点，构建失败指针
            if i==0 :
                continue
            nd=allNode[i] # 获取当前节点
            nd.Index = i # 节点对应的索引
            r = nd.Parent.Failure  # 当前节点的父节点的失败指针
            c = nd.Char # 当前节点对应的字符
            while r  and c not in r.m_values:
                r = r.Failure
            if r == None: # 如果r是None,就是i=1时,这时r会是root的Failure，是None,这时指定为root
                nd.Failure = root
            else:
                nd.Failure = r.m_values[c]
                for key2 in nd.Failure.Results :
                    nd.SetResults(key2)
        root.Failure = root

        allNode2 = []
        for i in range(len(allNode)): # for (i = 0; i < allNode.length; i++) 
            allNode2.append( TrieNode2())
        
        for i in range(len(allNode2)): # for (i = 0; i < allNode2.length; i++) 
            oldNode = allNode[i]
            newNode = allNode2[i]

            for key in oldNode.m_values :
                index = oldNode.m_values[key].Index
                newNode.Add(key, allNode2[index])
            
            for index in range(len(oldNode.Results)): # for (index = 0; index < oldNode.Results.length; index++) 
                item = oldNode.Results[index]
                newNode.SetResults(item)
            
            oldNode=oldNode.Failure
            while oldNode != root:
                for key in oldNode.m_values :
                    if (newNode.HasKey(key) == False):
                        index = oldNode.m_values[key].Index
                        newNode.Add(key, allNode2[index])
                for index in range(len(oldNode.Results)): 
                    item = oldNode.Results[index]
                    newNode.SetResults(item)
                oldNode=oldNode.Failure
        allNode = None
        root = None

        # first = []
        # for index in range(65535):# for (index = 0; index < 0xffff; index++) 
        #     first.append(None)
        
        # for key in allNode2[0].m_values :
        #     first[key] = allNode2[0].m_values[key]
        
        self._first = allNode2[0]
    
    # 查找文本中的第一个敏感词。
    def FindFirst(self,text):
        ptr = None
        for index in range(len(text)): # for (index = 0; index < text.length; index++) 
            t =ord(text[index]) # text.charCodeAt(index)
            tn = None
            if (ptr == None):
                tn = self._first.TryGetValue(t)
            else:
                tn = ptr.TryGetValue(t)
                if (tn==None):
                    tn = self._first.TryGetValue(t)
                
            
            if (tn != None):
                if (tn.End):
                    item = tn.Results[0]
                    keyword = self._keywords[item]
                    return { "Keyword": keyword, "Success": True, "End": index, "Start": index + 1 - len(keyword), "Index": self._indexs[item] }
            ptr = tn
        return None
    # 查找文本中的所有敏感词
    def FindAll(self,text):
        ptr = None
        list = []

        for index in range(len(text)): # for (index = 0; index < text.length; index++) 
            t =ord(text[index]) # text.charCodeAt(index)
            tn = None
            if (ptr == None):
                tn = self._first.TryGetValue(t)
            else:
                tn = ptr.TryGetValue(t)
                if (tn==None):
                    tn = self._first.TryGetValue(t)
                
            
            if (tn != None):
                if (tn.End):
                    for j in range(len(tn.Results)): # for (j = 0; j < tn.Results.length; j++) 
                        item = tn.Results[j]
                        keyword = self._keywords[item]
                        list.append({ "Keyword": keyword, "Success": True, "End": index, "Start": index + 1 - len(keyword), "Index": self._indexs[item] })
            ptr = tn
        return list

    # 检查文本是否包含任何敏感词。
    def ContainsAny(self,text):
        ptr = None
        for index in range(len(text)): # for (index = 0; index < text.length; index++) 
            t =ord(text[index]) # text.charCodeAt(index)
            tn = None
            if (ptr == None):
                tn = self._first.TryGetValue(t)
            else:
                tn = ptr.TryGetValue(t)
                if (tn==None):
                    tn = self._first.TryGetValue(t)
            
            if (tn != None):
                if (tn.End):
                    return True
            ptr = tn
        return False
    # 将文本中的敏感词替换成指定的字符（默认是 *）。
    def Replace(self,text, replaceChar = '*'):
        result = list(text) 

        ptr = None
        for i in range(len(text)): # for (i = 0; i < text.length; i++) 
            t =ord(text[i]) # text.charCodeAt(index)
            tn = None
            if (ptr == None):
                tn = self._first.TryGetValue(t)
            else:
                tn = ptr.TryGetValue(t)
                if (tn==None):
                    tn = self._first.TryGetValue(t)
            
            if (tn != None):
                if (tn.End):
                    maxLength = len( self._keywords[tn.Results[0]])
                    start = i + 1 - maxLength
                    for j in range(start,i+1): # for (j = start; j <= i; j++) 
                        result[j] = replaceChar
            ptr = tn
        return ''.join(result) 