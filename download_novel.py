import os
import requests
import aiohttp
import asyncio
from bs4 import BeautifulSoup,Tag

base_url = 'https://www.qu.la'
base_dir = 'novel/' 

# 通过requests的方式获取html
def get_html_content(url): 
    r = requests.get(url)
    r.raise_for_status
    r.encoding = 'utf-8'
    return BeautifulSoup(r.text,'html.parser')

# 解析排行榜分类、书名、及小说的url地址
'''
[
    {
        'name': '排行榜名',
        'books': [
            {
                'url': '书籍下载地址',
                'name': '书名'
            }
        ]
    }
]
'''
def get_class_book_url_list(content):
    books = list()
    main = content.find_all('div',{'id':'main'})[0]
    divs = chooice_tags(main.contents)
    for div in divs:
        contents = chooice_tags(div.contents)
        # 排行榜类型名
        name = contents[0].find_all('span')[0].string
        # 解析该排名下的小说列表
        books_list = chooice_tags(contents[1].contents)[0]
        li_list = books_list.find_all('li')
        # 解析书名与链接
        b_list = list()
        for li in li_list:
            a = li.find_all('a')[0]
            # 小说地址
            url = a.attrs['href']
            # 书名
            book_name = a.string
            b_list.append({'url':base_url + url,'name':book_name})
        books.append({'name':name,'books':b_list})
    return books

# 去除bs4中的字符，保留tag类型
def chooice_tags(tags):
    tag_list = list()
    for tag in tags:
        if isinstance(tag,Tag):
            tag_list.append(tag)
    return tag_list

# 创建目录
# 返回目录路径
def make_dir(name):
    # 去除首尾空格
    name = base_dir + name.strip()
    if not os.path.exists(name):
        os.makedirs(name)
    return name

# 根据分类创建文件夹并下载小说
# 返回分组任务
def download_book_list(class_books):
    groups = list()
    for node in class_books:
        name = node['name']
        books = node['books']
        path = make_dir(name)
        tasks = [download_book(book['url'],path,book['name']) for book in books]
        groups.append(asyncio.gather(*tasks))
    return groups

# 下载一本小说
async def download_book(url,path,name):
    print('download book [{}] start...'.format(name))
    content = await get_content(url)
    # 解析章节列表
    chapter_list = content.find_all('div',{'id':'list'})[0].find_all('dl')[0].contents
    chapter_list = chooice_tags(chapter_list)
    # 打开存放小说的文件
    text_file = open(path + '/' + name + '.txt','w',encoding='utf-8')
    # 限制最大并发数
    sem = asyncio.Semaphore(10)
    # 标识是否下载该章节
    is_download = True
    for chapter in chapter_list:
        if chapter.name == 'dt':
            if chapter.string.find('最新章节') is not -1:
                is_download = False
            else:
                is_download = True
            continue
        if is_download:
            async with sem:
                await download_chapter(text_file,url,chapter)
    text_file.close()
    print('download book [{}] end...'.format(name))

# 下载一个章节
async def download_chapter(text_file,url,node):
    a = node.find_all('a')[0]
    # 章节标题
    title = a.string
    print('download chapter [{}] start...'.format(title))
    # 章节uri
    uri = a.attrs['href']
    content = await get_content(url + uri)
    attr = content.find_all('div',{'id':'content'})[0]
    text = attr.get_text()
    text_file.write(title + '\n')
    text_file.write(text + '\n')
    print('download chapter [{}] end...'.format(title))

# aio获取html
async def fetch(session,url):
    count = 10
    while count > 0:
        try:
            async with session.get(url) as response:
                return await response.text()
        except BaseException as e:
            print('Error',e)
            count -= 1
    return ''

# aio获取页面bs4元素
async def get_content(url):
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        html = await fetch(session,url)
        return BeautifulSoup(html,'html.parser')

def main():
    # 获取排行榜首页内容
    content = get_html_content(base_url + '/paihangbang/')
    class_books = get_class_book_url_list(content)
    loop = asyncio.get_event_loop()
    # 获得分组任务
    groups = download_book_list(class_books)
    loop.run_until_complete(asyncio.gather(*groups))
    loop.close()

if __name__ == '__main__':
    main()
